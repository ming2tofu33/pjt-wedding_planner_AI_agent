import os
import json
from typing import Dict, Any, List
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from db import db, engine
import sqlalchemy as sa
from dotenv import load_dotenv

load_dotenv()

# OpenAI 모델 초기화
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.1,
    api_key=os.getenv('OPENAI_API_KEY')
)

@tool
def db_query_tool(query_request: str, user_memo: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    웨딩 관련 업체 정보를 데이터베이스에서 조회
    
    Args:
        query_request: 사용자의 검색 요청
        user_memo: 사용자 메모리 정보 (예산, 선호 지역 등)
    
    Returns:
        Dict[str, Any]: 조회 결과
    """
    try:
        # 사용자 메모에서 조건 추출
        budget = user_memo.get("budget", "") if user_memo else ""
        location = user_memo.get("preferred_location", "") if user_memo else ""
        
        # LLM을 사용해 자연어 쿼리를 SQL로 변환
        table_info = db.get_table_info()
        
        prompt = f"""
        다음 테이블 정보를 참고해서 사용자 요청에 맞는 SQL 쿼리를 작성해주세요.
        
        테이블 정보:
        {table_info}
        
        사용자 요청: {query_request}
        사용자 예산: {budget}
        선호 지역: {location}
        
        조건:
        1. 예산이 있으면 min_fee나 관련 가격 컬럼으로 필터링
        2. 지역이 있으면 subway 컬럼에서 관련 지하철역으로 필터링
        3. 결과는 최대 10개로 제한
        4. SQL 쿼리만 반환 (설명 없이)
        
        예시: SELECT * FROM wedding_hall WHERE min_fee <= 1000000 LIMIT 10;
        """
        
        sql_response = llm.invoke([HumanMessage(content=prompt)])
        sql_query = sql_response.content.strip()
        
        # SQL 쿼리 실행
        result = db.run(sql_query)
        
        return {
            "status": "success",
            "query": sql_query,
            "results": result,
            "count": len(result.split('\n')) - 1 if result else 0
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "results": "데이터베이스 조회 중 오류가 발생했습니다."
        }

@tool
def web_search_tool(search_query: str) -> Dict[str, Any]:
    """
    웹 검색 툴 (placeholder - 실제 검색 API 연동 필요)
    
    Args:
        search_query: 검색할 키워드
        
    Returns:
        Dict[str, Any]: 검색 결과
    """
    try:
        # TODO: 실제 웹 검색 API (Google, Bing 등) 연동
        # 현재는 placeholder로 구현
        
        return {
            "status": "success",
            "query": search_query,
            "results": [
                {
                    "title": f"{search_query} 관련 정보 1",
                    "url": "https://example.com/1",
                    "snippet": f"{search_query}에 대한 유용한 정보입니다."
                },
                {
                    "title": f"{search_query} 관련 정보 2", 
                    "url": "https://example.com/2",
                    "snippet": f"{search_query} 관련 추가 정보입니다."
                }
            ],
            "count": 2
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "results": "웹 검색 중 오류가 발생했습니다."
        }

@tool
def calculator_tool(calculation_request: str, context_data: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    계산 툴 - 단순 계산 + 웨딩 특화 계산
    
    Args:
        calculation_request: 계산 요청
        context_data: 계산에 필요한 컨텍스트 데이터
        
    Returns:
        Dict[str, Any]: 계산 결과
    """
    try:
        # LLM을 사용해 계산 요청 해석 및 실행
        prompt = f"""
        다음 계산 요청을 처리해주세요. 웨딩 관련 계산이면 적절한 공식을 사용하세요.
        
        계산 요청: {calculation_request}
        컨텍스트: {json.dumps(context_data, ensure_ascii=False) if context_data else "없음"}
        
        웨딩 관련 계산 예시:
        - 하객수 기반 예산: 하객 1명당 식대 + 답례품 비용
        - 업체별 비용 비교: 여러 업체 견적 비교
        - 총 예산 계산: 각 카테고리별 비용 합계
        
        결과를 다음 형식으로 답변해주세요:
        계산식: [사용한 공식]
        결과: [숫자 결과]
        설명: [계산 과정 설명]
        """
        
        calc_response = llm.invoke([HumanMessage(content=prompt)])
        
        # 단순 수식 계산도 지원 (eval 사용 주의)
        if any(op in calculation_request for op in ['+', '-', '*', '/', '(', ')']):
            try:
                # 안전한 계산을 위해 허용된 문자만 포함된 경우에만 eval 사용
                import re
                if re.match(r'^[0-9+\-*/().\s]+$', calculation_request):
                    simple_result = eval(calculation_request)
                    return {
                        "status": "success",
                        "request": calculation_request,
                        "result": simple_result,
                        "type": "simple_calculation",
                        "explanation": f"{calculation_request} = {simple_result}"
                    }
            except:
                pass
        
        return {
            "status": "success",
            "request": calculation_request,
            "result": calc_response.content,
            "type": "wedding_calculation",
            "explanation": "LLM 기반 웨딩 계산 완료"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "result": "계산 중 오류가 발생했습니다."
        }

@tool  
def user_db_update_tool(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    사용자 데이터베이스 업데이트 툴 (MVP 이후 구현 예정)
    
    Args:
        user_data: 업데이트할 사용자 데이터
        
    Returns:
        Dict[str, Any]: 업데이트 결과
    """
    try:
        # TODO: MVP 완료 후 실제 사용자 DB 테이블 생성 및 연동
        
        return {
            "status": "success",
            "message": "사용자 DB 업데이트 기능은 MVP 이후 구현 예정입니다.",
            "data": user_data
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "message": "사용자 DB 업데이트 중 오류가 발생했습니다."
        }

# 툴 실행 헬퍼 함수
def execute_tools(tools_needed: List[str], user_message: str, user_memo: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    필요한 툴들을 실행하는 헬퍼 함수
    
    Args:
        tools_needed: 실행할 툴 목록
        user_message: 사용자 메시지
        user_memo: 사용자 메모리
        
    Returns:
        Dict[str, Any]: 모든 툴 실행 결과
    """
    results = {}
    
    for tool_name in tools_needed:
        try:
            if tool_name == "db_query":
                results[tool_name] = db_query_tool(user_message, user_memo)
            elif tool_name == "web_search":
                results[tool_name] = web_search_tool(user_message)
            elif tool_name == "calculator":
                results[tool_name] = calculator_tool(user_message, user_memo)
            elif tool_name == "user_db_update":
                results[tool_name] = user_db_update_tool(user_memo or {})
            else:
                results[tool_name] = {"status": "error", "error": f"Unknown tool: {tool_name}"}
                
        except Exception as e:
            results[tool_name] = {"status": "error", "error": str(e)}
    
    return results