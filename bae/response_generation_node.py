# 목적: tool_execution_node가 채운 state.rows를 사람이 읽기 좋은 텍스트로 정리해 최종 답변(state.answer) 생성
# 특징:
# - 기존 state.answer가 있으면 결과 목록을 "덧붙이는" 합성 방식
# - 결과 헤더/항목 포맷과 풍부한 제안은 기존(네 버전) 유지
# - 안전 가드(limit 클램프, None 처리) 추가

from typing import List, Dict, Any, Optional
from state_mvp import State

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
    header = _fmt_header(state)
    lines = [header, ""]
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
    lines.extend(["", "다음 중 하나를 선택해 더 좁혀볼까요?"])
    return "\n".join(lines)

def _fill_suggestions(state: State, has_results: bool) -> None:
    """state.suggestions / state.quick_replies 채움"""
    # 기존에 general_response 등에서 넣은 제안이 있을 수도 있으니 덮어쓰기 대신 "보강" 위주로 동작
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
            "가격 상한을 정해 다시 보여줘",
            "다른 지역으로 추천해줘",
            "비슷한 가격대 더 보여줘",
        ])
        ty = VENDOR_LABEL.get(state.get("vendor_type") or "", "업체")
        nxt = _clamp_limit((state.get("limit") or 5) + 5)
        qr_set.update([
            f"{ty} 더 보기 {nxt}개",
            "지역을 강남으로 변경",
            "예산 300만원 이하로",
        ])
    else:
        sg_set.update([
            "지역을 넓혀 다시 검색해줘",
            "예산 범위를 늘려줘",
            "다른 카테고리로 찾아줘",
        ])
        qr_set.update([
            "전지역으로 다시 검색",
            "예산 +100만원",
            "카테고리를 스튜디오로 변경",
        ])

    # 다시 리스트로 반영 (원래 순서는 대략 유지)
    state["suggestions"] = list(sg_set)[:10]
    state["quick_replies"] = list(qr_set)[:6]

def response_generation_node(state: State) -> State:
    """
    - tool_exec 결과 rows를 보기 좋게 포맷
    - 기존 state.answer가 있으면 그 아래에 결과를 덧붙임
    - 결과 없으면 친절한 가이드 제공
    - suggestions / quick_replies 보강
    """
    try:
        rows = state.get("rows", [])

        if state.get("status") == "error":
            # error_handler_node가 이미 사용자 멘트를 만들었을 가능성 높음
            # 여기선 제안만 보강하고 종료
            _fill_suggestions(state, has_results=False)
            return state

        if not rows:
            ty = VENDOR_LABEL.get(state.get("vendor_type") or "", state.get("vendor_type") or "업체")
            region = state.get("region_keyword") or "전체"
            base = state.get("answer") or ""
            empty_msg = (
                f"현재 조건으로는 {region} 지역 {ty} 결과가 없어요.\n"
                f"- 지역을 바꾸거나 넓혀볼까요?\n"
                f"- 예산(만원)을 조정하거나 키워드를 줄여보면 좋아요."
            )
            state["answer"] = f"{base}\n\n{empty_msg}".strip() if base else empty_msg
            _fill_suggestions(state, has_results=False)
            state["status"] = "empty"
            current_reason = state.get("reason", "")
            state["reason"] = current_reason + " [response_gen: empty]"
            return state

        # 성공 케이스: 기존 answer가 있으면 이어붙이고, 없으면 새로 구성
        list_block = _compose_success_answer(state, rows)
        current_answer = state.get("answer")
        if current_answer:
            state["answer"] = f"{current_answer}\n\n{list_block}"
        else:
            state["answer"] = list_block

        _fill_suggestions(state, has_results=True)
        state["status"] = "ok"
        state["response_content"] = f"[response_gen] rows={len(rows)} limit={_clamp_limit(state.get('limit'))}"
        return state

    except Exception as e:
        state["status"] = "error"
        state["answer"] = "응답을 정리하는 중 문제가 생겼어요. 조건을 조금 바꿔 다시 시도해볼까요?"
        state["reason"] = f"[response_gen] 실패: {e}"
        _fill_suggestions(state, has_results=False)
        return state