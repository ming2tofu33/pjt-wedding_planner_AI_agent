# 목적: 대화 요약을 갱신하고(user_memo.conversation_summary), 필요 시 메모 파일을 저장한다.
import json
import os
from typing import List, Tuple
from state_mvp import State

# ---- LLM 요약기능 ----
def llm_summarize(turns: List[Tuple[str, str]], prev_summary: str | None) -> str | None:
    """
    LLM이 사용 가능하면 최근 대화를 한국어로 짧게 요약.
    실패/미구현/환경 변수 없음 → None 반환하여 Fallback 사용.
    """
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.prompts import ChatPromptTemplate
    except Exception:
        return None

    if not os.getenv("OPENAI_API_KEY"):
        return None

    sys = (
        "너는 웨딩 챗봇의 기록 요약 도우미야. 다음 규칙을 지켜:\n"
        "- 한국어로 3문장 이내 요약\n"
        "- 예산(만원), 지역, 벤더타입, 날짜 등 핵심 파라미터는 가능한 포함\n"
        "- 불필요한 감탄/이모지는 제외"
    )
    user_lines = []
    if prev_summary:
        user_lines.append(f"[이전 요약]\n{prev_summary}\n")
    user_lines.append("[최근 대화]")
    for role, text in turns:
        user_lines.append(f"{role.upper()}: {text}")
    user_msg = "\n".join(user_lines)

    model = os.getenv("LLM_MODEL", "gpt-4o")
    try:
        temperature = float(os.getenv("LLM_TEMPERATURE", "0"))
    except ValueError:
        temperature = 0.0

    prompt = ChatPromptTemplate.from_messages([("system", sys), ("user", "{msg}")])
    llm = ChatOpenAI(model=model, temperature=temperature)
    try:
        out = (prompt | llm).invoke({"msg": user_msg})
        content = out.content if hasattr(out, "content") else str(out)
        content = (content or "").strip()
        return content or None
    except Exception:
        return None

# ---- Fallback 요약기 (LLM 실패 시) ----
def _fallback_summarize(turns: List[Tuple[str, str]], prev_summary: str | None) -> str:
    """
    최근 3~6턴 내에서 핵심을 간단히 엮어 한 문단으로 압축.
    """
    buf = []
    if prev_summary:
        buf.append(f"[이전] {prev_summary}")
    for role, text in turns[-6:]:
        text = " ".join(text.split())
        if len(text) > 120:
            text = text[:117] + "..."
        buf.append(f"{role[:1].upper()}: {text}")
    return " / ".join(buf) if buf else "(대화 없음)"

def _collect_recent_turns(state: State) -> List[Tuple[str, str]]:
    """
    MessagesState.messages에서 최근 user/assistant content만 뽑는다.
    state.user_input이 있으면 가장 마지막 user로 간주해 추가.
    """
    turns: List[Tuple[str, str]] = []

    msgs = state.get("messages", [])
    for m in msgs[-12:]:
        role = getattr(m, "type", None) or getattr(m, "role", None) or ""
        content = getattr(m, "content", None)
        if isinstance(content, str):
            if role in ("human", "user"):
                turns.append(("user", content))
            elif role in ("ai", "assistant"):
                turns.append(("assistant", content))

    if state.get("user_input") and (not turns or turns[-1][0] != "user"):
        turns.append(("user", state["user_input"]))

    return turns

def _save_json(path: str, data: dict) -> bool:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

def memo_update_node(state: State) -> State:
    """
    - 최근 대화 요약 → state.conversation_summary 및 user_memo.conversation_summary 갱신
    - last_input / last_query 간단 기록
    - state.memo_needs_update == True 이거나 요약/메타가 변경되면 파일 저장
    - 실패해도 흐름을 끊지 않음
    """
    try:
        if not state.get("user_memo"):
            current_response = state.get("response_content", "")
            state["response_content"] = current_response + " [memo_update: no memo]"
            return state

        recent = _collect_recent_turns(state)
        prev_summary = state["user_memo"].get("conversation_summary")

        # 1) 요약 생성 (LLM 우선, 실패 시 Fallback)
        new_summary = llm_summarize(recent, prev_summary) or _fallback_summarize(recent, prev_summary)
        state["conversation_summary"] = new_summary
        state["user_memo"]["conversation_summary"] = new_summary  # type: ignore[index]

        # 2) 가벼운 메타 기록(변경 시 저장 트리거 포함)
        meta_changed = False
        if state.get("user_input") and state["user_memo"].get("last_input") != state["user_input"]:  # type: ignore[index]
            state["user_memo"]["last_input"] = state["user_input"]  # type: ignore[index]
            meta_changed = True

        if any([state.get("vendor_type"), state.get("region_keyword"), state.get("limit")]):
            last_query_new = {
                "vendor_type": state.get("vendor_type"),
                "region_keyword": state.get("region_keyword"),
                "limit": state.get("limit"),
            }
            if state["user_memo"].get("last_query") != last_query_new:  # type: ignore[index]
                state["user_memo"]["last_query"] = last_query_new  # type: ignore[index]
                meta_changed = True

        # 3) 저장 필요 여부 판단
        need_save = state.get("memo_needs_update") or (new_summary != prev_summary) or meta_changed

        if need_save:
            path = state.get("memo_file_path")
            if path:
                ok = _save_json(path, state["user_memo"])  # type: ignore[arg-type]
                state["memo_needs_update"] = not ok
                if not ok:
                    state["status"] = "error"
                    current_reason = state.get("reason", "")
                    state["reason"] = current_reason + " [memo_update: save failed]"
            else:
                state["memo_needs_update"] = True
                current_reason = state.get("reason", "")
                state["reason"] = current_reason + " [memo_update: missing memo_file_path]"

        # 4) 로그 길이 관리
        current_response = state.get("response_content", "")
        if len(current_response) > 500:
            current_response = current_response[-500:]
        state["response_content"] = current_response + " [memo_update: done]"
        return state

    except Exception as e:
        state["status"] = "error"
        current_reason = state.get("reason", "")
        state["reason"] = current_reason + f" [memo_update: {e}]"
        return state