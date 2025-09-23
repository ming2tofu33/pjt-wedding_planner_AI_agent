# graph.py
"""
LangGraph 기반 AI 웨딩플래너 에이전트의 그래프 구조
- 중복 엣지 제거
- 논리적이고 명확한 플로우
- conditional_edges만 사용하여 깔끔한 구조
"""
from dotenv import load_dotenv
import os
from typing import List, Dict, Any, Optional
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


# ============= 라우팅 함수들 =============

def route_from_parsing(state: State) -> str:
    """parsing 노드에서 다음 노드 결정"""
    if state.get('status') == 'error':
        return "error_handler"
    return "memo_check"

def route_from_memo_check(state: State) -> str:
    """memo_check 노드에서 다음 노드 결정"""
    if state.get('status') == 'error':
        return "error_handler" 
    return "router"

def route_from_router(state: State) -> str:
    """router 노드에서 다음 노드 결정"""
    if state.get('status') == 'error':
        return "error_handler"
    
    routing_decision = state.get('routing_decision')
    
    # routing_decision에 따른 분기
    if routing_decision == "tool_execution":
        return "tool_execution"
    elif routing_decision == "recommendation": 
        return "recommendation"
    elif routing_decision == "general_response":
        return "response_generation"
    elif routing_decision == "error_handler":
        return "error_handler"
    else:
        # 기본값: 일반 응답 생성
        return "response_generation"

def route_from_recommendation(state: State) -> str:
    """recommendation 노드에서 다음 노드 결정"""
    if state.get('status') == 'error':
        return "error_handler"
    return "tool_execution"

def route_from_tool_execution(state: State) -> str:
    """tool_execution 노드에서 다음 노드 결정"""
    if state.get('status') == 'error':
        return "error_handler"
    return "memo_update"

def route_from_memo_update(state: State) -> str:
    """memo_update 노드에서 다음 노드 결정"""
    if state.get('status') == 'error':
        return "error_handler"
    return "response_generation"

def route_from_response_generation(state: State) -> str:
    """response_generation 노드에서 다음 노드 결정"""
    if state.get('status') == 'error':
        return "error_handler"
    return END

def route_from_error_handler(state: State) -> str:
    """error_handler 노드에서 항상 END로"""
    return END

# ============= 그래프 구성 =============

def create_wedding_planner_graph() -> StateGraph:
    """웨딩플래너 그래프 생성 함수"""
    
    # StateGraph 객체 생성
    builder = StateGraph(State)
    
    # ===== 1. 노드 추가 =====
    builder.add_node("parsing", parsing_node)
    builder.add_node("memo_check", memo_check_node)
    builder.add_node("router", conditional_router)
    builder.add_node("recommendation", recommendation_node)
    builder.add_node("tool_execution", tool_execution_node)
    builder.add_node("memo_update", memo_update_node)
    builder.add_node("response_generation", response_generation_node)
    builder.add_node("error_handler", error_handler_node)
    
    # ===== 2. 진입점 설정 =====
    builder.add_edge(START, "parsing")
    
    # ===== 3. 조건부 라우팅 설정 (중복 없는 깔끔한 구조) =====
    
    # parsing → memo_check or error_handler
    builder.add_conditional_edges(
        "parsing",
        route_from_parsing,
        {
            "memo_check": "memo_check",
            "error_handler": "error_handler"
        }
    )
    
    # memo_check → router or error_handler  
    builder.add_conditional_edges(
        "memo_check",
        route_from_memo_check,
        {
            "router": "router",
            "error_handler": "error_handler"
        }
    )
    
    # router → tool_execution/recommendation/response_generation/error_handler
    builder.add_conditional_edges(
        "router",
        route_from_router,
        {
            "tool_execution": "tool_execution",
            "recommendation": "recommendation", 
            "response_generation": "response_generation",
            "error_handler": "error_handler"
        }
    )
    
    # recommendation → tool_execution or error_handler
    builder.add_conditional_edges(
        "recommendation",
        route_from_recommendation,
        {
            "tool_execution": "tool_execution",
            "error_handler": "error_handler"
        }
    )
    
    # tool_execution → memo_update or error_handler
    builder.add_conditional_edges(
        "tool_execution", 
        route_from_tool_execution,
        {
            "memo_update": "memo_update",
            "error_handler": "error_handler"
        }
    )
    
    # memo_update → response_generation or error_handler
    builder.add_conditional_edges(
        "memo_update",
        route_from_memo_update,
        {
            "response_generation": "response_generation",
            "error_handler": "error_handler"
        }
    )
    
    # response_generation → END or error_handler
    builder.add_conditional_edges(
        "response_generation",
        route_from_response_generation,
        {
            "error_handler": "error_handler",
            END: END
        }
    )
    
    # error_handler → END (항상)
    builder.add_conditional_edges(
        "error_handler",
        route_from_error_handler,
        {
            END: END
        }
    )
    
    return builder

# ============= 메인 그래프 객체 =============

# 그래프 생성 및 컴파일
builder = create_wedding_planner_graph()
app = builder.compile()

# ============= 그래프 검증 함수 =============

def validate_graph_structure() -> Dict[str, Any]:
    """그래프 구조의 유효성을 검사하는 함수"""
    try:
        # 그래프 노드 목록 확인
        graph_dict = app.get_graph().to_json()
        nodes = [node["id"] for node in graph_dict.get("nodes", [])]
        edges = [(edge["source"], edge["target"]) for edge in graph_dict.get("edges", [])]
        
        expected_nodes = [
            "parsing", "memo_check", "router", "recommendation", 
            "tool_execution", "memo_update", "response_generation", "error_handler"
        ]
        
        validation_result = {
            "valid": True,
            "nodes_present": nodes,
            "expected_nodes": expected_nodes,
            "missing_nodes": [node for node in expected_nodes if node not in nodes],
            "extra_nodes": [node for node in nodes if node not in expected_nodes],
            "total_edges": len(edges),
            "has_start_edge": any(edge[0] == "__start__" for edge in edges),
            "has_end_edge": any(edge[1] == "__end__" for edge in edges)
        }
        
        if validation_result["missing_nodes"] or not validation_result["has_start_edge"]:
            validation_result["valid"] = False
            
        return validation_result
        
    except Exception as e:
        return {
            "valid": False,
            "error": str(e),
            "nodes_present": [],
            "expected_nodes": expected_nodes,
            "missing_nodes": expected_nodes,
            "extra_nodes": []
        }

def get_graph_flow_summary() -> Dict[str, List[str]]:
    """그래프의 플로우를 요약해서 반환"""
    return {
        "main_flow": [
            "START → parsing",
            "parsing → memo_check", 
            "memo_check → router",
            "router → [tool_execution|recommendation|response_generation]",
            "recommendation → tool_execution",
            "tool_execution → memo_update",
            "memo_update → response_generation", 
            "response_generation → END"
        ],
        "error_flow": [
            "Any node with error → error_handler",
            "error_handler → END"
        ],
        "decision_points": [
            "parsing: status check",
            "memo_check: status check", 
            "router: routing_decision",
            "recommendation: status check",
            "tool_execution: status check",
            "memo_update: status check",
            "response_generation: status check"
        ]
    }

# ============= 개발/디버깅용 코드 =============

if __name__ == "__main__":
    from langgraph.graph import MermaidDrawMethod
    
    print("🎯 LangGraph 웨딩플래너 에이전트")
    print("=" * 50)
    
    # 그래프 구조 검증
    validation = validate_graph_structure()
    if validation["valid"]:
        print("✅ 그래프 구조 검증 성공!")
        print(f"📊 총 {len(validation['nodes_present'])} 개 노드, {validation['total_edges']} 개 엣지")
    else:
        print("❌ 그래프 구조 검증 실패!")
        if validation.get("missing_nodes"):
            print(f"   누락된 노드: {validation['missing_nodes']}")
        if validation.get("error"):
            print(f"   에러: {validation['error']}")
    
    # 플로우 요약 출력
    print("\n📋 그래프 플로우 요약:")
    flow_summary = get_graph_flow_summary()
    
    print("\n🔄 메인 플로우:")
    for step in flow_summary["main_flow"]:
        print(f"   {step}")
    
    print("\n🚨 에러 플로우:")
    for step in flow_summary["error_flow"]:
        print(f"   {step}")
    
    print("\n🤔 결정 포인트:")
    for decision in flow_summary["decision_points"]:
        print(f"   {decision}")
    
    # Mermaid 다이어그램 생성
    try:
        print("\n🎨 Mermaid 다이어그램:")
        mermaid = app.get_graph(draw_method=MermaidDrawMethod(node_representation="basic")).draw_mermaid()
        print(mermaid)
    except Exception as e:
        print(f"⚠️ Mermaid 다이어그램 생성 실패: {e}")
    
    # PNG 이미지 저장 시도
    try:
        app.get_graph().draw_png("wedding_planner_graph_clean.png")
        print("\n💾 그래프 이미지가 'wedding_planner_graph_clean.png'로 저장되었습니다.")
    except ImportError:
        print("\n⚠️ graphviz 라이브러리가 설치되지 않아 이미지로 저장할 수 없습니다.")
        print("   설치 방법: pip install pygraphviz graphviz")
    except Exception as e:
        print(f"\n⚠️ 이미지 저장 실패: {e}")
    
    print("\n🚀 그래프 준비 완료! 'langgraph dev' 명령으로 실행하세요.")