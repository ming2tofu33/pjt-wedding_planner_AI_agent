# 목적: 노드/툴 실행 중 발생한 에러를 사용자 친화적으로 응답하고, 복구 옵션을 제시한다.

from typing import Optional
import re
from state_mvp import State

_ERROR_TEMPLATES = {
    "db": "데이터를 불러오는 중 문제가 있었어요. 조건을 조금 바꿔 다시 시도해볼까요?",
    "llm": "잠깐 이해가 어려웠어요. 문장을 조금만 다르게 말씀해 주실 수 있을까요?",
    "io": "저장 중 문제가 있었어요. 다시 한 번 시도해볼게요.",
    "default": "알 수 없는 문제가 있었어요. 간단히 다시 요청해 주세요.",
}

def _classify_error(reason: Optional[str]) -> str:
    if not reason:
        return "default"
    t = reason.lower()
    if any(k in t for k in ["db","psycopg","sql","query","timeout","read timeout","connection reset","connection","operationalerror","tool_exec"]):
        return "db"
    if any(k in t for k in ["llm","parsing","json","prompt","token","too many requests","rate limit"]):
        return "llm"
    if any(k in t for k in ["memo_update: save failed","file","ioerror","permission"]):
        return "io"
    return "default"

def _sanitize_debug(reason: Optional[str]) -> str:
    if not reason:
        return ""
    cleaned = re.sub(r"(postgresql\+?psycopg2?:\/\/)([^:@\/\s]+)(:[^@\/\s]+)?@", r"\1***@", reason, flags=re.I)
    cleaned = re.sub(r"(api[_-]?key\s*[:=]\s*)[A-Za-z0-9_\-]+", r"\1***", cleaned, flags=re.I)
    cleaned = re.sub(r"([?&](password|apikey|token)=[^&\s]+)", r"\1=***", cleaned, flags=re.I)
    cleaned = re.sub(r"(/?Users|/home)[^\s]+", "***", cleaned)
    return cleaned[:300]

def _fill_recovery_suggestions(state: State, kind: str) -> None:
    if not hasattr(state, 'suggestions') or not isinstance(state.suggestions, list):
        state.suggestions = []
    if not hasattr(state, 'quick_replies') or not isinstance(state.quick_replies, list):
        state.quick_replies = []
    state.suggestions.clear()
    state.quick_replies.clear()

    if kind == "db":
        state.suggestions.extend([
            "지역을 바꿔서 다시 검색",
            "카테고리를 바꿔서 검색",
            "추천 개수를 줄여서 다시 시도",
        ])
        state.quick_replies.extend([
            "전지역으로 검색",
            "스튜디오로 변경",
            "결과 5개만 보기",
        ])
    elif kind == "llm":
        state.suggestions.extend([
            "짧고 명확하게 다시 말하기",
            "예산/지역/카테고리 중 2개만 먼저 지정",
            "예시 문장 보여줘",
        ])
        state.quick_replies.extend([
            "강남 웨딩홀 5곳 보여줘",
            "스튜디오 5곳 추천",
            "드레스 200만원 이하",
        ])
    elif kind == "io":
        state.suggestions.extend([
            "요약을 빼고 다시 저장",
            "새 세션으로 다시 시작",
            "메모 경로를 확인",
        ])
        state.quick_replies.extend([
            "다시 저장해줘",
            "처음부터 다시",
            "요약 없이 진행",
        ])
    else:
        state.suggestions.extend([
            "간단히 다시 요청",
            "카테고리만 먼저 지정",
            "지역만 먼저 지정",
        ])
        state.quick_replies.extend([
            "웨딩홀 찾기",
            "스튜디오 찾기",
            "전지역으로 검색",
        ])

def error_handler_node(state: State) -> State:
    """
    공통 에러 핸들러(MVP):
    - state.status, state.reason 기반 사용자 메시지/제안 구성
    - 상태를 'error'로 유지하되 answer를 깔끔히 작성
    """
    try:
        kind = _classify_error(state.reason)
        user_msg = _ERROR_TEMPLATES.get(kind, _ERROR_TEMPLATES["default"])

        ctx_parts = []
        if isinstance(state.total_budget_manwon, int):
            ctx_parts.append(f"예산 {state.total_budget_manwon}만원")
        if state.wedding_date:
            ctx_parts.append(f"예식일 {state.wedding_date}")
        if state.region_keyword:
            ctx_parts.append(f"지역 {state.region_keyword}")
        ctx_tail = f"\n\n기억하고 있는 정보: {' · '.join(ctx_parts)}" if ctx_parts else ""

        state.answer = f"{user_msg}{ctx_tail}"
        _fill_recovery_suggestions(state, kind)

        state.status = "error"
        dbg = _sanitize_debug(state.reason)
        state.response_content = (state.response_content or "")
        if len(state.response_content) > 800:
            state.response_content = state.response_content[-800:]
        state.response_content += f" [error_handler: {kind}" + (f" | {dbg}]" if dbg else "]")
        return state
        
    except Exception as e:
        state.answer = "일시적인 문제가 발생했습니다. 다시 시도해주세요."
        state.status = "error"
        state.reason = f"error_handler 실패: {e}"
        if not hasattr(state, 'suggestions'):
            state.suggestions = []
        if not hasattr(state, 'quick_replies'):
            state.quick_replies = []
        state.suggestions = ["간단히 다시 요청", "처음부터 시작"]
        state.quick_replies = ["웨딩홀 찾기", "스튜디오 찾기", "드레스 찾기"]
        return state

if __name__ == "__main__":
    test_cases = [
        ("DB 에러", "[tool_exec] DB query timeout at postgresql://user:pw@localhost:5432/db"),
        ("LLM 에러", "[parsing] LLM JSON 파싱 실패: too many requests"),
        ("IO 에러", "[memo_update: save failed] permission denied /Users/path/memo.json"),
        ("일반 에러", "unknown error occurred"),
        ("빈 에러", None),
    ]
    for test_name, reason in test_cases:
        s = State()
        s.reason = reason
        s.total_budget_manwon = 300
        s.region_keyword = "강남"
        s.status = "error"
        out = error_handler_node(s)
        print(f"✅ {test_name}: {out.answer}")
        print(f"   제안: {out.suggestions[:1]}")
        print(f"   디버그: {out.response_content}")
        print("---")
