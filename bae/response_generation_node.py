# 목적: tool_execution_node가 채운 state.rows를 사람이 읽기 좋은 텍스트로 정리해 최종 답변(state.answer) 생성
from typing import List, Dict, Any, Optional
from state_mvp import State

# ---- 간단 유틸 ----
VENDOR_LABEL = {
    "wedding_hall": "웨딩홀",
    "studio": "스튜디오",
    "wedding_dress": "드레스",
    "makeup": "메이크업",
}
def _fmt_price_manwon(v: Optional[int]) -> str:
    return f"{int(v)}만원" if isinstance(v, int) else "-"

def _fmt_header(state: State) -> str:
    ty = VENDOR_LABEL.get(state.vendor_type or "", state.vendor_type or "업체")
    region = state.region_keyword or "전체"
    lim = state.limit or 5
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
            # 숫자면 만원 가정, 문자열이면 그대로
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
    for idx, r in enumerate(rows[: (state.limit or 5)], start=1):
        lines.append(_fmt_item(r, idx))

    # 상황 정보(예산/날짜)가 있으면 한 줄 덧붙임
    budget = state.total_budget_manwon
    wdate = state.wedding_date
    meta_line_parts: List[str] = []
    if isinstance(budget, int):
        meta_line_parts.append(f"총예산 {budget}만원 기준")
    if wdate:
        meta_line_parts.append(f"예식일 {wdate}")
    if meta_line_parts:
        lines.extend(["", "ℹ️ " + " · ".join(meta_line_parts)])

    # 후속 제안
    lines.extend(["", "다음 중 하나를 선택해 더 좁혀볼까요?"])
    return "\n".join(lines)

def _fill_suggestions(state: State, has_results: bool) -> None:
    """state.suggestions / state.quick_replies 채움"""
    state.suggestions.clear()
    state.quick_replies.clear()

    if has_results:
        # 결과가 있을 때
        state.suggestions.extend([
            "가격 상한을 정해 다시 보여줘",
            "다른 지역으로 추천해줘",
            "비슷한 가격대 더 보여줘",
        ])
        # 빠른 답변 버튼 예시
        ty = VENDOR_LABEL.get(state.vendor_type or "", "업체")
        state.quick_replies.extend([
            f"{ty} 더 보기 {min((state.limit or 5) + 5, 20)}개",
            "지역을 강남으로 변경",
            "예산 300만원 이하로",
        ])
    else:
        # 결과가 없을 때
        state.suggestions.extend([
            "지역을 넓혀 다시 검색해줘",
            "예산 범위를 늘려줘",
            "다른 카테고리로 찾아줘",
        ])
        state.quick_replies.extend([
            "전지역으로 다시 검색",
            "예산 +100만원",
            "카테고리를 스튜디오로 변경",
        ])

def response_generation_node(state: State) -> State:
    """
    - state.rows를 사용해 최종 답변 텍스트 생성
    - 결과가 없으면 친절한 가이드 제공
    - suggestions / quick_replies도 세팅
    """
    try:
        rows = state.rows or []

        if state.status == "error":
            # error_handler_node가 따로 있다면 거기서 최종 멘트를 담당해도 됨.
            state.answer = "잠깐 문제가 있었어요. 잠시 뒤 다시 시도해볼게요."
            _fill_suggestions(state, has_results=False)
            return state

        if not rows:
            ty = VENDOR_LABEL.get(state.vendor_type or "", state.vendor_type or "업체")
            region = state.region_keyword or "전체"
            state.answer = (
                f"현재 조건으로는 {region} 지역 {ty} 결과가 없어요.\n"
                f"- 지역을 바꾸거나 넓혀볼까요?\n"
                f"- 예산(만원)을 조정하거나 키워드를 줄여보면 좋아요."
            )
            _fill_suggestions(state, has_results=False)
            state.status = "empty"
            state.reason = (state.reason or "") + " [response_gen: empty]"
            return state

        # 성공 케이스
        state.answer = _compose_success_answer(state, rows)
        _fill_suggestions(state, has_results=True)
        state.status = "ok"
        # 디버깅용 response_content 업데이트
        state.response_content = f"[response_gen] rows={len(rows)} limit={state.limit}"
        return state

    except Exception as e:
        state.status = "error"
        state.answer = "응답을 정리하는 중 문제가 생겼어요. 조건을 조금 바꿔 다시 시도해볼까요?"
        state.reason = f"[response_gen] 실패: {e}"
        _fill_suggestions(state, has_results=False)
        return state
