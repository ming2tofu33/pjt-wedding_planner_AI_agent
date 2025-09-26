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
    """사용자 메시지의 의도를 파싱하고 필요한 툴 판단 (개선된 버전)"""
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

웨딩 관련 키워드들:
- 업체: 웨딩홀, 스튜디오(웨딩 촬영), 드레스, 메이크업, 플로리스트, 케이크, 한복
- 장소: 압구정, 강남, 홍대 등 + "스튜디오/웨딩홀" 조합
- 행동: 추천, 찾기, 예약, 견적, 비교, 검색, 웹서치
- 예산: 가격, 비용, 예산, 계산
- 기타: 결혼, 웨딩, 신부, 신랑, 하객

2. 웨딩 관련인 경우 필요한 툴들 (복수 선택 가능):
   
   - db_query: 다음 경우에 사용
     * "추천해줘", "찾아줘" + 업체 유형 (드레스, 웨딩홀, 스튜디오, 메이크업)
     * 지역 + 업체 유형 조합 ("압구정 드레스", "강남 웨딩홀")
     * 예: "청담역 드레스 추천", "강남 웨딩홀 찾아줘"

   - web_search: 다음 경우에 반드시 사용
     * 명시적 검색 요청: "검색", "웹서치", "찾아봐", "알아봐", "정보 알려줘"
     * "찾아줘", "알려줘", "어때", "정보", "후기", "리뷰" 등이 포함된 모든 요청
     * 업체명이나 고유명사가 언급된 경우 (DB에 있든 없든 상관없이)
     * 추천 후 상세정보 요청: "위에서 추천한 업체들", "그 업체들", "3곳 웹서치"
     * 최신 정보: "트렌드", "최근", "요즘", "지금"
     * 연락처/위치 정보: "전화번호", "주소", "위치", "연락처"
   
   - calculator: 예산 계산, 비용 분배, 하객수 계산 등이 필요한 경우  
   
   - memo_update: 사용자 정보를 메모에 저장해야 하는 경우 (예산, 날짜, 선호도 등)

**중요한 판단 기준:**
- "추천해줘" → db_query + web_search (업체 찾기 + 상세정보)
- "찾아줘", "알려줘", "정보", "어때" → web_search 반드시 포함
- 특정 업체/브랜드명 언급 → web_search 반드시 포함
- "그 업체들", "위의 업체들" → web_search (이전 대화 참조)
- 웨딩 관련 질문은 가능하면 web_search도 함께 실행 (더 풍부한 정보 제공)

실제 적용 규칙:
1. "찾아줘", "알려줘", "정보", "어때", "후기", "리뷰" 키워드가 있으면 → web_search 무조건 포함
2. 업체 유형 + "추천해줘" → db_query + web_search 둘 다
3. 계산/예산 관련 → calculator (+ memo_update 필요시)
4. 일반 인사/대화 → general

예시:
"청담역 드레스 3곳 추천해줘" → wedding,db_query,web_search
"메이컵업바이김수 정보 알려줘" → wedding,web_search
"더케네스블랑 어때?" → wedding,web_search
"위의 3곳 업체 웹서치해줘" → wedding,web_search
"드레스 업체 후기 찾아봐" → wedding,web_search
"5000만원 예산 분배해줘" → wedding,calculator,memo_update
"안녕하세요" → general,

답변 형식:
wedding,db_query,web_search (업체 추천 + 상세정보)
wedding,web_search (웹 검색만 필요)
wedding,db_query (DB 검색만 필요)
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
        
        # 키워드 기반 자동 web_search 트리거 (LLM이 놓친 경우를 위한 안전장치)
        if intent == "wedding":
            web_search_triggers = ["찾아줘", "알려줘", "정보", "어때", "후기", "리뷰", "검색", "웹서치"]
            if any(trigger in last_message for trigger in web_search_triggers):
                if "web_search" not in tools_needed:
                    tools_needed.append("web_search")
                    print(f"[DEBUG] 키워드 트리거로 web_search 자동 추가: {last_message}")
        
        print(f"[DEBUG] Intent: {intent}, Tools: {tools_needed}")
        print(f"[DEBUG] Original message: {last_message}")
        print(f"[DEBUG] Previous context: {previous_context[:100]}...")
        
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
    """기존 메모리를 로드하고 상태에 저장 (기존 상태 보존)"""
    user_id = os.getenv('DEFAULT_USER_ID', 'mvp-test-user')
    memo_path = f"./memories/{user_id}.json"
    
    # memories 디렉토리 생성
    os.makedirs("./memories", exist_ok=True)
    
    # 기존 메모 로드
    try:
        if os.path.exists(memo_path):
            with open(memo_path, 'r', encoding='utf-8') as f:
                existing_memo = json.load(f)
            print(f"[DEBUG] 메모리 로드 성공: {existing_memo}")
        else:
            # 기본 메모 구조 생성
            existing_memo = {
                "budget": "",
                "preferred_location": "",
                "wedding_date": "",
                "style": "",
                "confirmed_vendors": {},
                "notes": []
            }
            print(f"[DEBUG] 새로운 메모리 생성")
    except Exception as e:
        print(f"메모리 로드 중 오류: {e}")
        existing_memo = {
            "budget": "",
            "preferred_location": "",
            "wedding_date": "",
            "style": "",
            "confirmed_vendors": {},
            "notes": []
        }
    
    # 기존 상태를 보존하면서 메모만 추가
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
    """사용자 메모리 업데이트 - 대화에서 정보 추출"""
    user_id = os.getenv('DEFAULT_USER_ID', 'mvp-test-user')
    memo_path = f"./memories/{user_id}.json"
    
    # memories 디렉토리 생성
    os.makedirs("./memories", exist_ok=True)
    
    # 현재 사용자 입력
    current_input = state["messages"][-1].content if state["messages"] else ""
    
    # 기존 메모 로드
    try:
        if os.path.exists(memo_path):
            with open(memo_path, 'r', encoding='utf-8') as f:
                existing_memo = json.load(f)
        else:
            existing_memo = {
                "budget": "",
                "preferred_location": "",
                "wedding_date": "",
                "style": "",
                "confirmed_vendors": {},
                "notes": []
            }
    except:
        existing_memo = {
            "budget": "",
            "preferred_location": "",
            "wedding_date": "",
            "style": "",
            "confirmed_vendors": {},
            "notes": []
        }
    
    # LLM으로 사용자 입력에서 정보 추출
    prompt = f"""
현재 메모: {json.dumps(existing_memo, ensure_ascii=False)}
사용자 입력: {current_input}

사용자 입력에서 결혼 준비 관련 정보를 추출해서 메모를 업데이트해주세요.

추출할 정보:
- budget: 예산 관련 정보 (예: "5000만원", "3000만원 정도")
- preferred_location: 선호 지역 (예: "압구정", "강남", "홍대")  
- wedding_date: 결혼 날짜 (예: "2024년 12월", "내년 봄")
- style: 선호 스타일 (예: "모던", "클래식", "빈티지")

변경사항이 없으면 빈 객체 {{}}를 반환하세요.
새로운 정보만 JSON으로 반환하세요.

예시:
입력: "압구정 근처 웨딩홀 찾아요"
출력: {{"preferred_location": "압구정"}}

입력: "예산은 5000만원 정도 생각해요"  
출력: {{"budget": "5000만원"}}

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
                if key in existing_memo and value and value != existing_memo.get(key, ""):
                    existing_memo[key] = value
                    if "notes" not in existing_memo:
                        existing_memo["notes"] = []
                    existing_memo["notes"].append({
                        "timestamp": current_time,
                        "update": f"{key} updated to: {value}"
                    })
                    updated = True
            
            # 업데이트된 경우에만 파일 저장
            if updated:
                with open(memo_path, 'w', encoding='utf-8') as f:
                    json.dump(existing_memo, f, ensure_ascii=False, indent=2)
                print(f"[DEBUG] 메모 파일 저장 완료")
        
        return {
            "memo": existing_memo
        }
        
    except Exception as e:
        print(f"메모 업데이트 중 오류: {e}")
        return {
            "memo": existing_memo
        }
    
def response_generation_node(state: State) -> Dict[str, Any]:
    """툴 실행 결과를 바탕으로 최종 응답 생성"""
    
    last_message = state["messages"][-1].content
    tool_results_text = ""
    
    # 툴 실행 결과 정리
    for tool_name, result in state["tool_results"].items():
        tool_results_text += f"\n{tool_name}: {result.get('result', result)}"
    
    # 메모리 정보
    memo_text = f"사용자 정보: {json.dumps(state['memo'], ensure_ascii=False, indent=2)}"
    
    # 최종 응답 생성
    prompt = f"""
    사용자의 웨딩 관련 질문에 친근하고 도움이 되는 답변을 해주세요.
    
    사용자 질문: {last_message}
    
    툴 실행 결과: {tool_results_text}
    
    {memo_text}
    
    위 정보를 바탕으로 자연스럽고 유용한 답변을 생성해주세요.
    """
    
    response = llm.invoke([HumanMessage(content=prompt)])
    
    # 새로운 메시지 리스트 생성
    new_messages = state["messages"] + [AIMessage(content=response.content)]
    
    return {
        "messages": new_messages
    }

def general_response_node(state: State) -> Dict[str, Any]:
    """메모리 정보를 활용한 일반적인 대화 응답 생성"""
    
    last_message = state["messages"][-1].content
    memo = state.get("memo", {})
    
    # 메모리 정보를 텍스트로 정리
    memo_context = ""
    if memo:
        context_parts = []
        if memo.get("budget"):
            context_parts.append(f"예산: {memo['budget']}")
        if memo.get("preferred_location"):
            context_parts.append(f"선호 지역: {memo['preferred_location']}")
        if memo.get("wedding_date"):
            context_parts.append(f"결혼 날짜: {memo['wedding_date']}")
        if memo.get("style"):
            context_parts.append(f"선호 스타일: {memo['style']}")
        if memo.get("confirmed_vendors"):
            vendors = list(memo['confirmed_vendors'].keys())
            if vendors:
                context_parts.append(f"확정된 업체: {', '.join(vendors)}")
        
        if context_parts:
            memo_context = f"\n\n사용자 정보: {', '.join(context_parts)}"
    
    prompt = f"""
    사용자와 자연스러운 대화를 나눠주세요. 
    웨딩 플래너 챗봇 '마리'로서 친근하고 도움이 되는 답변을 해주세요.
    
    사용자 메시지: {last_message}
    {memo_context}
    
    위의 사용자 정보가 있다면 이를 자연스럽게 활용해서 개인화된 답변을 해주세요.
    예를 들어, 예산이나 지역 정보가 있다면 그에 맞는 조언을 포함할 수 있습니다.
    
    친근하고 자연스러운 답변을 해주세요.
    """
    
    response = llm.invoke([HumanMessage(content=prompt)])
    
    # 새로운 메시지 리스트 생성
    new_messages = state["messages"] + [AIMessage(content=response.content)]
    
    return {
        "messages": new_messages
    }