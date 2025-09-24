import os
import json
from datetime import datetime
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage
from state import State
from dotenv import load_dotenv

load_dotenv()

# OpenAI 모델 초기화
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.1,
    api_key=os.getenv('OPENAI_API_KEY')
)

def parsing_node(state: State) -> Dict[str, Any]:
    """사용자 메시지의 의도를 파싱하여 intent 설정"""
    
    # 최근 메시지 가져오기
    last_message = state["messages"][-1].content if state["messages"] else ""
    
    # LLM을 사용한 의도 분류
    prompt = f"""
    다음 메시지가 웨딩 관련 질문인지 일반 대화인지 분류해주세요.
    
    메시지: {last_message}
    
    웨딩 관련이면 "wedding", 일반 대화면 "general"로만 답변해주세요.
    """
    
    response = llm.invoke([HumanMessage(content=prompt)])
    intent = response.content.strip().lower()
    
    # intent 정규화
    if "wedding" in intent:
        intent = "wedding"
    else:
        intent = "general"
    
    return {
        "intent": intent,
        "tools_needed": [],  # 초기화
        "tool_results": {}
    }

def tool_execution_node(state: State) -> Dict[str, Any]:
    """필요한 툴들을 순차적으로 실행"""
    
    from tools import execute_tools
    
    # 사용자의 최근 메시지 가져오기
    last_message = state["messages"][-1].content if state["messages"] else ""
    
    # 실제 툴 실행
    tool_results = execute_tools(
        tools_needed=state["tools_needed"],
        user_message=last_message,
        user_memo=state["memo"]
    )
    
    return {
        "tool_results": tool_results
    }

def memo_update_node(state: State) -> Dict[str, Any]:
    """사용자 메모리 JSON 파일 업데이트"""
    
    user_id = os.getenv('DEFAULT_USER_ID', 'mvp-test-user')
    memo_path = f"./memories/{user_id}.json"
    
    # memories 디렉토리 생성
    os.makedirs("./memories", exist_ok=True)
    
    current_memo = state["memo"].copy()
    
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
        
        return {
            "memo": existing_memo
        }
        
    except Exception as e:
        print(f"메모 업데이트 중 오류: {e}")
        return {
            "memo": current_memo
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