# graph.py
# LangGraph를 직접 구성하고 컴파일하여 'app' 변수에 할당합니다.

from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.base import BaseCheckpointSaver

from state import State
from nodes import (
    parsing_node, 
    memo_check_node, 
    conditional_router, 
    tool_execution_node,
    memo_update_node,
    response_generation_node,
    recommendation_node,
    error_handler_node
)

# LangGraph builder 객체 생성
builder = StateGraph(State)

# 노드 추가
builder.add_node("parsing", parsing_node)
builder.add_node("memo_check", memo_check_node)
builder.add_node("router", conditional_router)
builder.add_node("tool_execution", tool_execution_node)
builder.add_node("memo_update", memo_update_node)
builder.add_node("response_generation", response_generation_node)
builder.add_node("recommendation", recommendation_node)
builder.add_node("error_handler", error_handler_node)

# 엣지(흐름) 정의
# 시작점(START)에서 첫 노드로
builder.add_edge(START, "parsing")

# 정상적인 처리 흐름
builder.add_edge("parsing", "memo_check")
builder.add_edge("memo_check", "router")
builder.add_edge("recommendation", "tool_execution")
builder.add_edge("tool_execution", "memo_update")
builder.add_edge("memo_update", 'response_generation')
# 라우터에서 'general_response'로 결정되면 바로 'response_generation'으로
builder.add_edge("router", 'response_generation')
# 최종 응답이 생성되면 END로
builder.add_edge("response_generation", END)
# 에러 핸들러에서 최종 응답이 생성되면 END로
builder.add_edge("error_handler", END)

# 조건부 라우팅
builder.add_conditional_edges(
    "router",
    lambda state: state['routing_decision'],
    {
        "tool_execution": "tool_execution",
        "general_response": "response_generation",
        "recommendation": "recommendation",
        "error_handler": "error_handler"
    }
)

# 각 노드에서 오류 발생 시 'error_handler' 노드로 연결
# 'ok' 상태가 아니면 무조건 에러 핸들러로
builder.add_conditional_edges(
    "parsing", 
    lambda state: "error_handler" if state.get("status") == "error" else "memo_check"
)
builder.add_conditional_edges(
    "memo_check", 
    lambda state: "error_handler" if state.get("status") == "error" else "router"
)
builder.add_conditional_edges(
    "tool_execution", 
    lambda state: "error_handler" if state.get("status") == "error" else "memo_update"
)
builder.add_conditional_edges(
    "memo_update", 
    lambda state: "error_handler" if state.get("status") == "error" else "response_generation"
)
builder.add_conditional_edges(
    "response_generation", 
    lambda state: "error_handler" if state.get("status") == "error" else END
)

# 컴파일된 그래프를 'app' 변수에 할당
app = builder.compile()

# 로컬 테스트용 코드 블록
if __name__ == "__main__":
    from langgraph.graph import MermaidDrawMethod
    
    # Mermaid 다이어그램 생성 (터미널 출력용)
    print("\n✅ LangGraph 구조 (Mermaid 다이어그램):")
    print(app.get_graph(draw_method=MermaidDrawMethod(node_representation="basic")).draw_mermaid_ir())

    # PNG 이미지로 저장 (graphviz 필요)
    try:
        app.get_graph().draw_png("wedding_planner_graph.png")
        print("\n✅ 그래프 이미지가 'wedding_planner_graph.png'로 저장되었습니다.")
    except ImportError:
        print("\n⚠️ graphviz 라이브러리가 설치되지 않아 이미지로 저장할 수 없습니다.")
        print("   pip install pygraphviz graphviz 를 실행하거나,")
        print("   brew install graphviz (Mac) / sudo apt-get install graphviz (Ubuntu) 로 설치해주세요.")