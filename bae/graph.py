from langgraph.graph import START, END, StateGraph
from state import State
from nodes import (
    parsing_node,
    tool_execution_node,
    memo_update_node,
    response_generation_node,
    general_response_node
)
from routers import conditional_router


# StateGraph 빌더 생성
builder = StateGraph(State)

# 노드 추가
builder.add_node("parsing_node", parsing_node)
builder.add_node("tool_execution_node", tool_execution_node)
builder.add_node("memo_update_node", memo_update_node)
builder.add_node("response_generation_node", response_generation_node)
builder.add_node("general_response_node", general_response_node)

# 시작점 연결
builder.add_edge(START, "parsing_node")

# parsing_node에서 conditional_router로 분기
builder.add_conditional_edges(
    "parsing_node",
    conditional_router,
    {
        "tool_execution": "tool_execution_node",
        "general_response": "general_response_node"
    }
)

# 툴 실행 플로우
builder.add_edge("tool_execution_node", "memo_update_node")
builder.add_edge("memo_update_node", "response_generation_node")
builder.add_edge("response_generation_node", END)

# 일반 응답 플로우
builder.add_edge("general_response_node", END)

# 그래프 컴파일
app = builder.compile()

# 디버깅용 - 그래프 구조 확인
if __name__ == "__main__":
    print("웨딩 챗봇 그래프가 성공적으로 생성되었습니다!")
    print("사용 가능한 노드들:")
    for node in app.get_graph().nodes:
        print(f"- {node}")