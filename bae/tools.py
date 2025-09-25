import os
import json
import re # re 모듈을 최상단으로 이동했습니다.
from typing import Dict, Any, List
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_community.tools.tavily_search import TavilySearchResults
from db import db, engine # db, engine 객체는 이 파일 외부에서 import 된다고 가정
import sqlalchemy as sa
from dotenv import load_dotenv

load_dotenv()

# OpenAI 모델 초기화
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.1,
    api_key=os.getenv('OPENAI_API_KEY')
)

# Tavily 웹 검색 초기화
tavily_search = TavilySearchResults(
    max_results=5,
    api_key=os.getenv('TAVILY_API_KEY')
)

@tool
def db_query_tool(query_request: str, user_memo: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    웨딩 관련 업체 정보를 데이터베이스에서 조회
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
        2. 지역이 있으면 subway 컬umn에서 관련 지하철역으로 필터링
        3. 결과는 최대 5개로 제한
        4. 깔끔한 SQL 쿼리만 반환 (설명, 백틱, 주석 없이)
        
        예시: SELECT conm, min_fee, subway FROM wedding_hall WHERE min_fee <= 1000000 LIMIT 5
        """
        
        sql_response = llm.invoke([HumanMessage(content=prompt)])
        sql_query = sql_response.content.strip()
        
        # SQL 정리 (혹시 있을 특수문자 제거)
        sql_query = sql_query.replace('```sql', '').replace('```', '').strip()
        
        print(f"[DEBUG] Generated SQL: {repr(sql_query)}")
        
        # 직접 SQLAlchemy 엔진 사용
        with engine.connect() as conn:
            result = conn.execute(sa.text(sql_query))
            rows = result.fetchall()
            columns = list(result.keys())
            
            # 결과를 딕셔너리 리스트로 변환
            results = []
            for row in rows:
                row_dict = {}
                for i, col in enumerate(columns):
                    row_dict[col] = row[i]
                results.append(row_dict)
        
        return {
            "status": "success",
            "query": sql_query,
            "results": results,
            "count": len(results)
        }
        
    except Exception as e:
        print(f"[ERROR] DB query error: {e}")
        return {
            "status": "error",
            "error": str(e),
            "results": "데이터베이스 조회 중 오류가 발생했습니다."
        }

@tool
def web_search_tool(search_query: str) -> Dict[str, Any]:
    """
    TAVILY를 사용한 실제 웹 검색
    """
    try:
        # Tavily로 웹 검색 실행
        search_results = tavily_search.invoke({"query": search_query})
        
        # 결과 정리
        formatted_results = []
        for result in search_results:
            formatted_results.append({
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "snippet": result.get("content", "")
            })
        
        return {
            "status": "success",
            "query": search_query,
            "results": formatted_results,
            "count": len(formatted_results)
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "results": f"웹 검색 중 오류가 발생했습니다: {str(e)}"
        }

@tool
def calculator_tool(calculation_request: str, context_data: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    계산 툴 - 단순 계산 + 웨딩 특화 계산
    """
    try:
        # 1. 단순 수식 계산 지원 (가장 먼저 처리)
        # 쉼표(,) 제거 및 공백 정리
        cleaned_request = calculation_request.replace(',', '').strip()
        
        # 숫자, 공백, 기본 연산자(+, -, *, /, (, ))로만 구성되었는지 확인
        if re.fullmatch(r'[\d\s+\-*/().]+', cleaned_request):
            try:
                # eval을 사용해 단순 수식 계산
                simple_result = eval(cleaned_request)
                return {
                    "status": "success",
                    "request": calculation_request,
                    "result": simple_result,
                    "type": "simple_calculation",
                    "explanation": f"{calculation_request} = {simple_result:,}"
                }
            except Exception as e:
                # 단순 계산 오류는 LLM 로직으로 넘어가도록 처리
                print(f"[DEBUG] Simple calculation error, deferring to LLM: {e}")
                pass
        
        # 2. LLM을 사용해 계산 요청 해석 및 실행 (웨딩 특화 계산)
        prompt = f"""
        다음 계산 요청을 처리해주세요. 웨딩 관련 계산이면 적절한 공식을 사용하세요.
        
        계산 요청: {calculation_request}
        컨텍스트: {json.dumps(context_data, ensure_ascii=False) if context_data else "없음"}
        
        웨딩 관련 계산 예시:
        - 총 예산 계산: 각 카테고리별 비용 합계
        - 하객수 기반 예산: 하객 1명당 식대 + 답례품 비용
        - 업체별 비용 비교: 여러 업체 견적 비교
        - 예산 분배: 총예산을 카테고리별로 분배
        
        결과를 다음 형식으로 답변해주세요:
        계산식: [사용한 공식]
        결과: [숫자 결과]
        설명: [계산 과정 설명]
        """
        
        calc_response = llm.invoke([HumanMessage(content=prompt)])
        
        return {
            "status": "success",
            "request": calculation_request,
            "result": calc_response.content,
            "type": "wedding_calculation",
            "explanation": "웨딩 특화 계산 완료"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "result": "계산 중 오류가 발생했습니다."
        }

@tool  
def memo_update_tool(update_data: str) -> Dict[str, Any]:
    """
    메모 업데이트 툴 (문자열 입력으로 변경)
    """
    try:
        # 문자열을 딕셔너리로 변환 시도
        if isinstance(update_data, str):
            try:
                data = json.loads(update_data)
            except:
                data = {"raw_input": update_data}
        else:
            data = update_data
            
        return {
            "status": "success",
            "message": "메모 업데이트가 완료되었습니다.",
            "updated_data": data
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "message": "메모 업데이트 중 오류가 발생했습니다."
        }

# 툴 실행 헬퍼 함수
def execute_tools(tools_needed: List[str], user_message: str, user_memo: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    필요한 툴들을 실행하는 헬퍼 함수
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
            elif tool_name == "memo_update":
                results[tool_name] = memo_update_tool(user_memo or {})
            else:
                results[tool_name] = {"status": "error", "error": f"Unknown tool: {tool_name}"}
                
        except Exception as e:
            results[tool_name] = {"status": "error", "error": str(e)}
    
    return results