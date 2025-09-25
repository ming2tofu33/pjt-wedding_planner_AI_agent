from state import State

def conditional_router(state: State) -> str:
    """intent를 보고 라우팅 결정"""
    
    # 웨딩 관련이면 tool_execution으로, 아니면 general_response로
    if state.get("intent") == "wedding":
        return "tool_execution"
    else:
        return "general_response"