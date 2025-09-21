# 목적: LLM이 사용자 입력을 구조화(JSON)로 파싱 → State에 반영

import os
import json
from typing import Optional, Dict, Any
from state_mvp import State, memo_set_budget, memo_set_wedding_date
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

# ---- LLM 초기화 (심플 & 재사용) ----
def _llm() -> ChatOpenAI:
    return ChatOpenAI(model=os.getenv("LLM_MODEL", "gpt-4o"), temperature=0)

# ---- 파서 프롬프트 (LLM 주도 파싱) ----
SYSTEM = """You are a wedding-planner data extractor.
Return ONLY a valid JSON object with the fields below. No comments, no extra text.

Normalization rules:
- budget_manwon: integer in 만원 unit. Examples: "132만원" -> 132, "1,320,000원" -> 132, "1.5백만원" -> 150.
- wedding_date: ISO date "YYYY-MM-DD" if present; else null.
- vendor_type: one of ["wedding_hall","studio","wedding_dress","makeup"] or null.
- region_keyword: short location keyword (e.g., "강남","청담") or null.
- limit: integer 1..20 (default 5 if not specified).
- intent_hint: one of ["recommend","tool","general"] (pick what best matches the request).

Output schema (keys must exist):
{
  "vendor_type": string|null,
  "region_keyword": string|null,
  "limit": integer,
  "intent_hint": "recommend"|"tool"|"general",
  "budget_manwon": integer|null,
  "wedding_date": string|null,
  "reason": string    // short reasoning in Korean (1 sentence max)
}
"""

USER_TMPL = """사용자 메시지:
{user_text}
"""

PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM),
        ("user", USER_TMPL),
    ]
)

def _latest_user_text(state: State) -> Optional[str]:
    """State에서 가장 최신 user 텍스트를 추출(있으면 user_input 우선)."""
    if state.user_input and state.user_input.strip():
        return state.user_input.strip()
    
    msgs = getattr(state, "messages", None)
    if not msgs:
        return None
    
    for m in reversed(msgs):
        content = getattr(m, "content", None)
        role = getattr(m, "type", None) or getattr(m, "role", None)
        if isinstance(content, str) and (role in (None, "human", "user")):
            return content.strip()
    return None

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
    - LLM이 의도를 판단하여 JSON 반환
    - 반환된 budget/wedding_date는 메모에 동기화(만원/ISO)
    """
    text = _latest_user_text(state)
    if not text:
        state.status = "empty"
        state.reason = "입력 텍스트 없음"
        return state

    try:
        chain = PROMPT | _llm()
        resp = chain.invoke({"user_text": text})
        raw = resp.content if hasattr(resp, "content") else str(resp)
        
        # JSON 파싱 안전성 강화
        data = _safe_parse_json(raw)
        if data is None:
            state.status = "error"
            state.reason = f"LLM JSON 파싱 실패: {raw[:100]}..."
            return state

        # 1) 주요 필드 반영 (없으면 기본값 채우기)
        state.vendor_type = data.get("vendor_type") or None
        state.region_keyword = data.get("region_keyword") or None
        state.limit = _coerce_int(data.get("limit"), default=state.limit or 5)
        state.intent_hint = data.get("intent_hint") or None

        # 2) 부가정보 → 메모 동기화(만원/ISO)
        budget = data.get("budget_manwon", None)
        if budget is not None:
            memo_set_budget(state, int(budget))

        wdate = data.get("wedding_date", None)
        if wdate:
            memo_set_wedding_date(state, str(wdate))

        # 3) 상태/디버깅
        state.status = "ok"
        why = data.get("reason") or ""
        state.reason = None
        state.response_content = (
            f"[parsing] vendor={state.vendor_type}, region={state.region_keyword}, "
            f"limit={state.limit}, intent={state.intent_hint}, "
            f"budget(manwon)={state.total_budget_manwon}, date={state.wedding_date} | {why}"
        )
        return state

    except Exception as e:
        # LLM 실패하거나 JSON 파싱 실패 시 안전하게 종료
        state.status = "error"
        state.reason = f"parsing_node 실패: {e}"
        return state