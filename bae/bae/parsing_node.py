# 목적: LLM이 사용자 입력을 구조화(JSON)로 파싱 → State에 반영
import os
import json
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from state_mvp import State, memo_set_budget, memo_set_wedding_date, ensure_user_id
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

# 환경변수 로드
load_dotenv()

# ---- LLM 초기화 (심플 & 재사용) ----
def _llm() -> ChatOpenAI:
    return ChatOpenAI(model=os.getenv("LLM_MODEL", "gpt-4o"), temperature=0)

# ---- 대화 맥락 포함 파서 프롬프트 ----
SYSTEM = """You are a wedding-planner data extractor.
Return ONLY a valid JSON object with the fields below. No comments, no extra text.

You can see previous conversation context to better understand the current request.
If the current message refers to previous information (like "더 저렴한 곳", "다른 지역", "그런 업체"), 
use the conversation context to maintain continuity.

Normalization rules:
- budget_manwon: integer in 만원 unit. Examples: "132만원" -> 132, "1,320,000원" -> 132, "1.5백만원" -> 150.
- wedding_date: ISO date "YYYY-MM-DD" if present; else null.
- vendor_type: one of ["wedding_hall","studio","wedding_dress","makeup"] or null.
- region_keyword: short location keyword (e.g., "강남","청담") or null.
- limit: integer 1..20 (default 5 if not specified).
- intent_hint: one of ["recommend","tool","general"] (pick what best matches the request).

Output schema (keys must exist):
{{
  "vendor_type": "string or null",
  "region_keyword": "string or null", 
  "limit": "integer",
  "intent_hint": "recommend or tool or general",
  "budget_manwon": "integer or null",
  "wedding_date": "string or null",
  "reason": "string - short reasoning in Korean (1 sentence max)"
}}
"""

USER_TMPL = """이전 대화 맥락:
{conversation_context}

현재 사용자 메시지:
{user_text}

메모된 정보:
- 총 예산: {current_budget}만원
- 결혼 날짜: {wedding_date}
- 이전 검색: {previous_searches}
"""

# 프롬프트 재정의 (대화 맥락 포함)
PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM),
        ("user", USER_TMPL),
    ]
)

def _latest_user_text(state: State) -> Optional[str]:
    """State에서 가장 최신 user 텍스트를 추출(있으면 user_input 우선)."""
    if state.get("user_input") and state["user_input"].strip():
        return state["user_input"].strip()
    
    msgs = state.get("messages", None)
    if not msgs:
        return None
    
    for m in reversed(msgs):
        content = getattr(m, "content", None)
        role = getattr(m, "type", None) or getattr(m, "role", None)
        if isinstance(content, str) and (role in (None, "human", "user")):
            return content.strip()
    return None

def _get_conversation_context(state: State) -> str:
    """대화 맥락을 문자열로 가져오기"""
    return state.get("recent_conversation_context", "첫 대화")

def _get_previous_searches(state: State) -> str:
    """이전 검색 정보 요약"""
    user_memo = state.get("user_memo")
    if not user_memo:
        return "없음"
    
    profile = user_memo.get("profile", {})
    locations = profile.get("preferred_locations", [])
    if locations:
        return f"선호 지역: {', '.join(locations)}"
    return "없음"

def _safe_parse_json(raw: str) -> Optional[Dict[str, Any]]:
    """LLM 응답에서 JSON 추출 (마크다운 코드블록 등 처리)"""
    # 1. 마크다운 코드블록 제거
    if "```json" in raw:
        start = raw.find("```json") + 7
        end = raw.find("```", start)
        if end != -1:
            raw = raw[start:end].strip()
    elif "```" in raw:
        # json 키워드 없어도 코드블록일 수 있음
        start = raw.find("```") + 3
        end = raw.find("```", start)
        if end != -1:
            raw = raw[start:end].strip()
    
    # 2. JSON 파싱
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None

def _coerce_int(v: Any, default: int = 5) -> int:
    try:
        iv = int(v)
        return min(max(iv, 1), 20)
    except Exception:
        return default

def parsing_node(state: State) -> State:
    """
    사용자에게 입력받은 메시지를 LLM으로 파싱하고 State를 채웁니다.
    - 대화 맥락과 메모된 정보를 함께 고려하여 파싱
    - LLM이 의도를 판단하여 JSON 반환
    - 반환된 budget/wedding_date는 메모에 동기화(만원/ISO)
    """
    # user_id 보장
    ensure_user_id(state)
    
    text = _latest_user_text(state)
    if not text:
        state["status"] = "empty"
        state["reason"] = "입력 텍스트 없음"
        return state

    try:
        # 대화 맥락 및 메모 정보 준비
        conversation_context = _get_conversation_context(state)
        current_budget = state.get("total_budget_manwon") or "없음"
        wedding_date = state.get("wedding_date") or "없음"
        previous_searches = _get_previous_searches(state)
        
        # 파라미터 구성
        invoke_params = {
            "user_text": text,
            "conversation_context": conversation_context,
            "current_budget": current_budget,
            "wedding_date": wedding_date,
            "previous_searches": previous_searches
        }
        
        print(f"🔍 DEBUG - Input text: {text[:50]}...")
        print(f"🔍 DEBUG - Conversation context: {conversation_context[:100]}...")
        
        chain = PROMPT | _llm()
        resp = chain.invoke(invoke_params)
        raw = resp.content if hasattr(resp, "content") else str(resp)
        
        print(f"🤖 LLM Response: {raw[:100]}...")
        
        # JSON 파싱 안전성 강화
        data = _safe_parse_json(raw)
        if data is None:
            state["status"] = "error"
            state["reason"] = f"LLM JSON 파싱 실패: {raw[:100]}..."
            return state

        # 1) 주요 필드 반영 (없으면 기본값 채우기)
        state["vendor_type"] = data.get("vendor_type") or None
        state["region_keyword"] = data.get("region_keyword") or None
        state["limit"] = _coerce_int(data.get("limit"), default=state.get("limit") or 5)
        state["intent_hint"] = data.get("intent_hint") or None

        # 2) 부가정보 → 메모 동기화(만원/ISO)
        budget = data.get("budget_manwon", None)
        if budget is not None:
            memo_set_budget(state, int(budget))

        wdate = data.get("wedding_date", None)
        if wdate:
            memo_set_wedding_date(state, str(wdate))

        # 3) 상태/디버깅
        state["status"] = "ok"
        why = data.get("reason") or ""
        state["reason"] = None
        state["response_content"] = (
            f"[parsing] vendor={state.get('vendor_type')}, region={state.get('region_keyword')}, "
            f"limit={state.get('limit')}, intent={state.get('intent_hint')}, "
            f"budget(manwon)={state.get('total_budget_manwon')}, date={state.get('wedding_date')} | {why}"
        )
        
        print(f"✅ Parsing successful: {state['response_content']}")
        return state

    except Exception as e:
        # LLM 실패하거나 JSON 파싱 실패 시 안전하게 종료
        state["status"] = "error"
        state["reason"] = f"parsing_node 실패: {e}"
        print(f"❌ Parsing failed: {e}")
        return state