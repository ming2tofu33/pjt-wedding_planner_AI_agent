from state_mvp import State

def conditional_router(state: State) -> State:
    """
    파싱/메모 결과를 바탕으로 다음 실행 노드를 결정하고(상태 변경),
    필요 시 tools_to_execute에 db_query_tool을 계획에 추가한다.
    """
    # 0) 에러/빈입력 가드
    if state.status in ("error", "empty"):
        state.routing_decision = "general_response"
        state.reason = (state.reason or "") + " [router: status guard]"
        return state
    hint = (state.intent_hint or "").lower()
    # 1) general → 일반 응답
    if hint == "general":
        state.routing_decision = "general_response"
        state.reason = "[router] general_response by intent=general"
        return state
    # 2) tool / recommend(MVP에선 tool로 대체)
    if hint in ("tool", "recommend"):
        if state.vendor_type:
            state.routing_decision = "tool_execution"
            if "db_query_tool" not in state.tools_to_execute:
                state.tools_to_execute += ["db_query_tool"]
            state.reason = (
                f"[router] tool_execution: vendor={state.vendor_type}, region={state.region_keyword}"
            )
            return state
        else:
            state.routing_decision = "general_response"
            state.reason = "[router] general_response (missing vendor_type)"
            return state
    # 3) 폴백
    state.routing_decision = "general_response"
    state.reason = "[router] fallback to general (no clear hint)"
    return state
