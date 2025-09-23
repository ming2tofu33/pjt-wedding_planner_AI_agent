from langgraph.graph import START, END, StateGraph
from state import State
from nodes import (
    parsing_node, 
    memo_check_node,
    recommendation_node, 
    tool_execution_node, 
    general_response_node, 
    memo_update_node, 
    response_generation_node, 
    error_handler_node
)
from routers import conditional_router

from dotenv import load_dotenv

load_dotenv()

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
    if d == "recommendation":
        return "recommendation_node"
    return "general_response_node"

def _after_tool_exec(state: State) -> str:
    return "error_handler_node" if state.get("status") == "error" else "memo_update_node"

def _after_general(state: State) -> str:
    return "error_handler_node" if state.get("status") == "error" else "response_generation_node"

def _after_recommendation(state: State) -> str:
    return "error_handler_node" if state.get("status") == "error" else "memo_update_node"

def _after_memo_update(state: State) -> str:
    return "error_handler_node" if state.get("status") == "error" else "response_generation_node"

def _after_response_generation(state: State) -> str:
    return "error_handler_node" if state.get("status") == "error" else "__end__"

def _after_error(state: State) -> str:
    return "__end__"

# 그래프 빌드
builder = StateGraph(State)

# 노드 등록
builder.add_node("parsing_node", parsing_node)
builder.add_node("memo_check_node", memo_check_node)
builder.add_node("conditional_router", conditional_router)
builder.add_node("recommendation_node", recommendation_node)
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
    "recommendation_node": "recommendation_node",
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

builder.add_conditional_edges("recommendation_node", _after_recommendation, {
    "memo_update_node": "memo_update_node",
    "error_handler_node": "error_handler_node",
})

builder.add_conditional_edges("memo_update_node", _after_memo_update, {
    "response_generation_node": "response_generation_node",
    "error_handler_node": "error_handler_node",
})

builder.add_conditional_edges("response_generation_node", _after_response_generation, {
    "__end__": END,
    "error_handler_node": "error_handler_node",
})

builder.add_conditional_edges("error_handler_node", _after_error, {
    "__end__": END,
})

# 컴파일
app = builder.compile()