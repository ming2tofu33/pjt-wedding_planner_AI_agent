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
        with engine.connect() as conn:
            # 트랜잭션 없이 읽기 전용으로 실행
            result = conn.execute(sa.text(sql_query))
            rows = result.fetchall()
            columns = list(result.keys())
            
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
                # DB 쿼리 결과가 있으면 컨텍스트로 전달 (안전한 방식)
                context_data = None
                if "db_query" in results and isinstance(results["db_query"], dict):
                    context_data = {"db_query": results["db_query"]}
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


# 스케줄 관리 툴
def schedule_management_tool(schedule_request: str, user_memo: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    일정 관리 도구 - DB와 연동하여 일정 추가/수정/삭제/조회
    """
    try:
        # schedule_request 처리
        if isinstance(schedule_request, list):
            if schedule_request and isinstance(schedule_request[0], dict) and 'text' in schedule_request[0]:
                actual_request = schedule_request[0]['text']
            else:
                actual_request = str(schedule_request[0]) if schedule_request else ""
        else:
            actual_request = str(schedule_request)
        
        print(f"[DEBUG] 일정 관리 요청: {actual_request}")
        
        # 사용자 ID
        user_id = os.getenv('DEFAULT_USER_ID', 'mvp-test-user')
        
        # LLM으로 일정 요청 분석
        analysis_prompt = f"""
사용자 요청: {actual_request}
현재 메모: {json.dumps(user_memo, ensure_ascii=False) if user_memo else "없음"}

다음 중 어떤 작업인지 판단하고 필요한 정보를 추출해주세요:

1. 일정 조회: "일정 확인", "스케줄 보여줘", "언제 뭐해"
2. 일정 추가: "추가해줘", "등록해줘", "예약", "약속"
3. 일정 수정: "변경", "미루기", "시간 바꿔"
4. 일정 완료: "완료", "끝났어", "했어"
5. 일정 취소: "취소", "삭제"

응답 형식 (JSON):
{{
    "action": "view|add|update|complete|cancel",
    "schedule_info": {{
        "title": "일정 제목",
        "date": "2025-03-15",
        "time": "14:00",
        "category": "venue|dress|photo|makeup|general",
        "priority": "high|medium|low",
        "description": "상세 내용"
    }}
}}

일정 추가 예시:
"내일 드레스 피팅 예약해줘" → {{"action": "add", "schedule_info": {{"title": "드레스 피팅", "date": "2025-01-16", "category": "dress"}}}}
"이번주 일정 확인해줘" → {{"action": "view"}}

JSON만 반환:
"""
        
        analysis_response = llm.invoke([HumanMessage(content=analysis_prompt)])
        schedule_data = json.loads(analysis_response.content.strip())
        
        action = schedule_data.get("action")
        schedule_info = schedule_data.get("schedule_info", {})
        
        # DB 작업 실행
        with engine.connect() as conn:
            if action == "view":
                result = conn.execute(sa.text("""
                    SELECT id, title, scheduled_date, scheduled_time, status, category, priority, description
                    FROM user_schedule 
                    WHERE user_id = :user_id 
                    ORDER BY scheduled_date ASC, scheduled_time ASC
                """), {"user_id": user_id})
                
                schedules = result.fetchall()
                formatted_result = format_schedule_list(schedules)
                
                return {
                    "status": "success",
                    "action": "view",
                    "result": formatted_result,
                    "count": len(schedules)
                }
                
            elif action == "add":
                conn.execute(sa.text("""
                    INSERT INTO user_schedule (user_id, title, scheduled_date, scheduled_time, status, category, priority, description)
                    VALUES (:user_id, :title, :date, :time, :status, :category, :priority, :description)
                """), {
                    "user_id": user_id,
                    "title": schedule_info.get("title", "새 일정"),
                    "date": schedule_info.get("date"),
                    "time": schedule_info.get("time"),
                    "status": "pending",
                    "category": schedule_info.get("category", "general"),
                    "priority": schedule_info.get("priority", "medium"),
                    "description": schedule_info.get("description", "")
                })
                conn.commit()
                
                return {
                    "status": "success",
                    "action": "add",
                    "result": f"'{schedule_info.get('title')}' 일정이 {schedule_info.get('date')}에 추가되었습니다.",
                    "schedule_info": schedule_info
                }
                
            elif action == "complete":
                # 제목으로 일정 찾아서 완료 처리
                conn.execute(sa.text("""
                    UPDATE user_schedule 
                    SET status = 'completed', updated_at = NOW()
                    WHERE user_id = :user_id AND title ILIKE :title AND status != 'completed'
                """), {
                    "user_id": user_id,
                    "title": f"%{schedule_info.get('title', '')}%"
                })
                conn.commit()
                
                return {
                    "status": "success",
                    "action": "complete",
                    "result": f"'{schedule_info.get('title')}' 일정이 완료 처리되었습니다."
                }
                
            elif action == "cancel":
                conn.execute(sa.text("""
                    UPDATE user_schedule 
                    SET status = 'cancelled', updated_at = NOW()
                    WHERE user_id = :user_id AND title ILIKE :title AND status NOT IN ('completed', 'cancelled')
                """), {
                    "user_id": user_id,
                    "title": f"%{schedule_info.get('title', '')}%"
                })
                conn.commit()
                
                return {
                    "status": "success",
                    "action": "cancel",
                    "result": f"'{schedule_info.get('title')}' 일정이 취소되었습니다."
                }
        
        return {
            "status": "success",
            "action": action,
            "result": "일정 관리가 완료되었습니다."
        }
        
    except Exception as e:
        print(f"[ERROR] 일정 관리 오류: {e}")
        return {
            "status": "error",
            "error": str(e),
            "result": f"일정 관리 중 오류가 발생했습니다: {str(e)}"
        }

def format_schedule_list(schedules) -> str:
    """일정 목록을 보기 좋게 포매팅"""
    if not schedules:
        return "등록된 일정이 없습니다."
    
    result = "📅 **현재 일정:**\n\n"
    
    # 상태별로 그룹화
    status_groups = {"pending": [], "in_progress": [], "completed": [], "cancelled": []}
    
    for schedule in schedules:
        status = schedule[4]  # status 컬럼
        status_groups[status].append(schedule)
    
    # 예정 일정
    if status_groups["pending"]:
        result += "**📋 예정:**\n"
        for s in status_groups["pending"]:
            category_icon = get_category_icon(s[5])  # category 컬럼
            time_str = f" {s[3]}" if s[3] else ""  # scheduled_time
            result += f"• {category_icon} {s[1]} - {s[2]}{time_str}\n"  # title, scheduled_date
        result += "\n"
    
    # 진행중 일정
    if status_groups["in_progress"]:
        result += "**⏳ 진행중:**\n"
        for s in status_groups["in_progress"]:
            category_icon = get_category_icon(s[5])
            time_str = f" {s[3]}" if s[3] else ""
            result += f"• {category_icon} {s[1]} - {s[2]}{time_str}\n"
        result += "\n"
    
    # 완료 일정
    if status_groups["completed"]:
        result += "**✅ 완료:**\n"
        for s in status_groups["completed"]:
            category_icon = get_category_icon(s[5])
            result += f"• {category_icon} {s[1]} - {s[2]}\n"
    
    return result

def get_category_icon(category: str) -> str:
    """카테고리별 아이콘 반환"""
    icons = {
        "venue": "🏛️",
        "dress": "👗", 
        "photo": "📸",
        "makeup": "💄",
        "general": "📝"
    }
    return icons.get(category, "📝")

# execute_tools 함수에 추가
def execute_tools(tools_needed: List[str], user_message: str, user_memo: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    필요한 툴들을 실행하는 헬퍼 함수 (일정 관리 툴 추가)
    """
    results = {}
    
    print(f"[DEBUG] 실행할 툴들: {tools_needed}")
    
    for tool_name in tools_needed:
        try:
            print(f"[DEBUG] {tool_name} 툴 실행 시작")
            
            if tool_name == "db_query":
                results[tool_name] = db_query_tool(user_message, user_memo)
                
            elif tool_name == "web_search":
                context_data = None
                if "db_query" in results and isinstance(results["db_query"], dict):
                    context_data = {"db_query": results["db_query"]}
                results[tool_name] = web_search_tool(user_message, context_data)
                
            elif tool_name == "calculator":
                results[tool_name] = calculator_tool(user_message, user_memo)
                
            elif tool_name == "memo_update":
                results[tool_name] = memo_update_tool(json.dumps(user_memo) if user_memo else "{}")
                
            elif tool_name == "schedule_management":  # 새로 추가
                results[tool_name] = schedule_management_tool(user_message, user_memo)
                
            else:
                results[tool_name] = {"status": "error", "error": f"Unknown tool: {tool_name}"}
                
            print(f"[DEBUG] {tool_name} 툴 실행 완료: {results[tool_name].get('status', 'unknown')}")
                
        except Exception as e:
            print(f"[ERROR] {tool_name} 툴 실행 중 오류: {e}")
            results[tool_name] = {"status": "error", "error": str(e)}
    
    return results