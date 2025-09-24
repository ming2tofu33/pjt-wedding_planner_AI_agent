# 목적: 웨딩과 관련없는 일반 대화/인사 처리 + 웨딩 주제로 부드럽게 안내
# 추가: 스트레스 감지, 예산 현실성 체크, 개인정보 보호, 긍정적 마무리

from typing import List
import os
import re
import random
from state_mvp import State

VENDOR_LABEL = {
    "wedding_hall": "웨딩홀",
    "studio": "스튜디오",
    "wedding_dress": "드레스",
    "makeup": "메이크업",
}

# 최소 현실적 예산 (만원 단위)
MIN_REALISTIC_BUDGETS = {
    "wedding_hall": 1500,
    "studio": 200,
    "wedding_dress": 100,
    "makeup": 50,
}

def _quick_replies_for_category() -> List[str]:
    return ["웨딩홀 찾기", "스튜디오 찾기", "드레스 찾기", "메이크업 찾기"]

def _quick_replies_for_region() -> List[str]:
    return ["지역을 강남으로", "지역을 홍대로", "지역을 전지역으로"]

def _clamp_limit(n: int | None) -> int:
    try:
        i = int(n or 5)
    except Exception:
        i = 5
    return max(1, min(i, 20))

def _quick_replies_for_limits(limit: int) -> List[str]:
    limit = _clamp_limit(limit)
    nxt = _clamp_limit(limit + 5)
    return [f"{nxt}개로 더 보기", "5개만 간단히", "10개 추천받기"]

def _format_known_context(state: State) -> str:
    parts = []
    if state.get("total_budget_manwon") and isinstance(state.get("total_budget_manwon"), int):
        parts.append(f"예산 {state['total_budget_manwon']}만원")
    if state.get("wedding_date"):
        parts.append(f"예식일 {state['wedding_date']}")
    if state.get("region_keyword"):
        parts.append(f"지역 {state['region_keyword']}")
    return " · ".join(parts)

def _detect_stress_signals(text: str) -> bool:
    """결혼 준비 스트레스 신호 감지"""
    if not text:
        return False
    t = text.lower()
    stress_words = [
        "힘들어","스트레스","지쳐","벅차","복잡해",
        "모르겠어","막막해","답답해","걱정","불안",
        "어려워","혼란","피곤","우울","포기",
    ]
    return any(word in t for word in stress_words)

def _budget_reality_check(budget: int, vendor_type: str | None) -> str:
    """예산이 너무 낮으면 현실적 조언"""
    if not vendor_type:
        return ""
    min_budget = MIN_REALISTIC_BUDGETS.get(vendor_type)
    if min_budget and budget < min_budget:
        return (
            f"말씀하신 예산으로는 선택지가 제한적일 수 있어요. "
            f"현실적으로는 {min_budget}만원 정도부터 시작하시는 것을 추천드려요."
        )
    return ""

def _contains_personal_info(text: str) -> bool:
    """개인정보 포함 여부 체크(간단 휴리스틱)"""
    if not text:
        return False
    patterns = [
        r'\d{3}-\d{4}-\d{4}',           # 전화번호
        r'\d{6}-\d{7}',                 # 주민번호
        r'[가-힣]{2,4}\s*\d+동',          # 상세 주소 일부
        r'\d{4}-\d{4}-\d{4}-\d{4}',     # 카드번호 형태
    ]
    return any(re.search(pattern, text) for pattern in patterns)

def _get_positive_ending() -> str:
    """긍정적 마무리 멘트"""
    endings = [
        "함께 멋진 결혼식을 만들어가요!",
        "하나씩 차근차근 준비하면 됩니다.",
        "걱정 마세요, 제가 도와드릴게요!",
        "천천히 하나씩 정리해나가면 괜찮을 거예요.",
        "완벽한 결혼식을 위해 차근차근 진행해봐요.",
    ]
    return random.choice(endings)

def _looks_non_wedding(text: str) -> bool:
    """웨딩 관련 키워드 확장 + 부정 표현도 고려"""
    if not text:
        return False
    t = text.lower()
    wedding_hints = [
        "웨딩","결혼","예식","스드메","홀","드레스","메이크업","스튜디오",
        "청첩장","하객","본식","스냅","신부","신랑","혼수","예물","반지",
        "부케","턱시도","예단","폐백","신혼여행","허니문","예비부부",
    ]
    negative_patterns = ["안 해","하지 않","싫어","필요없","관심없"]
    has_negative = any(neg in t for neg in negative_patterns)
    has_wedding = any(hint in t for hint in wedding_hints)
    if has_wedding and has_negative:
        return True
    return not has_wedding

def _llm_smalltalk(user_text: str) -> str:
    """웨딩과 무관한 메시지 → 짧은 공감 후 웨딩 주제로 연결"""
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.prompts import ChatPromptTemplate
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("no key")
        sys = (
            "너는 친근한 웨딩 플래너 AI 마리야. "
            "사용자의 메시지에 1-2문장으로 공감하고, "
            "마지막에 자연스럽게 웨딩 준비 제안을 곁들여라. "
            "과도한 이모지/감탄사 금지."
        )
        prompt = ChatPromptTemplate.from_messages([("system", sys), ("user", "{u}")])
        llm = ChatOpenAI(model=os.getenv("LLM_MODEL", "gpt-4o"), temperature=float(os.getenv("LLM_TEMPERATURE", "0.2")))
        out = (prompt | llm).invoke({"u": user_text})
        content = getattr(out, "content", "").strip()
        return content or "그렇군요! 그런데 혹시 웨딩 준비는 어떻게 진행되고 있나요?"
    except Exception:
        return "그렇군요! 그런데 혹시 웨딩 준비는 어떻게 진행되고 있나요?"

def general_response_node(state: State) -> State:
    """
    웨딩과 관련없는 메세지가 들어오면 일반적인 대화를 생성해서 응답합니다.
    웨딩 관련일 경우엔 부족한 정보(카테고리/지역/개수)를 가볍게 유도합니다.
    + 스트레스 감지, 예산 현실성 체크, 개인정보 보호 포함
    """
    try:
        # suggestions와 quick_replies 초기화
        state["suggestions"] = []
        state["quick_replies"] = []

        # 0) 개인정보 보호
        if _contains_personal_info(state.get("user_input") or ""):
            state["answer"] = (
                "개인정보는 입력하지 말아주세요. 지역명이나 대략적인 예산 정도만 알려주시면 됩니다."
            )
            current_quick_replies = state.get("quick_replies", [])
            state["quick_replies"] = current_quick_replies + _quick_replies_for_category()
            return state

        # 1) 스트레스 신호
        if _detect_stress_signals(state.get("user_input") or ""):
            state["answer"] = (
                "결혼 준비가 생각보다 복잡하고 힘드시죠. "
                "천천히 하나씩 정리해나가면 괜찮을 거예요. 어떤 부분이 가장 막막하신가요?"
            )
            current_suggestions = state.get("suggestions", [])
            state["suggestions"] = current_suggestions + [
                "전체적인 준비 순서가 궁금해요",
                "예산 계획을 어떻게 세워야 할까요",
                "우선순위를 정하고 싶어요",
            ]
            current_quick_replies = state.get("quick_replies", [])
            state["quick_replies"] = current_quick_replies + _quick_replies_for_category()
            return state

        # 2) 인사말
        user_input_lower = (state.get("user_input") or "").lower().strip()
        if user_input_lower in ["", "안녕", "시작", "hello", "hi", "안녕하세요"]:
            state["answer"] = (
                "안녕하세요! 웨딩 준비를 도와드릴 마리예요.\n어떤 준비를 시작해볼까요?"
            )
            current_suggestions = state.get("suggestions", [])
            state["suggestions"] = current_suggestions + [
                "강남 웨딩홀 5곳 보여줘",
                "전지역 스튜디오 추천",
                "드레스 예산 200만원 이하",
                "메이크업 상위 5곳",
            ]
            current_quick_replies = state.get("quick_replies", [])
            state["quick_replies"] = current_quick_replies + _quick_replies_for_category()
            return state

        # 3) 비웨딩 대화
        if _looks_non_wedding(user_input_lower):
            smalltalk = _llm_smalltalk(state.get("user_input") or "")
            ctx = _format_known_context(state)
            tail = ("\n\n현재 인지된 정보: " + ctx) if ctx else ""
            state["answer"] = smalltalk + tail + f"\n\n{_get_positive_ending()}"
            current_suggestions = state.get("suggestions", [])
            state["suggestions"] = current_suggestions + [
                "강남 웨딩홀 5곳 보여줘",
                "스튜디오 촬영 견적 알려줘",
                "예산 300만원 기준으로 추천",
            ]
            current_quick_replies = state.get("quick_replies", [])
            state["quick_replies"] = current_quick_replies + _quick_replies_for_category()
            return state

        # 4) 웨딩인데 카테고리 없음
        if not state.get("vendor_type"):
            ctx = _format_known_context(state)
            intro = "원하시는 준비 항목을 선택해 주세요."
            tip = '예: "강남 웨딩홀 5곳", "드레스 예산 200만원 이하"'  # ← 따옴표 수정
            msg = (("현재 인지된 정보: " + ctx + "\n\n") if ctx else "") + intro + f"\n{tip}"
            state["answer"] = msg.strip() + f"\n\n{_get_positive_ending()}"
            current_suggestions = state.get("suggestions", [])
            state["suggestions"] = current_suggestions + [
                "강남 웨딩홀 5곳 보여줘",
                "전지역 스튜디오 5곳",
                "드레스 200만원 이하",
                "메이크업 상위 5곳",
            ]
            current_quick_replies = state.get("quick_replies", [])
            state["quick_replies"] = current_quick_replies + _quick_replies_for_category()
            return state

        # 5) 카테고리는 있고 지역 없음
        ty_label = VENDOR_LABEL.get(state.get("vendor_type"), state.get("vendor_type"))
        if not state.get("region_keyword"):
            ctx = _format_known_context(state)
            ask = f"{ty_label}을(를) 찾아볼게요! 선호 지역이 있으신가요?"
            tip = "예: 강남, 청담, 홍대, 전지역"
            budget_warning = ""
            if isinstance(state.get("total_budget_manwon"), int):
                bw = _budget_reality_check(state["total_budget_manwon"], state.get("vendor_type"))
                if bw:
                    budget_warning = f"\n\n💡 {bw}"
            msg = (("현재 인지된 정보: " + ctx + "\n\n") if ctx else "") + ask + f"\n{tip}" + budget_warning
            state["answer"] = msg.strip() + f"\n\n{_get_positive_ending()}"
            current_suggestions = state.get("suggestions", [])
            state["suggestions"] = current_suggestions + [
                f"강남 {ty_label} 상위 {_clamp_limit(state.get('limit'))}곳",
                f"전지역 {ty_label} 추천",
                "예산 범위를 지정해서 보여줘",
            ]
            current_quick_replies = state.get("quick_replies", [])
            state["quick_replies"] = current_quick_replies + _quick_replies_for_region()
            return state

        # 6) 카테고리/지역 모두 있음 → 실행 전 확인
        ctx = _format_known_context(state)
        limit = _clamp_limit(state.get("limit"))
        confirm = f"그럼 '{state.get('region_keyword')}' 지역 {ty_label} {limit}곳을 찾아볼게요."
        budget_warning = ""
        if isinstance(state.get("total_budget_manwon"), int):
            bw = _budget_reality_check(state["total_budget_manwon"], state.get("vendor_type"))
            if bw:
                budget_warning = f"\n\n💡 {bw}"
        msg = (("현재 인지된 정보: " + ctx + "\n\n") if ctx else "") + confirm + budget_warning
        state["answer"] = msg.strip() + f"\n\n{_get_positive_ending()}"
        current_suggestions = state.get("suggestions", [])
        state["suggestions"] = current_suggestions + [
            "가격 상한을 정해 필터링해줘",
            "비슷한 가격대 더 보여줘",
            "다른 지역으로도 보여줘",
        ]
        current_quick_replies = state.get("quick_replies", [])
        state["quick_replies"] = current_quick_replies + _quick_replies_for_limits(limit)
        return state

    except Exception as e:
        state["status"] = "error"
        state["answer"] = "일반 응답을 정리하는 중 문제가 생겼어요. 간단히 다시 요청해 주세요."
        state["reason"] = (state.get("reason") or "") + f" [general_response: {e}]"
        return state

# 개발용 테스트
if __name__ == "__main__":
    from state_mvp import State
    cases = [
        ("오늘 날씨가 좋네요", "일반 대화"),
        ("결혼 준비가 너무 힘들어요", "스트레스 감지"),
        ("010-1234-5678로 연락주세요", "개인정보 보호"),
        ("웨딩홀 50만원으로 찾아주세요", "예산 현실성"),
        ("결혼 하기 싫어요", "부정적 웨딩 메시지"),
    ]
    for user_input, name in cases:
        st = State()
        st["user_input"] = user_input
        out = general_response_node(st)
        print(f"✅ {name}: {out.get('answer', '')[:80]}...")
        print("---")