import os
import json
from datetime import datetime
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage
from state import State
from tools import execute_tools
from dotenv import load_dotenv

load_dotenv()

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.1,
    api_key=os.getenv('OPENAI_API_KEY')
)

def parsing_node(state) -> Dict[str, Any]:
    """사용자 메시지의 의도를 파싱하고 필요한 툴 판단 (개인정보 키워드 감지 강화)"""
    last_message = state["messages"][-1].content if state["messages"] else ""
    memo = state.get("memo", {})
    
    # 이전 대화에서 언급된 업체명들을 추출 (컨텍스트 활용)
    previous_context = ""
    if len(state["messages"]) > 2:  # 이전 대화가 있다면
        recent_messages = state["messages"][-4:]  # 최근 4개 메시지 확인
        for msg in recent_messages:
            if hasattr(msg, 'content') and msg.content and isinstance(msg.content, str):
                previous_context += msg.content + " "
    
    prompt = f"""
메시지: {last_message}
현재 메모: {json.dumps(memo, ensure_ascii=False)}
최근 대화 컨텍스트: {previous_context}

다음을 판단해주세요:

1. 의도: wedding(결혼 준비 관련) 또는 general(일반 대화)

**중요: 다음 개인정보/메모 관련 키워드가 포함된 경우 무조건 wedding으로 분류하고 memo_update 툴 포함:**
- 개인정보: 이름, 나이, 생년월일, 주소, 직장, 회사, 직업
- 배우자정보: 남편, 아내, 남자친구, 여자친구, 배우자, 신랑, 신부, 파트너
- 예산정보: 예산, 돈, 비용, 가격, 만원, 억, 천만원, 웨딩홀예산, 드레스예산
- 날짜정보: 결혼, 웨딩, 예식일, 날짜, 언제, 몇월, 년도, 결혼날짜
- 지역정보: 살아, 거주, 사는곳, 동네, 구, 시, 지역, 선호지역
- 선호정보: 좋아해, 선호, 취향, 스타일, 타입
- 고객유형: 시간부족, 개성추구, 합리적, 알잘딱깔센

웨딩 관련 키워드들:
- 업체: 웨딩홀, 스튜디오(웨딩 촬영), 드레스, 메이크업, 플로리스트, 케이크, 한복
- 장소: 압구정, 강남, 홍대 등 + "스튜디오/웨딩홀" 조합
- 행동: 추천, 찾기, 예약, 견적, 비교, 검색, 웹서치
- 예산: 가격, 비용, 예산, 계산
- 기타: 결혼, 웨딩, 신부, 신랑, 하객

2. 웨딩 관련인 경우 필요한 툴들 (복수 선택 가능):
   
   - memo_update: 개인정보/메모 관련 키워드가 있으면 **반드시 포함**
   
   - db_query: 다음 경우에 사용
     * "추천해줘", "찾아줘" + 업체 유형 (드레스, 웨딩홀, 스튜디오, 메이크업)
     * 지역 + 업체 유형 조합 ("압구정 드레스", "강남 웨딩홀")

   - web_search: 다음 경우에 반드시 사용
     * 명시적 검색 요청: "검색", "웹서치", "찾아봐", "알아봐", "정보 알려줘"
     * "찾아줘", "알려줘", "어때", "정보", "후기", "리뷰" 등이 포함된 모든 요청
     * 업체명이나 고유명사가 언급된 경우
   
   - calculator: 예산 계산, 비용 분배, 하객수 계산 등이 필요한 경우

예시:
"내 이름은 민아야" → wedding,memo_update
"나는 25살이야" → wedding,memo_update
"우리 예산은 5000만원이야" → wedding,memo_update
"강남에 살아" → wedding,memo_update
"신랑은 회사원이야" → wedding,memo_update
"청담역 드레스 3곳 추천해줘" → wedding,db_query,web_search
"메이컵업바이김수 정보 알려줘" → wedding,web_search
"5000만원 예산 분배해줘" → wedding,calculator,memo_update
"안녕하세요" → general,

답변 형식:
wedding,memo_update (개인정보 저장)
wedding,web_search (웹 검색만 필요)
wedding,db_query,web_search (업체 추천 + 상세정보)
wedding,calculator,memo_update (계산 + 메모 저장)
wedding, (툴 불필요, 단순 질문)
general, (일반 대화)

답변:
"""
    
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        parts = response.content.strip().split(',')
        
        intent = "wedding" if "wedding" in parts[0].lower() else "general"
        
        tools_needed = []
        if len(parts) > 1:
            for i in range(1, len(parts)):
                tool = parts[i].strip()
                if tool and tool in ["db_query", "calculator", "web_search", "memo_update"]:
                    tools_needed.append(tool)
        
        # 개인정보 키워드 강제 감지 (LLM이 놓친 경우를 위한 안전장치)
        personal_info_keywords = [
            "이름", "나이", "살", "생년월일", "주소", "직장", "회사", "직업",
            "남편", "아내", "남자친구", "여자친구", "배우자", "신랑", "신부", "파트너",
            "예산", "만원", "억", "천만원", "결혼날짜", "예식일", "언제", "몇월",
            "살아", "거주", "사는곳", "동네", "좋아해", "선호", "취향", "스타일"
        ]
        
        if any(keyword in last_message for keyword in personal_info_keywords):
            intent = "wedding"
            if "memo_update" not in tools_needed:
                tools_needed.append("memo_update")
                print(f"[DEBUG] 개인정보 키워드 감지로 wedding + memo_update 강제 설정: {last_message}")
        
        # 키워드 기반 자동 web_search 트리거
        if intent == "wedding":
            web_search_triggers = ["찾아줘", "알려줘", "정보", "어때", "후기", "리뷰", "검색", "웹서치"]
            if any(trigger in last_message for trigger in web_search_triggers):
                if "web_search" not in tools_needed:
                    tools_needed.append("web_search")
                    print(f"[DEBUG] 키워드 트리거로 web_search 자동 추가: {last_message}")
        
        print(f"[DEBUG] Intent: {intent}, Tools: {tools_needed}")
        print(f"[DEBUG] Original message: {last_message}")
        
        return {
            "intent": intent,
            "tools_needed": tools_needed,
            "tool_results": {}
        }
        
    except Exception as e:
        print(f"Intent parsing 오류: {e}")
        return {
            "intent": "general",
            "tools_needed": [],
            "tool_results": {}
        }

def memo_check_node(state: State) -> Dict[str, Any]:
    """메모 파일을 로드하고 없으면 새로운 구조로 자동 생성"""
    user_id = os.getenv('DEFAULT_USER_ID', 'mvp-test-user')
    memo_path = f"./memories/{user_id}.json"
    
    # memories 디렉토리 생성
    os.makedirs("./memories", exist_ok=True)
    
    # 현재 사용자 메시지와 파싱된 의도
    current_message = state["messages"][-1].content if state["messages"] else ""
    current_intent = state.get("intent", "")
    tools_needed = state.get("tools_needed", [])
    
    # 새로운 구조의 기본 메모 정의
    default_memo = {
        "name": "",                     # 서비스 이용 고객 이름
        "birthdate": "",               # 고객 생년월일
        "address": "",                 # 고객 주소
        "job": "",                     # 고객 직장
        "spouse": {                    # 고객 배우자 정보
            "name": "",
            "birthdate": "",
            "address": "",
            "job": "",
        },
        "budget": {                    # 예산 정보
            "total": "",
            "wedding_hall": "",
            "wedding_dress": "",
            "studio": "",
            "makeup": "",
            "etc": ""
        },
        "type": "",                    # 고객 유형
        "preferred_locations": [],     # 선호 지역
        "wedding_date": "",           # 웨딩 날짜
        "preferences": [],            # 취향 정보
        "confirmed_vendors": {},      # 예약 확정 업체 정보
        "changes": []                 # 메모 변경 이력
    }
    
    # 메모 파일 로드 또는 생성
    try:
        if os.path.exists(memo_path):
            # 기존 파일 로드
            with open(memo_path, 'r', encoding='utf-8') as f:
                existing_memo = json.load(f)
            print(f"[DEBUG] 기존 메모 파일 로드: {memo_path}")
        else:
            # 파일이 없으면 새로운 구조로 생성
            existing_memo = default_memo.copy()
            with open(memo_path, 'w', encoding='utf-8') as f:
                json.dump(existing_memo, f, ensure_ascii=False, indent=2)
            print(f"[DEBUG] 새 메모 파일 생성 완료: {memo_path}")
            
    except Exception as e:
        print(f"메모 파일 처리 오류: {e}")
        # 오류 시 기본 구조 사용하고 다시 저장 시도
        existing_memo = default_memo.copy()
        try:
            with open(memo_path, 'w', encoding='utf-8') as f:
                json.dump(existing_memo, f, ensure_ascii=False, indent=2)
            print(f"[DEBUG] 오류 후 새 메모 파일 생성 완료")
        except:
            print(f"[ERROR] 메모 파일 생성 실패")
    
    # 기존 상태를 보존하면서 메모만 추가/업데이트
    return {
        "memo": existing_memo
        # intent, tools_needed, tool_results는 그대로 유지됨
    }
    

def tool_execution_node(state: State) -> Dict[str, Any]:
    """필요한 툴들을 실행하고 결과 저장"""
    
    tools_needed = state.get("tools_needed", [])
    
    # 툴이 없으면 빈 결과 반환
    if not tools_needed:
        return {"tool_results": {}}
    
    # 현재 사용자 입력과 메모
    last_message = state["messages"][-1].content if state["messages"] else ""
    memo = state.get("memo", {})
    
    try:
        # tools.py의 execute_tools 함수 사용
        tool_results = execute_tools(
            tools_needed=tools_needed,
            user_message=last_message,
            user_memo=memo
        )
        
        return {"tool_results": tool_results}
        
    except Exception as e:
        print(f"Tool execution 오류: {e}")
        # 에러 시 각 툴별로 에러 결과 생성
        error_results = {}
        for tool_name in tools_needed:
            error_results[tool_name] = {
                "status": "error",
                "error": str(e)
            }
        return {"tool_results": error_results}
    
def memo_update_node(state: State) -> Dict[str, Any]:
    """사용자 메모리 업데이트 - 새로운 메모 구조에 맞게 정보 추출"""
    user_id = os.getenv('DEFAULT_USER_ID', 'mvp-test-user')
    memo_path = f"./memories/{user_id}.json"
    
    # memories 디렉토리 생성
    os.makedirs("./memories", exist_ok=True)
    
    # 현재 사용자 입력
    current_input = state["messages"][-1].content if state["messages"] else ""
    
    # 기존 메모 로드 (새로운 구조)
    try:
        if os.path.exists(memo_path):
            with open(memo_path, 'r', encoding='utf-8') as f:
                existing_memo = json.load(f)
        else:
            existing_memo = {
                "name": "",
                "birthdate": "",
                "address": "",
                "job": "",
                "spouse": {
                    "name": "",
                    "birthdate": "",
                    "address": "",
                    "job": "",
                },
                "budget": {
                    "total": "",
                    "wedding_hall": "",
                    "wedding_dress": "",
                    "studio": "",
                    "makeup": "",
                    "etc": ""
                },
                "type": "",
                "preferred_locations": [],
                "wedding_date": "",
                "preferences": [],
                "confirmed_vendors": {},
                "changes": []
            }
    except:
        existing_memo = {
            "name": "", "birthdate": "", "address": "", "job": "",
            "spouse": {"name": "", "birthdate": "", "address": "", "job": ""},
            "budget": {"total": "", "wedding_hall": "", "wedding_dress": "", "studio": "", "makeup": "", "etc": ""},
            "type": "", "preferred_locations": [], "wedding_date": "", "preferences": [], 
            "confirmed_vendors": {}, "changes": []
        }
    
    # LLM으로 사용자 입력에서 정보 추출 (새로운 구조에 맞게)
    prompt = f"""
현재 메모: {json.dumps(existing_memo, ensure_ascii=False)}
사용자 입력: {current_input}

사용자 입력에서 결혼 준비 관련 정보를 추출해서 메모를 업데이트해주세요.

추출할 정보:
1. 개인정보:
   - name: 본인 이름 (예: "내 이름은 민아야", "저는 김민아예요")
   - birthdate: 생년월일/나이 (예: "25살", "1999년생", "99년생")
   - address: 주소/거주지 (예: "강남에 살아", "압구정 거주")
   - job: 직장/직업 (예: "회사원", "디자이너", "삼성전자 다녀")

2. 배우자정보 (spouse 객체에 저장):
   - spouse.name: 배우자 이름 (예: "남편 이름은 준호야", "신랑은 김준호")
   - spouse.birthdate: 배우자 생년월일/나이
   - spouse.address: 배우자 주소
   - spouse.job: 배우자 직업

3. 예산정보 (budget 객체에 저장):
   - budget.total: 총 예산 (예: "총 5000만원", "전체 예산 1억")
   - budget.wedding_hall: 웨딩홀 예산
   - budget.wedding_dress: 드레스 예산
   - budget.studio: 스튜디오 예산
   - budget.makeup: 메이크업 예산
   - budget.etc: 기타 예산

4. 기타정보:
   - type: 고객 유형 (시간부족형, 개성추구형, 합리적소비형, 알잘딱깔센형)
   - preferred_locations: 선호 지역 배열 (예: ["압구정", "청담"])
   - wedding_date: 웨딩 날짜 (예: "2024년 12월", "내년 봄")
   - preferences: 취향/선호 사항 배열 (예: ["모던스타일", "심플한 디자인"])

변경사항이 없으면 빈 객체 {{}}를 반환하세요.
새로운/변경된 정보만 JSON으로 반환하세요.

예시:
입력: "내 이름은 민아야"
출력: {{"name": "민아"}}

입력: "나는 25살이고 강남에 살아"  
출력: {{"birthdate": "25살", "address": "강남"}}

입력: "신랑은 회사원이고 이름은 준호야"
출력: {{"spouse": {{"name": "준호", "job": "회사원"}}}}

입력: "총 예산은 5000만원이고 웨딩홀에는 2000만원 쓸 예정"
출력: {{"budget": {{"total": "5000만원", "wedding_hall": "2000만원"}}}}

입력: "압구정이나 청담 쪽으로 원해"
출력: {{"preferred_locations": ["압구정", "청담"]}}

JSON만 반환:
"""

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        new_info = json.loads(response.content.strip())
        
        print(f"[DEBUG] 추출된 정보: {new_info}")
        
        # 새로운 정보가 있으면 업데이트
        updated = False
        current_time = datetime.now().isoformat()
        
        if new_info:
            for key, value in new_info.items():
                if key == "spouse" and isinstance(value, dict):
                    # 배우자 정보 업데이트
                    if "spouse" not in existing_memo:
                        existing_memo["spouse"] = {"name": "", "birthdate": "", "address": "", "job": ""}
                    
                    for spouse_key, spouse_value in value.items():
                        if spouse_value and spouse_value != existing_memo["spouse"].get(spouse_key, ""):
                            existing_memo["spouse"][spouse_key] = spouse_value
                            existing_memo["changes"].append({
                                "timestamp": current_time,
                                "update": f"spouse.{spouse_key} updated to: {spouse_value}"
                            })
                            updated = True
                            
                elif key == "budget" and isinstance(value, dict):
                    # 예산 정보 업데이트
                    if "budget" not in existing_memo:
                        existing_memo["budget"] = {"total": "", "wedding_hall": "", "wedding_dress": "", "studio": "", "makeup": "", "etc": ""}
                    
                    for budget_key, budget_value in value.items():
                        if budget_value and budget_value != existing_memo["budget"].get(budget_key, ""):
                            existing_memo["budget"][budget_key] = budget_value
                            existing_memo["changes"].append({
                                "timestamp": current_time,
                                "update": f"budget.{budget_key} updated to: {budget_value}"
                            })
                            updated = True
                            
                elif key == "preferred_locations" and isinstance(value, list):
                    # 선호 지역 배열 업데이트
                    if value != existing_memo.get(key, []):
                        existing_memo[key] = value
                        existing_memo["changes"].append({
                            "timestamp": current_time,
                            "update": f"{key} updated to: {value}"
                        })
                        updated = True
                        
                elif key == "preferences" and isinstance(value, list):
                    # 취향 정보 배열 업데이트
                    if value != existing_memo.get(key, []):
                        existing_memo[key] = value
                        existing_memo["changes"].append({
                            "timestamp": current_time,
                            "update": f"{key} updated to: {value}"
                        })
                        updated = True
                        
                else:
                    # 일반 필드 업데이트 (name, birthdate, address, job, type, wedding_date 등)
                    if key in existing_memo and value and value != existing_memo.get(key, ""):
                        existing_memo[key] = value
                        existing_memo["changes"].append({
                            "timestamp": current_time,
                            "update": f"{key} updated to: {value}"
                        })
                        updated = True
            
            # 업데이트된 경우에만 파일 저장
            if updated:
                with open(memo_path, 'w', encoding='utf-8') as f:
                    json.dump(existing_memo, f, ensure_ascii=False, indent=2)
                print(f"[DEBUG] 새로운 구조로 메모 파일 저장 완료")
        
        return {
            "memo": existing_memo
        }
        
    except Exception as e:
        print(f"메모 업데이트 중 오류: {e}")
        return {
            "memo": existing_memo
        }
        
    
def response_generation_node(state: State) -> Dict[str, Any]:
    """툴 실행 결과를 바탕으로 최종 응답 생성 (새로운 메모 구조 반영)"""
    
    last_message = state["messages"][-1].content
    tool_results_text = ""
    
    # 툴 실행 결과 정리
    for tool_name, result in state["tool_results"].items():
        tool_results_text += f"\n{tool_name}: {result.get('result', result)}"
    
    # 새로운 메모 구조에 맞게 정보 정리
    memo = state.get("memo", {})
    memo_context = ""
    
    if memo:
        context_parts = []
        
        # 개인정보
        if memo.get("name"):
            context_parts.append(f"고객명: {memo['name']}")
        if memo.get("birthdate"):
            context_parts.append(f"나이: {memo['birthdate']}")
        if memo.get("address"):
            context_parts.append(f"거주지: {memo['address']}")
        if memo.get("job"):
            context_parts.append(f"직업: {memo['job']}")
            
        # 배우자 정보
        spouse = memo.get("spouse", {})
        if spouse and any(spouse.values()):
            spouse_info = []
            if spouse.get("name"):
                spouse_info.append(f"이름: {spouse['name']}")
            if spouse.get("job"):
                spouse_info.append(f"직업: {spouse['job']}")
            if spouse_info:
                context_parts.append(f"배우자 정보: {', '.join(spouse_info)}")
        
        # 예산 정보
        budget = memo.get("budget", {})
        if budget and any(budget.values()):
            budget_info = []
            if budget.get("total"):
                budget_info.append(f"총예산: {budget['total']}")
            if budget.get("wedding_hall"):
                budget_info.append(f"웨딩홀: {budget['wedding_hall']}")
            if budget.get("wedding_dress"):
                budget_info.append(f"드레스: {budget['wedding_dress']}")
            if budget.get("studio"):
                budget_info.append(f"스튜디오: {budget['studio']}")
            if budget.get("makeup"):
                budget_info.append(f"메이크업: {budget['makeup']}")
            if budget_info:
                context_parts.append(f"예산: {', '.join(budget_info)}")
        
        # 기타 정보
        if memo.get("type"):
            context_parts.append(f"고객유형: {memo['type']}")
        if memo.get("preferred_locations"):
            context_parts.append(f"선호지역: {', '.join(memo['preferred_locations'])}")
        if memo.get("wedding_date"):
            context_parts.append(f"웨딩날짜: {memo['wedding_date']}")
        if memo.get("preferences"):
            context_parts.append(f"선호사항: {', '.join(memo['preferences'])}")
        if memo.get("confirmed_vendors"):
            vendors = list(memo['confirmed_vendors'].keys())
            if vendors:
                context_parts.append(f"확정업체: {', '.join(vendors)}")
        
        if context_parts:
            memo_context = f"\n\n고객 정보: {' | '.join(context_parts)}"
    
    # 최종 응답 생성
    prompt = f"""
    웨딩 플래너 '마리'로서 사용자의 웨딩 관련 질문에 친근하고 도움이 되는 답변을 해주세요.
    
    사용자 질문: {last_message}
    
    툴 실행 결과: {tool_results_text}
    {memo_context}
    
    위 정보를 바탕으로 개인화되고 유용한 답변을 생성해주세요.
    고객의 예산, 선호지역, 취향 등을 고려해서 맞춤형 조언을 제공하세요.
    """
    
    response = llm.invoke([HumanMessage(content=prompt)])
    
    # 새로운 메시지 리스트 생성
    new_messages = state["messages"] + [AIMessage(content=response.content)]
    
    return {
        "messages": new_messages
    }

def general_response_node(state: State) -> Dict[str, Any]:
    """새로운 메모 구조를 활용한 일반적인 대화 응답 생성"""
    
    last_message = state["messages"][-1].content
    memo = state.get("memo", {})
    
    # 새로운 메모 구조에서 정보 추출
    memo_context = ""
    if memo:
        context_parts = []
        
        # 개인정보 활용
        if memo.get("name"):
            context_parts.append(f"이름: {memo['name']}")
        if memo.get("address"):
            context_parts.append(f"거주지: {memo['address']}")
            
        # 배우자 정보
        spouse = memo.get("spouse", {})
        if spouse and spouse.get("name"):
            context_parts.append(f"배우자: {spouse['name']}")
        
        # 예산 정보 (대화에 활용할 수 있는 수준으로)
        budget = memo.get("budget", {})
        if budget and budget.get("total"):
            context_parts.append(f"웨딩예산: {budget['total']}")
        
        # 기타 웨딩 관련 정보
        if memo.get("wedding_date"):
            context_parts.append(f"웨딩날짜: {memo['wedding_date']}")
        if memo.get("preferred_locations"):
            context_parts.append(f"선호지역: {', '.join(memo['preferred_locations'])}")
        if memo.get("type"):
            context_parts.append(f"고객유형: {memo['type']}")
        if memo.get("preferences"):
            context_parts.append(f"취향: {', '.join(memo['preferences'])}")
        
        # 확정된 업체가 있다면
        if memo.get("confirmed_vendors"):
            vendors = list(memo['confirmed_vendors'].keys())
            if vendors:
                context_parts.append(f"확정업체: {', '.join(vendors)}")
        
        if context_parts:
            memo_context = f"\n\n고객 정보: {' | '.join(context_parts)}"
    
    prompt = f"""
    사용자와 자연스러운 대화를 나눠주세요. 
    웨딩 플래너 챗봇 '마리'로서 친근하고 도움이 되는 답변을 해주세요.
    
    사용자 메시지: {last_message}
    {memo_context}
    
    위의 고객 정보가 있다면 이를 자연스럽게 활용해서 개인화된 답변을 해주세요.
    예를 들어:
    - 이름이 있다면 이름을 불러주세요
    - 예산이나 지역 정보가 있다면 그에 맞는 조언을 포함할 수 있습니다
    - 웨딩 날짜가 가까우면 일정 관련 조언을 할 수 있습니다
    - 고객 유형에 맞는 맞춤형 조언을 제공할 수 있습니다
    
    친근하고 자연스러운 답변을 해주세요.
    """
    
    response = llm.invoke([HumanMessage(content=prompt)])
    
    # 새로운 메시지 리스트 생성
    new_messages = state["messages"] + [AIMessage(content=response.content)]
    
    return {
        "messages": new_messages
    }