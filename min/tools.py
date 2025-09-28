import os
import json
import re
from typing import Dict, Any, List
from datetime import datetime, date, time
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_community.tools.tavily_search import TavilySearchResults
from db import db, engine
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# 안전한 타입 체크 유틸리티 함수
def safe_str_join(items, separator=" "):
    """안전하게 리스트를 문자열로 연결"""
    if not items:
        return ""
    safe_items = [str(item) for item in items if item is not None]
    return separator.join(safe_items)

def safe_get_content(message):
    """메시지에서 안전하게 content 추출"""
    if not message:
        return ""
    if hasattr(message, 'content') and message.content:
        return str(message.content)
    return ""

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
    웨딩 관련 업체 정보를 데이터베이스에서 조회 (개선된 버전 - 테이블별 컬럼 최적화)
    """
    try:
        # query_request가 리스트 형태로 올 경우 문자열로 변환
        if isinstance(query_request, list):
            if query_request and isinstance(query_request[0], dict) and 'text' in query_request[0]:
                actual_query = query_request[0]['text']
            else:
                actual_query = str(query_request[0]) if query_request else ""
        else:
            actual_query = str(query_request)
        
        print(f"[DEBUG] DB Query 시작 - 요청: {actual_query}")
        print(f"[DEBUG] 원본 query_request 타입: {type(query_request)}")
        print(f"[DEBUG] 사용자 메모: {user_memo}")
        
        # 새로운 메모 구조에서 조건 추출
        budget = ""
        location = ""
        
        if user_memo:
            # 예산 정보 추출 (새로운 구조: budget.total, budget.wedding_hall 등)
            budget_info = user_memo.get("budget", {})
            if isinstance(budget_info, dict):
                # 총 예산이 있으면 우선 사용
                if budget_info.get("total"):
                    budget = budget_info.get("total")
                # 특정 업체 예산이 있으면 해당 예산 사용
                elif budget_info.get("wedding_hall") and "웨딩홀" in actual_query:
                    budget = budget_info.get("wedding_hall")
                elif budget_info.get("wedding_dress") and "드레스" in actual_query:
                    budget = budget_info.get("wedding_dress")
                elif budget_info.get("studio") and "스튜디오" in actual_query:
                    budget = budget_info.get("studio")
                elif budget_info.get("makeup") and "메이크업" in actual_query:
                    budget = budget_info.get("makeup")
            elif isinstance(budget_info, str):
                # 기존 구조 호환성
                budget = budget_info
            
            # 선호 지역 정보 추출 (새로운 구조: preferred_locations 배열)
            preferred_locations = user_memo.get("preferred_locations", [])
            if isinstance(preferred_locations, list) and preferred_locations:
                location = preferred_locations[0]  # 첫 번째 선호 지역 사용
            elif isinstance(preferred_locations, str):
                # 기존 구조 호환성
                location = preferred_locations
            
            # 주소 정보도 활용 (거주지가 선호 지역일 가능성)
            if not location and user_memo.get("address"):
                location = user_memo.get("address")
        
        print(f"[DEBUG] 추출된 예산: {budget}")
        print(f"[DEBUG] 추출된 선호지역: {location}")
        
        # 테이블 정보 가져오기
        table_info = db.get_table_info()
        print(f"[DEBUG] 사용 가능한 테이블: {table_info[:500]}...")
        
        # 개선된 SQL 생성 프롬프트 (실제 컬럼만 사용)
        sql_generation_prompt = f"""
다음 테이블 정보를 참고해서 사용자 요청에 맞는 SQL 쿼리를 작성해주세요.

테이블 정보:
{table_info}

사용자 요청: {actual_query}
사용자 예산: {budget}
선호 지역: {location}

**중요: 실제 존재하는 컬럼만 사용**
1. wedding_dress 테이블: "conm","wedding","photo","wedding+photo","fitting_fee","helper","min_fee","subway"
2. wedding_hall 테이블: "conm","season(T/F)","peak(T/F)","hall_rental_fee","meal_expense","num_guarantors","min_fee","snapphoto","snapvideo","subway"
3. makeup 테이블: "conm","manager(1)","manager(2)","vicedirector(1)","vicedirector(2)","director(1)","director(2)","min_fee","subway"
4. studio 테이블: "conm","std_price","afternoon_price","allday_price","subway"

**쿼리 작성 규칙:**
1. 업체 유형 매핑:
   - "드레스" 관련 요청 → wedding_dress 테이블, min_fee 사용
   - "웨딩홀", "예식장" 관련 요청 → wedding_hall 테이블, min_fee 사용  
   - "스튜디오", "촬영" 관련 요청 → studio 테이블, std_price 사용
   - "메이크업" 관련 요청 → makeup 테이블, min_fee 사용

2. 컬럼 선택 (존재하는 컬럼만):
   - wedding_dress: SELECT conm, min_fee, subway FROM wedding_dress
   - wedding_hall: SELECT conm, min_fee, subway FROM wedding_hall  
   - makeup: SELECT conm, min_fee, subway FROM makeup
   - studio: SELECT conm, std_price, subway FROM studio

3. 지역 필터링:
   - 지역명이나 지하철역명이 언급되면 subway 컬럼에서 LIKE 검색
   - 예: "청담역" → WHERE subway LIKE '%청담%'
   - 예: "강남" → WHERE subway LIKE '%강남%'

4. 예산 필터링:
   - 예산 정보가 있으면 가격 컬럼 활용 (min_fee 또는 std_price)
   - 예산 범위 내의 업체만 조회
   - 예산에서 숫자 추출: "5000만원" → 50000000

5. 결과 제한:
   - 요청에서 "3곳", "5개" 등 숫자가 언급되면 그 수만큼 LIMIT
   - 언급이 없으면 기본적으로 LIMIT 5

6. 정렬:
   - 예산이 있으면 가격 컬럼 오름차순 정렬 (저렴한 순)
   - 예산이 없으면 conm 오름차순 정렬 (이름순)

**중요: address, tel 컬럼은 존재하지 않으므로 절대 사용하지 마세요**

예시:
- "청담역 근처 드레스 3곳 추천해줘" 
  → SELECT conm, min_fee, subway FROM wedding_dress WHERE subway LIKE '%청담%' ORDER BY min_fee ASC LIMIT 3

- "강남 스튜디오 찾아줘"
  → SELECT conm, std_price, subway FROM studio WHERE subway LIKE '%강남%' ORDER BY std_price ASC LIMIT 5

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
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST'),
            port=os.getenv('POSTGRES_PORT', '5432'), 
            database=os.getenv('POSTGRES_DB'),
            user=os.getenv('POSTGRES_USER'),
            password=os.getenv('POSTGRES_PASSWORD')
        )
        
        with conn.cursor() as cur:
            cur.execute(sql_query)
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]
        
        conn.close()
        
        print(f"[DEBUG] 조회된 행 수: {len(rows)}")
        print(f"[DEBUG] 컬럼명: {columns}")
            
        # 결과를 딕셔너리 리스트로 변환 (가격 포맷팅 개선)
        results = []
        for row in rows:
            row_dict = {}
            for i, col in enumerate(columns):
                value = row[i]
                # None 값 처리
                if value is None:
                    value = "정보없음"
                # 가격 컬럼 포맷팅 (숫자인 경우 천 단위 콤마 추가)
                elif col in ['min_fee', 'std_price'] and isinstance(value, (int, float)):
                    value = f"{int(value):,}원"
                # 전화번호 포맷팅
                elif col == 'tel' and value and value != "정보없음":
                    value = str(value).strip()
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
            error_message = "데이터베이스 구조에 문제가 있습니다. 특히 스튜디오는 std_price 컬럼을 사용해야 합니다."
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
        # search_query가 리스트 형태로 올 경우 문자열로 변환
        if isinstance(search_query, list):
            if search_query and isinstance(search_query[0], dict) and 'text' in search_query[0]:
                actual_query = search_query[0]['text']
            else:
                actual_query = str(search_query[0]) if search_query else ""
        else:
            actual_query = str(search_query)
        
        print(f"[DEBUG] 웹 검색 시작: {actual_query}")
        print(f"[DEBUG] 원본 search_query 타입: {type(search_query)}")
        print(f"[DEBUG] 컨텍스트 데이터: {context_data}")
        
        # 검색 쿼리 개선
        enhanced_query = actual_query
        
        # 컨텍스트에서 업체명 추출하여 검색 쿼리 보강
        if context_data and isinstance(context_data, dict):
            db_results = context_data.get("db_query", {}).get("results", [])
            if db_results and isinstance(db_results, list):
                # DB에서 찾은 업체명들을 검색 쿼리에 포함
                company_names = []
                for result in db_results:
                    if isinstance(result, dict) and result.get("conm"):
                        company_names.append(str(result.get("conm")))
                
                if company_names:
                    enhanced_query = f"{search_query} {' '.join(company_names[:3])}"  # 상위 3개만
        
        # "그 업체들", "위의 업체들" 같은 참조 표현 처리
        if any(word in search_query for word in ["그 업체", "위의", "위에서", "앞서"]):
            if context_data and "db_query" in context_data:
                db_results = context_data.get("db_query", {}).get("results", [])
                if db_results and isinstance(db_results, list):
                    company_names = []
                    for result in db_results:
                        if isinstance(result, dict) and result.get("conm"):
                            company_names.append(str(result.get("conm")))
                    
                    if company_names:
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

# 계산기 툴도 기존과 동일
def calculator_tool(calculation_request: str, context_data: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    계산 툴 - 단순 계산 + 웨딩 특화 계산 (개선된 버전)
    """
    try:
        # calculation_request가 리스트 형태로 올 경우 문자열로 변환
        if isinstance(calculation_request, list):
            if calculation_request and isinstance(calculation_request[0], dict) and 'text' in calculation_request[0]:
                actual_request = calculation_request[0]['text']
            else:
                actual_request = str(calculation_request[0]) if calculation_request else ""
        else:
            actual_request = str(calculation_request)
        
        print(f"[DEBUG] 계산 요청: {actual_request}")
        print(f"[DEBUG] 원본 calculation_request 타입: {type(calculation_request)}")
        print(f"[DEBUG] 컨텍스트 데이터: {context_data}")
        
        # 1. 단순 수식 계산 지원
        cleaned_request = actual_request.replace(',', '').replace('만원', '0000').replace('억', '00000000').strip()
        
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
    필요한 툴들을 실행하는 헬퍼 함수 (툴 간 데이터 전달 개선 + user_db_update 추가)
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
                # DB 쿼리 결과가 있으면 컨텍스트로 전달 (안전한 방식)
                context_data = None
                if "db_query" in results and isinstance(results["db_query"], dict):
                    context_data = {"db_query": results["db_query"]}
                results[tool_name] = web_search_tool(user_message, context_data)
                
            elif tool_name == "calculator":
                results[tool_name] = calculator_tool(user_message, user_memo)
                
            elif tool_name == "memo_update":
                results[tool_name] = memo_update_tool(json.dumps(user_memo) if user_memo else "{}")
                
            elif tool_name == "user_db_update":
                # 사용자 일정 관리 툴 추가
                # 메시지에서 액션과 데이터 파싱
                action, schedule_data = _parse_schedule_request(user_message)
                results[tool_name] = user_db_update_tool(action, schedule_data, user_memo)
                
            else:
                results[tool_name] = {"status": "error", "error": f"Unknown tool: {tool_name}"}
                
            print(f"[DEBUG] {tool_name} 툴 실행 완료: {results[tool_name].get('status', 'unknown')}")
                
        except Exception as e:
            print(f"[ERROR] {tool_name} 툴 실행 중 오류: {e}")
            results[tool_name] = {"status": "error", "error": str(e)}
    
    print(f"[DEBUG] 모든 툴 실행 완료: {list(results.keys())}")
    return results

def _parse_schedule_request(user_message: str) -> tuple[str, Dict[str, Any]]:
    """
    사용자 메시지에서 일정 관련 액션과 데이터를 파싱
    """
    message_lower = user_message.lower()
    
    # 일정 조회
    if any(word in message_lower for word in ["일정", "스케줄", "계획", "보여줘", "확인"]):
        if any(word in message_lower for word in ["목록", "전체", "모든", "보여줘"]):
            return "list", {}
    
    # 일정 추가
    elif any(word in message_lower for word in ["추가", "등록", "만들어", "생성", "예약"]):
        # 간단한 일정 데이터 추출 시도
        schedule_data = {"title": user_message}
        
        # 날짜 패턴 찾기 (YYYY-MM-DD, MM/DD, 내일, 다음주 등)
        import re
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # 2024-12-25
            r'\d{1,2}/\d{1,2}',    # 12/25
            r'\d{1,2}월\s*\d{1,2}일'  # 12월 25일
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, user_message)
            if match:
                schedule_data["scheduled_date_raw"] = match.group()
                break
        
        return "add", schedule_data
    
    # 일정 완료
    elif any(word in message_lower for word in ["완료", "끝", "done", "완성"]):
        return "complete", {"message": user_message}
    
    # 일정 수정
    elif any(word in message_lower for word in ["수정", "변경", "업데이트"]):
        return "update", {"message": user_message}
    
    # 일정 삭제
    elif any(word in message_lower for word in ["삭제", "제거", "취소"]):
        return "delete", {"message": user_message}
    
    # 기본값: 목록 조회
    return "list", {}


def user_db_update_tool(action: str, schedule_data: Dict[str, Any] = None, user_memo: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    사용자 일정 관리 도구 - user_schedule 테이블과 연동
    
    Actions:
    - 'list': 일정 목록 조회
    - 'add': 새 일정 추가
    - 'update': 기존 일정 수정
    - 'delete': 일정 삭제
    - 'complete': 일정 완료 처리
    - 'sync': 메모와 DB 동기화
    """
    try:
        user_id = os.getenv('DEFAULT_USER_ID', 'mvp-test-user')
        
        print(f"[DEBUG] user_db_update_tool 실행 - 액션: {action}")
        print(f"[DEBUG] 일정 데이터: {schedule_data}")
        print(f"[DEBUG] 사용자 ID: {user_id}")
        
        # 이 두 줄 삭제
        # from db import engine
        # import sqlalchemy as sa
        
        if action == "list":
            # 일정 목록 조회
            return _get_user_schedules(user_id)
            
        elif action == "add":
            # 새 일정 추가
            if not schedule_data:
                return {"status": "error", "error": "일정 데이터가 필요합니다."}
            return _add_user_schedule(user_id, schedule_data)
            
        elif action == "update":
            # 일정 수정
            if not schedule_data or not schedule_data.get("id"):
                return {"status": "error", "error": "수정할 일정 ID가 필요합니다."}
            return _update_user_schedule(schedule_data)
            
        elif action == "delete":
            # 일정 삭제
            if not schedule_data or not schedule_data.get("id"):
                return {"status": "error", "error": "삭제할 일정 ID가 필요합니다."}
            return _delete_user_schedule(schedule_data["id"])
            
        elif action == "complete":
            # 일정 완료 처리
            if not schedule_data or not schedule_data.get("id"):
                return {"status": "error", "error": "완료할 일정 ID가 필요합니다."}
            return _complete_user_schedule(schedule_data["id"])
            
        elif action == "sync":
            # 메모와 DB 동기화
            return _sync_memo_with_db(user_id, user_memo)
            
        else:
            return {"status": "error", "error": f"지원하지 않는 액션: {action}"}
            
    except Exception as e:
        print(f"[ERROR] user_db_update_tool 오류: {e}")
        return {
            "status": "error",
            "error": str(e),
            "message": "일정 관리 중 오류가 발생했습니다."
        }

def _get_user_schedules(user_id: str, limit: int = 20) -> Dict[str, Any]:
    """사용자 일정 목록 조회"""
    try:
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST'),
            port=os.getenv('POSTGRES_PORT', '5432'), 
            database=os.getenv('POSTGRES_DB'),
            user=os.getenv('POSTGRES_USER'),
            password=os.getenv('POSTGRES_PASSWORD')
        )

        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, scheduled_date, scheduled_time, status, 
                       category, description, priority, created_at, updated_at
                FROM user_schedule 
                WHERE user_id = %s 
                ORDER BY scheduled_date ASC, scheduled_time ASC
                LIMIT %s
            """, (user_id, limit))
            
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]  # 이 부분 수정
            
            schedules = []
            for row in rows:
                schedule = {}
                for i, col in enumerate(columns):
                    value = row[i]
                    # 날짜/시간 포맷팅
                    if col in ['scheduled_date'] and value:
                        value = value.strftime('%Y-%m-%d')
                    elif col in ['scheduled_time'] and value:
                        value = value.strftime('%H:%M')
                    elif col in ['created_at', 'updated_at'] and value:
                        value = value.strftime('%Y-%m-%d %H:%M:%S')
                    schedule[col] = value
                schedules.append(schedule)
        
        conn.close()  # 연결 종료 추가
        
        return {
            "status": "success",
            "schedules": schedules,
            "count": len(schedules),
            "message": f"{len(schedules)}개의 일정을 찾았습니다."
        }
            
    except Exception as e:
        print(f"[ERROR] 일정 조회 오류: {e}")
        if 'conn' in locals():
            conn.close()
        return {"status": "error", "error": str(e)}

def _add_user_schedule(user_id: str, schedule_data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        # 기존의 SQLAlchemy 방식 대신 psycopg2 사용
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST'),
            port=os.getenv('POSTGRES_PORT', '5432'), 
            database=os.getenv('POSTGRES_DB'),
            user=os.getenv('POSTGRES_USER'),
            password=os.getenv('POSTGRES_PASSWORD')
        )
        
        title = schedule_data.get("title", "").strip().strip('"')
        if not title:
            return {"status": "error", "error": "일정 제목은 필수입니다."}
        
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_schedule 
                (user_id, title, scheduled_date, scheduled_time, status, category, description, priority)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                user_id,
                title,
                schedule_data.get("scheduled_date"),
                schedule_data.get("scheduled_time"),
                schedule_data.get("status", "pending"),
                schedule_data.get("category", "general"),
                schedule_data.get("description", ""),
                schedule_data.get("priority", "medium")
            ))
            
            new_id = cur.fetchone()[0]
            conn.commit()
            
        conn.close()
        
        return {
            "status": "success",
            "id": new_id,
            "message": f"일정 '{title}'이 추가되었습니다."
        }
        
    except Exception as e:
        print(f"[ERROR] 일정 추가 오류: {e}")
        return {"status": "error", "error": str(e)}

def _update_user_schedule(schedule_data: Dict[str, Any]) -> Dict[str, Any]:
    """기존 일정 수정"""
    try:
        conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST'),
        port=os.getenv('POSTGRES_PORT', '5432'), 
        database=os.getenv('POSTGRES_DB'),
        user=os.getenv('POSTGRES_USER'),
        password=os.getenv('POSTGRES_PASSWORD')
        )
        
        schedule_id = schedule_data.get("id")
        if not schedule_id:
            return {"status": "error", "error": "일정 ID가 필요합니다."}
        
        # 업데이트할 필드들 동적으로 구성
        update_fields = []
        params = {"id": schedule_id}
        
        for field in ["title", "scheduled_date", "scheduled_time", "status", "category", "description", "priority"]:
            if field in schedule_data:
                value = schedule_data[field]
                
                # 날짜/시간 처리
                if field == "scheduled_date" and isinstance(value, str):
                    try:
                        value = datetime.strptime(value, '%Y-%m-%d').date()
                    except ValueError:
                        continue
                elif field == "scheduled_time" and isinstance(value, str):
                    try:
                        value = datetime.strptime(value, '%H:%M').time()
                    except ValueError:
                        continue
                
                update_fields.append(f"{field} = :{field}")
                params[field] = value
        
        if not update_fields:
            return {"status": "error", "error": "업데이트할 필드가 없습니다."}
        
        # updated_at 자동 업데이트
        update_fields.append("updated_at = NOW()")
        
        with conn.cursor() as cur:
            query = f"""
                UPDATE user_schedule 
                SET {', '.join(update_fields)}
                WHERE id = %s
                RETURNING title
            """
            
            # 파라미터 순서 조정 필요
            values = [params[field.split(' = ')[0]] for field in update_fields if ' = ' in field]
            values.append(schedule_id)
            
            cur.execute(query, values)
            result = cur.fetchone()
            conn.commit()
            
            updated_row = result.fetchone()
            if updated_row:
                title = updated_row[0]
                return {
                    "status": "success",
                    "message": f"일정 '{title}'이 수정되었습니다."
                }
            else:
                return {"status": "error", "error": "일정을 찾을 수 없습니다."}
                
    except Exception as e:
        print(f"[ERROR] 일정 수정 오류: {e}")
        return {"status": "error", "error": str(e)}

def _delete_user_schedule(schedule_id: int) -> Dict[str, Any]:
    """일정 삭제"""
    try:
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST'),
            port=os.getenv('POSTGRES_PORT', '5432'), 
            database=os.getenv('POSTGRES_DB'),
            user=os.getenv('POSTGRES_USER'),
            password=os.getenv('POSTGRES_PASSWORD')
        )

        with conn.cursor() as cur:
            cur.execute("SELECT title FROM user_schedule WHERE id = %s", (schedule_id,))
            row = cur.fetchone()
            
            cur.execute("DELETE FROM user_schedule WHERE id = %s", (schedule_id,))
            conn.commit()
                    
    except Exception as e:
        print(f"[ERROR] 일정 삭제 오류: {e}")
        return {"status": "error", "error": str(e)}

def _complete_user_schedule(schedule_id: int) -> Dict[str, Any]:
    """일정 완료 처리"""
    try:
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST'),
            port=os.getenv('POSTGRES_PORT', '5432'), 
            database=os.getenv('POSTGRES_DB'),
            user=os.getenv('POSTGRES_USER'),
            password=os.getenv('POSTGRES_PASSWORD')
        )

        with conn.cursor() as cur:
            cur.execute("""
                UPDATE user_schedule 
                SET status = 'completed', updated_at = NOW()
                WHERE id = %s
                RETURNING title
            """, (schedule_id,))
            
            result = cur.fetchone()
            conn.commit()
            
            updated_row = result.fetchone()
            if updated_row:
                title = updated_row[0]
                return {
                    "status": "success",
                    "message": f"일정 '{title}'이 완료되었습니다."
                }
            else:
                return {"status": "error", "error": "일정을 찾을 수 없습니다."}
                
    except Exception as e:
        print(f"[ERROR] 일정 완료 처리 오류: {e}")
        return {"status": "error", "error": str(e)}

def _sync_memo_with_db(user_id: str, user_memo: Dict[str, Any] = None) -> Dict[str, Any]:
    """메모와 DB 동기화"""
    try:
        if not user_memo:
            return {"status": "error", "error": "메모 데이터가 없습니다."}
        
        # DB에서 최신 일정 조회
        db_schedules = _get_user_schedules(user_id, limit=50)
        
        if db_schedules["status"] == "success":
            # 메모의 schedule 캐시 업데이트
            schedule_info = user_memo.get("schedule", {})
            schedule_info["cache"] = db_schedules["schedules"]
            schedule_info["last_sync"] = datetime.now().isoformat()
            
            return {
                "status": "success",
                "message": "메모와 DB 동기화가 완료되었습니다.",
                "sync_count": db_schedules["count"],
                "last_sync": schedule_info["last_sync"]
            }
        else:
            return db_schedules
            
    except Exception as e:
        print(f"[ERROR] 동기화 오류: {e}")
        return {"status": "error", "error": str(e)}