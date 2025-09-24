# 목적: tool_execution_node가 채운 state.rows를 사람이 읽기 좋은 텍스트로 정리해 최종 답변(state.answer) 생성
# 특징:
# - 대화 히스토리를 MessagesState에 자동 업데이트
# - 기존 state.answer가 있으면 결과 목록을 "덧붙이는" 합성 방식
# - 결과 헤더/항목 포맷과 풍부한 제안은 기존(네 버전) 유지
# - 안전 가드(limit 클램프, None 처리) 추가

from typing import List, Dict, Any, Optional
from state_mvp import State, ensure_user_id
from langchain_core.messages import HumanMessage, AIMessage

# ---- 간단 유틸 ----
VENDOR_LABEL = {
    "wedding_hall": "웨딩홀",
    "studio": "스튜디오",
    "wedding_dress": "드레스",
    "makeup": "메이크업",
}

def _clamp_limit(n: Optional[int]) -> int:
    try:
        i = int(n or 5)
    except Exception:
        i = 5
    return max(1, min(i, 20))

def _fmt_price_manwon(v: Optional[int]) -> str:
    return f"{int(v)}만원" if isinstance(v, int) else "-"

def _fmt_header(state: State) -> str:
    ty = VENDOR_LABEL.get(state.get("vendor_type") or "", state.get("vendor_type") or "업체")
    region = state.get("region_keyword") or "전체"
    lim = _clamp_limit(state.get("limit"))
    return f"🗂 {region} 지역 {ty} 상위 {lim}건"

def _fmt_item(i: Dict[str, Any], idx: int) -> str:
    name = i.get("name") or "-"
    region = i.get("region") or "-"
    price = _fmt_price_manwon(i.get("price_manwon"))

    # extra에서 대표 1~2개만 간단 노출 (있을 때)
    extra = i.get("extra") or {}
    extra_snippets: List[str] = []

    # 필드명이 테이블마다 달라서 가장 흔한 것만 가볍게
    for key in ["hall_rental_fee", "meal_expense", "std_price", "wedding", "photo", "manager(2)"]:
        if key in extra and extra[key] is not None:
            val = extra[key]
            if isinstance(val, (int, float)):
                extra_snippets.append(f"{key}: {int(val)}만원")
            else:
                extra_snippets.append(f"{key}: {val}")

    extras = f" | {' / '.join(extra_snippets)}" if extra_snippets else ""
    return f"{idx}. {name} · {region} · {price}{extras}"

def _compose_success_answer(state: State, rows: List[Dict[str, Any]]) -> str:
    # 대화 맥락을 고려한 더 자연스러운 답변 생성
    conversation_context = state.get("recent_conversation_context", "")
    is_continuation = "human:" in conversation_context.lower() and len(conversation_context) > 20
    
    # 대화 맥락에 따른 인사말 조정
    if is_continuation:
        greeting = ""  # 대화 중이면 인사말 생략
    else:
        greeting = "안녕하세요! 웨딩 플래너 마리예요 ✨\n\n"
    
    header = _fmt_header(state)
    lines = [greeting + header, ""]
    take = _clamp_limit(state.get("limit"))
    for idx, r in enumerate(rows[: take], start=1):
        lines.append(_fmt_item(r, idx))

    # 상황 정보(예산/날짜)가 있으면 한 줄 덧붙임
    budget = state.get("total_budget_manwon")
    wdate = state.get("wedding_date")
    meta_line_parts: List[str] = []
    if isinstance(budget, int):
        meta_line_parts.append(f"총예산 {budget}만원 기준")
    if wdate:
        meta_line_parts.append(f"예식일 {wdate}")
    if meta_line_parts:
        lines.extend(["", "ℹ️ " + " · ".join(meta_line_parts)])

    # 후속 제안 리드
    lines.extend(["", "더 자세한 정보가 필요하시거나 다른 조건으로 검색하고 싶으시면 말씀해 주세요!"])
    return "\n".join(lines)

def _compose_empty_answer(state: State) -> str:
    """검색 결과가 없을 때 대화 맥락을 고려한 답변"""
    conversation_context = state.get("recent_conversation_context", "")
    is_continuation = "human:" in conversation_context.lower() and len(conversation_context) > 20
    
    ty = VENDOR_LABEL.get(state.get("vendor_type") or "", state.get("vendor_type") or "업체")
    region = state.get("region_keyword") or "해당 지역"
    
    if is_continuation:
        # 대화 중이면 더 자연스러운 표현
        empty_msg = (
            f"아쉽게도 {region}에서 조건에 맞는 {ty}을 찾지 못했어요 😅\n\n"
            f"• 다른 지역으로 범위를 넓혀볼까요?\n"
            f"• 예산 조건을 조정해보시거나\n"
            f"• 다른 업체 유형도 함께 살펴보시는 건 어떨까요?"
        )
    else:
        # 첫 대화면 더 상세한 안내
        empty_msg = (
            f"안녕하세요! 웨딩 플래너 마리예요 ✨\n\n"
            f"현재 조건으로는 {region} {ty} 검색 결과가 없네요.\n\n"
            f"이런 방법들을 시도해보시면 어떨까요?\n"
            f"• 지역을 바꾸거나 넓혀보기\n"
            f"• 예산 범위 조정하기\n"
            f"• 다른 업체 유형 검색하기"
        )
    
    return empty_msg

def _fill_suggestions(state: State, has_results: bool) -> None:
    """state.suggestions / state.quick_replies 채움 (대화 맥락 고려)"""
    current_suggestions = state.get("suggestions", [])
    current_quick_replies = state.get("quick_replies", [])
    
    if not isinstance(current_suggestions, list):
        current_suggestions = []
    if not isinstance(current_quick_replies, list):
        current_quick_replies = []

    # 중복 최소화를 위해 set으로 잠깐 관리
    sg_set = set(current_suggestions)
    qr_set = set(current_quick_replies)

    if has_results:
        sg_set.update([
            "더 저렴한 곳 보여줘",
            "다른 지역으로 추천해줘",
            "비슷한 가격대 더 보여줘",
        ])
        ty = VENDOR_LABEL.get(state.get("vendor_type") or "", "업체")
        nxt = _clamp_limit((state.get("limit") or 5) + 5)
        qr_set.update([
            f"{ty} 더 보기",
            "지역 변경",
            "예산 조정",
        ])
    else:
        sg_set.update([
            "지역을 넓혀서 다시 검색해줘",
            "예산 범위를 늘려줘", 
            "다른 업체 유형으로 찾아줘",
        ])
        qr_set.update([
            "전체 지역 검색",
            "예산 올리기",
            "업체 유형 변경",
        ])

    # 다시 리스트로 반영
    state["suggestions"] = list(sg_set)[:8]
    state["quick_replies"] = list(qr_set)[:5]

def _update_conversation_history(state: State) -> None:
    """대화 히스토리를 MessagesState에 업데이트"""
    try:
        user_input = state.get("user_input")
        answer = state.get("answer")
        
        if not user_input or not answer:
            return
            
        # 현재 messages 가져오기
        messages = state.get("messages", [])
        if not isinstance(messages, list):
            messages = []
        
        # 중복 방지: 마지막 메시지가 현재 입력과 같으면 추가하지 않음
        if messages and len(messages) > 0:
            last_message = messages[-1]
            if (hasattr(last_message, 'content') and last_message.content == user_input) or \
               (isinstance(last_message, dict) and last_message.get('content') == user_input):
                return
        
        # 새 메시지 추가
        messages.append(HumanMessage(content=user_input))
        messages.append(AIMessage(content=answer))
        
        # 메시지 히스토리 길이 제한 (최근 20개 메시지만 유지)
        if len(messages) > 20:
            messages = messages[-20:]
        
        state["messages"] = messages
        
    except Exception as e:
        print(f"⚠️  대화 히스토리 업데이트 실패: {e}")

def response_generation_node(state: State) -> State:
    """
    - tool_exec 결과 rows를 보기 좋게 포맷
    - 대화 맥락을 고려한 자연스러운 답변 생성
    - MessagesState에 대화 히스토리 자동 업데이트
    - suggestions / quick_replies 보강
    """
    try:
        # user_id 보장
        ensure_user_id(state)
        
        rows = state.get("rows", [])

        if state.get("status") == "error":
            # error_handler_node가 이미 사용자 멘트를 만들었을 가능성 높음
            # 여기선 제안만 보강하고 종료
            _fill_suggestions(state, has_results=False)
            return state

        if not rows:
            # 검색 결과가 없을 때 대화 맥락을 고려한 답변
            state["answer"] = _compose_empty_answer(state)
            _fill_suggestions(state, has_results=False)
            state["status"] = "empty"
            current_reason = state.get("reason", "")
            state["reason"] = current_reason + " [response_gen: empty]"
        else:
            # 성공 케이스: 대화 맥락을 고려한 답변 생성
            state["answer"] = _compose_success_answer(state, rows)
            _fill_suggestions(state, has_results=True)
            state["status"] = "ok"
            state["response_content"] = f"[response_gen] rows={len(rows)} limit={_clamp_limit(state.get('limit'))}"

        # 대화 히스토리 업데이트 (MessagesState 활용)
        _update_conversation_history(state)
        
        return state

    except Exception as e:
        state["status"] = "error"
        state["answer"] = "죄송해요, 답변을 준비하는 중에 문제가 생겼어요. 다시 한번 말씀해 주시겠어요?"
        state["reason"] = f"[response_gen] 실패: {e}"
        _fill_suggestions(state, has_results=False)
        
        # 에러 상황에서도 대화 히스토리 업데이트 시도
        _update_conversation_history(state)
        
        return state