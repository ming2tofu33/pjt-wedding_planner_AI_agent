import os
import json
import re
from typing import Dict, Any, List
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_community.tools.tavily_search import TavilySearchResults
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

# Tavily 웹 검색 초기화
tavily_search = TavilySearchResults(
    max_results=5,
    api_key=os.getenv('TAVILY_API_KEY')
)

def db_query_tool(query_request: str, user_memo: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    웨딩 관련 업체 정보를 데이터베이스에서 조회 (개선된 버전)
    """
    try:
        print(f"[DEBUG] DB Query 시작 - 요청: {query_request}")
        print(f"[DEBUG] 사용자 메모: {user_memo}")
        
        # 사용자 메모에서 조건 추출
        budget = user_memo.get("budget", "") if user_memo else ""
        location = user_memo.get("preferred_location", "") if user_memo else ""
        
        # 테이블 정보 가져오기
        table_info = db.get_table_info()
        print(f"[DEBUG] 사용 가능한 테이블: {table_info[:500]}...")
        
        # LLM을 사용해 자연어 쿼리를 SQL로 변환
        sql_generation_prompt = f"""
다음 테이블 정보를 참고해서 사용자 요청에 맞는 SQL 쿼리를 작성해주세요.

테이블 정보:
{table_info}

사용자 요청: {query_request}
사용자 예산: {budget}
선호 지역: {location}

쿼리 작성 규칙:
1. 업체 유형 매핑:
   - "드레스" 관련 요청 → wedding_dress 테이블
   - "웨딩홀", "예식장" 관련 요청 → wedding_hall 테이블  
   - "스튜디오", "촬영" 관련 요청 → studio 테이블
   - "메이크업" 관련 요청 → makeup 테이블

2. 지역 필터링:
   - 지역명이나 지하철역명이 언급되면 subway 컬럼에서 LIKE 검색
   - 예: "청담역" → WHERE subway LIKE '%청담%'
   - 예: "강남" → WHERE subway LIKE '%강남%'

3. 예산 필터링:
   - 예산 정보가 있으면 min_fee 컬럼 활용
   - 예산 범위 내의 업체만 조회

4. 결과 제한:
   - 요청에서 "3곳", "5개" 등 숫자가 언급되면 그 수만큼 LIMIT
   - 언급이 없으면 기본적으로 LIMIT 5

5. 컬럼 선택:
   - conm (업체명), min_fee (최소비용), subway (지하철역), address (주소) 등 유용한 정보 선택
   - 모든 컬럼(*)보다는 필요한 컬럼만 선택

6. 정렬:
   - 예산이 있으면 min_fee 오름차순 정렬 (저렴한 순)
   - 예산이 없으면 conm 오름차순 정렬 (이름순)

예시:
- "청담역 근처 드레스 3곳 추천해줘" 
  → SELECT conm, min_fee, subway, address FROM wedding_dress WHERE subway LIKE '%청담%' ORDER BY min_fee ASC LIMIT 3

- "강남 웨딩홀 찾아줘"
  → SELECT conm, min_fee, subway, address FROM wedding_hall WHERE subway LIKE '%강남%' ORDER BY min_fee ASC LIMIT 5

SQL 쿼리만 반환하세요 (설명이나 백틱 없이):
"""
        
        # SQL 쿼리 생성
        sql_response = llm.invoke([HumanMessage(content=sql_generation_prompt)])
        sql_query = sql_response.content.strip()
        
        # SQL 정리 (혹시 있을 특수문자 제거)
        sql_query = sql_query.replace('```sql', '').replace('```', '').strip()
        
        # 세미콜론 제거 (보안상 안전)
        if sql_query.endswith(';'):
            sql_query = sql_query[:-1]
        
        print(f"[DEBUG] 생성된 SQL: {sql_query}")
        
        # SQL 실행 (안전한 방법으로)
        with engine.connect() as conn:
            # 트랜잭션 없이 읽기 전용으로 실행
            result = conn.execute(sa.text(sql_query))
            rows = result.fetchall()
            columns = list(result.keys())
            
            print(f"[DEBUG] 조회된 행 수: {len(rows)}")
            print(f"[DEBUG] 컬럼명: {columns}")
            
            # 결과를 딕셔너리 리스트로 변환
            results = []
            for row in rows:
                row_dict = {}
                for i, col in enumerate(columns):
                    value = row[i]
                    # None 값 처리
                    if value is None:
                        value = "정보없음"
                    row_dict[col] = value
                results.append(row_dict)
            
            print(f"[DEBUG] 변환된 결과: {results}")
        
        # 성공적인 응답 반환
        return {
            "status": "success",
            "query": sql_query,
            "results": results,
            "count": len(results),
            "message": f"{len(results)}개의 업체를 찾았습니다."
        }
        
    except Exception as e:
        print(f"[ERROR] DB query 실행 중 오류: {e}")
        print(f"[ERROR] 오류 타입: {type(e)}")
        
        # 구체적인 오류 메시지 제공
        error_message = str(e)
        if "no such table" in error_message.lower():
            error_message = "요청하신 업체 유형의 데이터를 찾을 수 없습니다."
        elif "no such column" in error_message.lower():
            error_message = "데이터베이스 구조에 문제가 있습니다."
        elif "syntax error" in error_message.lower():
            error_message = "검색 조건을 처리하는 중 오류가 발생했습니다."
        else:
            error_message = "데이터베이스 조회 중 오류가 발생했습니다."
        
        return {
            "status": "error",
            "error": error_message,
            "results": [],
            "count": 0,
            "query": query_request,
            "message": f"죄송합니다. {error_message} 다른 조건으로 다시 시도해보세요."
        }

# 웹 검색 툴은 기존과 동일
def web_search_tool(search_query: str, context_data: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    TAVILY를 사용한 실제 웹 검색 (컨텍스트 활용 개선)
    """
    try:
        print(f"[DEBUG] 웹 검색 시작: {search_query}")
        print(f"[DEBUG] 컨텍스트 데이터: {context_data}")
        
        # 검색 쿼리 개선
        enhanced_query = search_query
        
        # 컨텍스트에서 업체명 추출하여 검색 쿼리 보강
        if context_data and isinstance(context_data, dict):
            db_results = context_data.get("db_query", {}).get("results", [])
            if db_results:
                # DB에서 찾은 업체명들을 검색 쿼리에 포함
                company_names = [result.get("conm", "") for result in db_results if result.get("conm")]
                if company_names:
                    enhanced_query = f"{search_query} {' '.join(company_names[:3])}"  # 상위 3개만
        
        # "그 업체들", "위의 업체들" 같은 참조 표현 처리
        if any(word in search_query for word in ["그 업체", "위의", "위에서", "앞서"]):
            if context_data and "db_query" in context_data:
                db_results = context_data.get("db_query", {}).get("results", [])
                if db_results:
                    company_names = [result.get("conm", "") for result in db_results]
                    enhanced_query = f"웨딩 {' '.join(company_names)} 업체 정보 후기"
        
        print(f"[DEBUG] 개선된 검색 쿼리: {enhanced_query}")
        
        # Tavily 검색 실행
        search_results = tavily_search.invoke({"query": enhanced_query})
        
        formatted_results = []
        for result in search_results:
            formatted_results.append({
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "snippet": result.get("content", "")
            })
        
        return {
            "status": "success",
            "query": enhanced_query,
            "original_query": search_query,
            "results": formatted_results,
            "count": len(formatted_results)
        }
        
    except Exception as e:
        print(f"[ERROR] 웹 검색 오류: {e}")
        return {
            "status": "error",
            "error": str(e),
            "results": f"웹 검색 중 오류가 발생했습니다: {str(e)}"
        }

# 계산기 툴도 개선
def calculator_tool(calculation_request: str, context_data: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    계산 툴 - 단순 계산 + 웨딩 특화 계산 (개선된 버전)
    """
    try:
        print(f"[DEBUG] 계산 요청: {calculation_request}")
        print(f"[DEBUG] 컨텍스트 데이터: {context_data}")
        
        # 1. 단순 수식 계산 지원
        cleaned_request = calculation_request.replace(',', '').replace('만원', '0000').replace('억', '00000000').strip()
        
        # 숫자와 기본 연산자로만 구성되었는지 확인
        if re.fullmatch(r'[\d\s+\-*/().]+', cleaned_request):
            try:
                simple_result = eval(cleaned_request)
                return {
                    "status": "success",
                    "request": calculation_request,
                    "result": f"{simple_result:,}",
                    "type": "simple_calculation",
                    "explanation": f"{calculation_request} = {simple_result:,}"
                }
            except Exception as e:
                print(f"[DEBUG] 단순 계산 실패, LLM으로 진행: {e}")
        
        # 2. LLM을 사용한 웨딩 특화 계산
        calc_prompt = f"""
다음 계산 요청을 처리해주세요. 웨딩 관련 계산이면 적절한 공식을 사용하세요.

계산 요청: {calculation_request}
컨텍스트: {json.dumps(context_data, ensure_ascii=False) if context_data else "없음"}

웨딩 관련 계산 예시:
- 총 예산 계산: 각 카테고리별 비용 합계
- 하객수 기반 예산: 하객 1명당 식대 + 답례품 비용  
- 업체별 비용 비교: 여러 업체 견적 비교
- 예산 분배: 총예산을 카테고리별로 분배 (웨딩홀 40%, 스드메 30%, 기타 30%)

결과를 다음 형식으로 답변해주세요:
계산식: [사용한 공식]
결과: [숫자 결과] 
설명: [계산 과정 설명]
"""
        
        calc_response = llm.invoke([HumanMessage(content=calc_prompt)])
        
        return {
            "status": "success",
            "request": calculation_request,
            "result": calc_response.content,
            "type": "wedding_calculation",
            "explanation": "웨딩 특화 계산 완료"
        }
        
    except Exception as e:
        print(f"[ERROR] 계산 오류: {e}")
        return {
            "status": "error",
            "error": str(e),
            "result": "계산 중 오류가 발생했습니다."
        }

def memo_update_tool(update_data: str) -> Dict[str, Any]:
    """
    메모 업데이트 툴
    """
    try:
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
        print(f"[ERROR] 메모 업데이트 오류: {e}")
        return {
            "status": "error",
            "error": str(e),
            "message": "메모 업데이트 중 오류가 발생했습니다."
        }

# 툴 실행 헬퍼 함수 (개선된 버전 - 툴 간 데이터 전달 지원)
def execute_tools(tools_needed: List[str], user_message: str, user_memo: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    필요한 툴들을 실행하는 헬퍼 함수 (툴 간 데이터 전달 개선)
    """
    results = {}
    
    print(f"[DEBUG] 실행할 툴들: {tools_needed}")
    print(f"[DEBUG] 사용자 메시지: {user_message}")
    print(f"[DEBUG] 사용자 메모: {user_memo}")
    
    for tool_name in tools_needed:
        try:
            print(f"[DEBUG] {tool_name} 툴 실행 시작")
            
            if tool_name == "db_query":
                results[tool_name] = db_query_tool(user_message, user_memo)
                
            elif tool_name == "web_search":
                # DB 쿼리 결과가 있으면 컨텍스트로 전달
                context_data = {"db_query": results.get("db_query", {})} if "db_query" in results else None
                results[tool_name] = web_search_tool(user_message, context_data)
                
            elif tool_name == "calculator":
                results[tool_name] = calculator_tool(user_message, user_memo)
                
            elif tool_name == "memo_update":
                results[tool_name] = memo_update_tool(json.dumps(user_memo) if user_memo else "{}")
            else:
                results[tool_name] = {"status": "error", "error": f"Unknown tool: {tool_name}"}
                
            print(f"[DEBUG] {tool_name} 툴 실행 완료: {results[tool_name].get('status', 'unknown')}")
                
        except Exception as e:
            print(f"[ERROR] {tool_name} 툴 실행 중 오류: {e}")
            results[tool_name] = {"status": "error", "error": str(e)}
    
    print(f"[DEBUG] 모든 툴 실행 완료: {list(results.keys())}")
    return results