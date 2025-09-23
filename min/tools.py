# tools.py
"""
LangGraph 기반 웨딩플래너를 위한 도구들
- 새로운 tool_execution_node와 호환
- 표준화된 반환값 형식
- 강화된 에러 처리
"""

import os
import re
from typing import Dict, List, Any, Optional, Union
from typing_extensions import Annotated
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_community.utilities import SQLDatabase
from sqlalchemy import create_engine
from dotenv import load_dotenv

# sympy 임포트
from sympy import sympify, SympifyError
from sympy.core.numbers import Integer, Float, Number
from sympy.parsing.latex import parse_latex

# 사용자 정의 모듈 임포트
from db import db, engine, table_info
from state import State, memo_set_budget, memo_set_wedding_date, memo_set_guest_count

# 환경 변수 로드
load_dotenv()

# 웹 검색 도구 초기화
tavily_tool = TavilySearchResults(max_results=3)

# ============= 유틸리티 함수 =============

def _sanitize_input(text: str) -> str:
    """SQL 인젝션 방지를 위한 입력 정화"""
    return re.sub(r"[\"\';`]+", "", text)

def _format_success_response(data: Any, message: str = "") -> Dict[str, Any]:
    """성공 응답 표준 형식"""
    return {
        "success": True,
        "data": data,
        "message": message,
        "error": None
    }

def _format_error_response(error_msg: str, data: Any = None) -> Dict[str, Any]:
    """에러 응답 표준 형식"""
    return {
        "success": False,
        "data": data,
        "message": "",
        "error": error_msg
    }

# ============= 도구 함수들 =============

def web_search_tool(query: str) -> Dict[str, Any]:
    """
    웹 검색을 수행하는 도구
    
    Args:
        query (str): 검색 쿼리
        
    Returns:
        Dict[str, Any]: 표준화된 응답 형식
    """
    try:
        if not query or not query.strip():
            return _format_error_response("Empty search query provided")
        
        # Tavily 검색 실행
        results = tavily_tool.invoke({"query": query})
        
        # 결과 정리
        if isinstance(results, list) and results:
            formatted_results = []
            for item in results:
                if isinstance(item, dict):
                    formatted_results.append({
                        "title": item.get("title", ""),
                        "content": item.get("content", ""),
                        "url": item.get("url", "")
                    })
            
            return _format_success_response(
                data={
                    "query": query,
                    "results": formatted_results,
                    "total_count": len(formatted_results)
                },
                message=f"Found {len(formatted_results)} search results"
            )
        else:
            return _format_success_response(
                data={"query": query, "results": [], "total_count": 0},
                message="No search results found"
            )
            
    except Exception as e:
        return _format_error_response(f"Web search failed: {str(e)}")

def calculator_tool(expression: str) -> Dict[str, Any]:
    """
    수학 계산을 수행하는 도구
    
    Args:
        expression (str): 계산할 수학 표현식
        
    Returns:
        Dict[str, Any]: 표준화된 응답 형식
    """
    try:
        if not expression or not expression.strip():
            return _format_error_response("Empty expression provided")
        
        # 보안 검사: 알파벳 문자가 있으면 거부
        if re.search(r'[a-zA-Z_]', expression):
            return _format_error_response("Invalid characters in expression. Only numbers and operators allowed.")
        
        # sympy로 계산 수행
        expr = sympify(expression)
        result = expr.evalf()
        
        # 결과 포맷팅
        if isinstance(result, (Integer, Float)):
            if result.is_integer:
                final_result = int(result)
            else:
                final_result = float(result)
        else:
            final_result = str(result)
        
        return _format_success_response(
            data={
                "expression": expression,
                "result": final_result,
                "result_type": type(final_result).__name__
            },
            message=f"Calculation completed: {expression} = {final_result}"
        )
        
    except SympifyError as e:
        return _format_error_response(f"Invalid mathematical expression: {str(e)}")
    except Exception as e:
        return _format_error_response(f"Calculation failed: {str(e)}")

def db_query_tool(query: str) -> Dict[str, Any]:
    """
    데이터베이스 조회를 수행하는 도구
    
    Args:
        query (str): 실행할 SQL SELECT 쿼리
        
    Returns:
        Dict[str, Any]: 표준화된 응답 형식
    """
    try:
        if not query or not query.strip():
            return _format_error_response("Empty query provided")
        
        # 보안 검사: SELECT 쿼리만 허용
        query_cleaned = query.strip().lower()
        if not query_cleaned.startswith("select"):
            return _format_error_response("Only SELECT queries are allowed")
        
        # 위험한 키워드 검사
        dangerous_keywords = ['drop', 'delete', 'insert', 'update', 'alter', 'create', 'truncate']
        if any(keyword in query_cleaned for keyword in dangerous_keywords):
            return _format_error_response("Query contains dangerous keywords")
        
        # 쿼리 실행
        with engine.connect() as connection:
            result = connection.execute(query).fetchall()
            
            # 결과를 딕셔너리 리스트로 변환
            if result:
                columns = result[0].keys() if hasattr(result[0], 'keys') else []
                formatted_results = []
                
                for row in result:
                    if hasattr(row, '_asdict'):
                        formatted_results.append(row._asdict())
                    elif hasattr(row, 'keys'):
                        formatted_results.append(dict(row))
                    else:
                        # 튜플인 경우
                        formatted_results.append(dict(zip(columns, row)))
            else:
                formatted_results = []
            
            return _format_success_response(
                data={
                    "query": query,
                    "results": formatted_results,
                    "total_count": len(formatted_results)
                },
                message=f"Query executed successfully. Found {len(formatted_results)} records."
            )
            
    except Exception as e:
        return _format_error_response(f"Database query failed: {str(e)}")

def user_db_update_tool(state: State, user_id: str, field: str, value: Any) -> Dict[str, Any]:
    """
    사용자 정보를 업데이트하는 도구
    
    Args:
        state (State): 현재 상태
        user_id (str): 사용자 ID
        field (str): 업데이트할 필드명
        value (Any): 새로운 값
        
    Returns:
        Dict[str, Any]: 표준화된 응답 형식
    """
    try:
        if not user_id:
            return _format_error_response("User ID is required")
        
        if not field:
            return _format_error_response("Field name is required")
        
        # 지원되는 필드 목록
        supported_fields = {
            "total_budget_manwon": {"type": int, "updater": memo_set_budget},
            "wedding_date": {"type": str, "updater": memo_set_wedding_date},
            "guest_count": {"type": int, "updater": memo_set_guest_count}
        }
        
        if field not in supported_fields:
            return _format_error_response(f"Unsupported field: {field}. Supported fields: {list(supported_fields.keys())}")
        
        # 값 타입 검증 및 변환
        field_config = supported_fields[field]
        expected_type = field_config["type"]
        
        try:
            if expected_type == int:
                converted_value = int(value) if value is not None else None
            elif expected_type == str:
                converted_value = str(value) if value is not None else None
            else:
                converted_value = value
        except (ValueError, TypeError):
            return _format_error_response(f"Invalid value type for field {field}. Expected {expected_type.__name__}")
        
        # State 업데이트 수행
        updater_func = field_config["updater"]
        old_value = state.get(field)
        
        updater_func(state, converted_value)
        
        return _format_success_response(
            data={
                "user_id": user_id,
                "field": field,
                "old_value": old_value,
                "new_value": converted_value,
                "updated_profile": state.get('user_memo', {}).get('profile', {}) if state.get('user_memo') else {}
            },
            message=f"Successfully updated {field} for user {user_id}"
        )
        
    except Exception as e:
        return _format_error_response(f"User update failed: {str(e)}")

# ============= 레거시 호환성을 위한 래퍼 함수들 =============

def web_search_tool_legacy(query: str) -> str:
    """레거시 호환성을 위한 문자열 반환 버전"""
    result = web_search_tool(query)
    if result["success"]:
        return f"Search results for '{query}': {len(result['data']['results'])} items found"
    else:
        return f"Search failed: {result['error']}"

def calculator_tool_legacy(expression: str) -> Union[float, int, str]:
    """레거시 호환성을 위한 직접 결과 반환 버전"""
    result = calculator_tool(expression)
    if result["success"]:
        return result["data"]["result"]
    else:
        return f"Error: {result['error']}"

def db_query_tool_legacy(query: str) -> str:
    """레거시 호환성을 위한 문자열 반환 버전"""
    result = db_query_tool(query)
    if result["success"]:
        return str(result["data"]["results"])
    else:
        return f"Query failed: {result['error']}"

def user_db_update_tool_legacy(state: State, user_id: str, field: str, value: Any) -> str:
    """레거시 호환성을 위한 문자열 반환 버전"""
    result = user_db_update_tool(state, user_id, field, value)
    if result["success"]:
        return result["message"]
    else:
        return f"Update failed: {result['error']}"

# ============= 도구 검증 함수 =============

def validate_tool_availability() -> Dict[str, bool]:
    """모든 도구들의 사용 가능성을 검사"""
    results = {}
    
    # Web search tool 검사
    try:
        test_result = web_search_tool("test")
        results["web_search_tool"] = True
    except:
        results["web_search_tool"] = False
    
    # Calculator tool 검사
    try:
        test_result = calculator_tool("1 + 1")
        results["calculator_tool"] = test_result["success"]
    except:
        results["calculator_tool"] = False
    
    # Database tool 검사
    try:
        test_result = db_query_tool("SELECT 1")
        results["db_query_tool"] = test_result["success"]
    except:
        results["db_query_tool"] = False
    
    # User update tool 검사
    try:
        from state import initialize_state
        test_state = initialize_state("test_user", "test")
        test_result = user_db_update_tool(test_state, "test_user", "total_budget_manwon", 1000)
        results["user_db_update_tool"] = test_result["success"]
    except:
        results["user_db_update_tool"] = False
    
    return results

# ============= 도구 목록 (새로운 tool_execution_node용) =============

TOOL_REGISTRY = {
    "web_search_tool": web_search_tool,
    "calculator_tool": calculator_tool,
    "db_query_tool": db_query_tool,
    "user_db_update_tool": user_db_update_tool
}

# 레거시 도구 목록
LEGACY_TOOL_REGISTRY = {
    "web_search_tool": web_search_tool_legacy,
    "calculator_tool": calculator_tool_legacy,
    "db_query_tool": db_query_tool_legacy,
    "user_db_update_tool": user_db_update_tool_legacy
}