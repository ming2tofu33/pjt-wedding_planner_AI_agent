from state_mvp import State

def conditional_router(state: State) -> State:
    """
    파싱/메모 결과를 바탕으로 다음 실행 노드를 결정하고(상태 변경),
    필요 시 tools_to_execute에 db_query_tool을 계획에 추가한다.
    """
    # 0) 에러 가드 (에러만 일반응답으로 보냄)
    if state.get("status") == "error":
        state["routing_decision"] = "general_response"
        state["reason"] = (state.get("reason") or "") + " [router: error guard]"
        return state

    # 방어적 초기화
    if not isinstance(state.get("tools_to_execute"), list):
        state["tools_to_execute"] = []

    hint = (state.get("intent_hint") or "").lower()
    vendor = state.get("vendor_type")

    # 1) intent가 general로 명시되면 일반 응답
    if hint == "general":
        state["routing_decision"] = "general_response"
        state["reason"] = "[router] general_response by intent=general"
        return state

    # 2) 힌트가 tool/recommend 이거나, 힌트가 없어도 vendor_type이 있으면 -> tool_execution
    if hint in ("tool", "recommend") or vendor:
        if vendor:
            state["routing_decision"] = "tool_execution"
            if "db_query_tool" not in state["tools_to_execute"]:
                state["tools_to_execute"] = state["tools_to_execute"] + ["db_query_tool"]
            state["reason"] = f"[router] tool_execution: vendor={vendor}, region={state.get('region_keyword')}"
            return state
        else:
            # vendor가 없으면 일반응답으로 폴백
            state["routing_decision"] = "general_response"
            state["reason"] = "[router] general_response (missing vendor_type)"
            return state

    # 3) 폴백: 명확한 힌트 없음 → 일반 응답
    state["routing_decision"] = "general_response"
    state["reason"] = "[router] fallback to general (no clear hint)"
    return state
