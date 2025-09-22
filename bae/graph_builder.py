# graph_builder.py (PATCH: minimal changes)

from langgraph.graph import START, END, StateGraph
from state_mvp import State
from parsing_node import parsing_node
from memo_check_node import memo_check_node
from conditional_router import conditional_router
from tool_execution_node import tool_execution_node
from general_response_node import general_response_node
from memo_update_node import memo_update_node
from response_generation_node import response_generation_node
from error_handler_node import error_handler_node

# 라우팅 함수들
def _after_parsing(state: State) -> str:
    return "error_handler_node" if state.get("status") == "error" else "memo_check_node"

def _after_memo_check(state: State) -> str:
    return "error_handler_node" if state.get("status") == "error" else "conditional_router"

def _route_from_router(state: State) -> str:
    if state.get("status") == "error":
        return "error_handler_node"
    d = state.get("routing_decision") or "general_response"
    if d == "tool_execution":
        return "tool_execution_node"
    return "general_response_node"

def _after_tool_exec(state: State) -> str:
    return "error_handler_node" if state.get("status") == "error" else "memo_update_node"

def _after_general(state: State) -> str:
    return "error_handler_node" if state.get("status") == "error" else "response_generation_node"

def _after_memo_update(state: State) -> str:
    return "error_handler_node" if state.get("status") == "error" else "response_generation_node"

# ===== CHANGED: END 객체가 아니라 "__end__" 문자열을 반환해야 매핑이 맞습니다.
def _after_response_generation(state: State) -> str:
    return "error_handler_node" if state.get("status") == "error" else "__end__"

# ===== CHANGED: 동일하게 "__end__" 문자열 반환
def _after_error(state: State) -> str:
    return "__end__"

# 그래프 빌드
builder = StateGraph(State)

# 노드 등록
builder.add_node("parsing_node", parsing_node)
builder.add_node("memo_check_node", memo_check_node)
builder.add_node("conditional_router", conditional_router)
builder.add_node("tool_execution_node", tool_execution_node)
builder.add_node("general_response_node", general_response_node)
builder.add_node("memo_update_node", memo_update_node)
builder.add_node("response_generation_node", response_generation_node)
builder.add_node("error_handler_node", error_handler_node)

# 엣지 연결
builder.add_edge(START, "parsing_node")

builder.add_conditional_edges("parsing_node", _after_parsing, {
    "memo_check_node": "memo_check_node",
    "error_handler_node": "error_handler_node",
})

builder.add_conditional_edges("memo_check_node", _after_memo_check, {
    "conditional_router": "conditional_router",
    "error_handler_node": "error_handler_node",
})

builder.add_conditional_edges("conditional_router", _route_from_router, {
    "tool_execution_node": "tool_execution_node",
    "general_response_node": "general_response_node",
    "error_handler_node": "error_handler_node",
})

builder.add_conditional_edges("tool_execution_node", _after_tool_exec, {
    "memo_update_node": "memo_update_node",
    "error_handler_node": "error_handler_node",
})

builder.add_conditional_edges("general_response_node", _after_general, {
    "response_generation_node": "response_generation_node",
    "error_handler_node": "error_handler_node",
})

builder.add_conditional_edges("memo_update_node", _after_memo_update, {
    "response_generation_node": "response_generation_node",
    "error_handler_node": "error_handler_node",
})

builder.add_conditional_edges("response_generation_node", _after_response_generation, {
    "error_handler_node": "error_handler_node",
    "__end__": END,
})

builder.add_conditional_edges("error_handler_node", _after_error, {
    "__end__": END,
})

# 컴파일
app = builder.compile()

# 테스트용
if __name__ == "__main__":
    from pprint import pprint
    result = app.invoke({
        "user_input": "압구정 웨딩홀 3곳 추천해줘. 예산은 5000만원!",
        "status": "ok"
    })
    print("\n=== FINAL ANSWER ===")  # <= 추가: 최종 답변 바로 확인
    print(result.get("answer"))
    print("\n=== STATE SNAPSHOT ===")
    pprint(result)