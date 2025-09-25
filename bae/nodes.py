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

# OpenAI 모델 초기화
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.1,
    api_key=os.getenv('OPENAI_API_KEY')
)

def parsing_node(state) -> Dict[str, Any]:
    """사용자 메시지의 의도를 파싱하고 필요한 툴 판단"""
    
    last_message = state["messages"][-1].content if state["messages"] else ""
    memo = state.get("memo", {})
    
    prompt = f"""
메시지: {last_message}
현재 메모: {json.dumps(memo, ensure_ascii=False)}

다음을 판단해주세요:

1. 의도: wedding(결혼 준비 관련) 또는 general(일반 대화)

웨딩 관련 키워드들:
- 업체: 웨딩홀, 스튜디오(웨딩 촬영), 드레스, 메이크업, 플로리스트, 케이크, 한복
- 장소: 압구정, 강남, 홍대 등 + "스튜디오/웨딩홀" 조합
- 행동: 추천, 찾기, 예약, 견적, 비교
- 예산: 가격, 비용, 예산, 계산
- 기타: 결혼, 웨딩, 신부, 신랑, 하객

2. 웨딩 관련인 경우 필요한 툴들:
   - db_query: 웨딩홀, 스튜디오, 드레스, 메이크업 업체 검색이 필요한 경우
   - calculator: 예산 계산, 비용 분배, 하객수 계산 등이 필요한 경우  
   - web_search: 최신 웨딩 트렌드, 리뷰, 팁 등 웹에서 정보를 찾아야 하는 경우
   - memo_update: 사용자 정보를 메모에 저장해야 하는 경우 (예산, 날짜, 선호도 등)

예시:
"압구정 스튜디오 추천" → wedding,db_query
"5000만원 예산 분배" → wedding,calculator,memo_update  
"웨딩 트렌드 알려줘" → wedding,web_search
"안녕하세요" → general,

답변 형식:
wedding,db_query (업체 검색만 필요)
wedding,calculator,memo_update (계산 + 메모 저장)
wedding,web_search (웹 검색만 필요)
wedding, (툴 불필요, 단순 질문)
general, (일반 대화)

답변:
"""
    
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        parts = response.content.strip().split(',')
        
        intent = "wedding" if "wedding" in parts[0].lower() else "general"
        
        # 툴들 추출 (여러 개 가능)
        tools_needed = []
        if len(parts) > 1:
            for i in range(1, len(parts)):
                tool = parts[i].strip()
                if tool and tool in ["db_query", "calculator", "web_search", "memo_update"]:
                    tools_needed.append(tool)
        
        print(f"[DEBUG] Intent: {intent}, Tools: {tools_needed}")
        
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
    """사용자 메모리 JSON 파일 업데이트"""
    
    user_id = os.getenv('DEFAULT_USER_ID', 'mvp-test-user')
    memo_path = f"./memories/{user_id}.json"
    
    # memories 디렉토리 생성
    os.makedirs("./memories", exist_ok=True)
    
    # 안전하게 memo 가져오기
    current_memo = state.get("memo", {})
    if current_memo:
        current_memo = current_memo.copy()
    else:
        current_memo = {}
    
    try:
        # 기존 메모리 로드
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
        
        # 새로운 정보가 있으면 업데이트하고 타임스탬프 추가
        updated = False
        current_time = datetime.now().isoformat()
        
        # current_memo와 기존 메모를 병합
        for key, value in current_memo.items():
            if value and value != existing_memo.get(key, ""):
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
            print(f"[DEBUG] 메모 업데이트 완료: {updated}")
        
        return {
            "memo": existing_memo
        }
        
    except Exception as e:
        print(f"메모 업데이트 중 오류: {e}")
        # 에러 시에도 기본 구조 반환
        default_memo = {
            "budget": "",
            "preferred_location": "",
            "wedding_date": "",
            "style": "",
            "confirmed_vendors": {},
            "notes": []
        }
        return {
            "memo": current_memo if current_memo else default_memo
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
    """일반적인 대화 응답 생성"""
    
    last_message = state["messages"][-1].content
    
    prompt = f"""
    사용자와 자연스러운 대화를 나눠주세요. 웨딩 플래너 챗봇이지만 일반적인 질문에도 친근하게 답변해주세요.
    
    사용자 메시지: {last_message}
    
    간단하고 자연스러운 답변을 해주세요.
    """
    
    response = llm.invoke([HumanMessage(content=prompt)])
    
    # 새로운 메시지 리스트 생성
    new_messages = state["messages"] + [AIMessage(content=response.content)]
    
    return {
        "messages": new_messages
    }