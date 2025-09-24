from state import State

def conditional_router(state: State) -> str:
    """tools_needed 결정 후 라우팅"""
    
    # 웨딩 관련이면 툴이 필요할 가능성이 높음
    if state["intent"] == "wedding":
        # 최근 메시지 안전하게 가져오기
        try:
            last_message = state["messages"][-1].content if state["messages"] else ""
            # 디버깅: 메시지 타입 확인
            print(f"[DEBUG] last_message type: {type(last_message)}")
            print(f"[DEBUG] last_message value: {last_message}")
            
            # 문자열인지 확인 후 처리
            if isinstance(last_message, str):
                last_message_lower = last_message.lower()
            else:
                print(f"[ERROR] last_message is not string: {type(last_message)}")
                return "general_response"
                
        except Exception as e:
            print(f"[ERROR] Error getting message: {e}")
            return "general_response"
        
        tools_needed = []
        
        # 키워드 기반으로 필요한 툴 결정
        if any(keyword in last_message_lower for keyword in ["홀", "드레스", "메이크업", "스튜디오", "업체", "추천"]):
            tools_needed.append("db_query")
        
        if any(keyword in last_message_lower for keyword in ["계산", "예산", "비용", "가격"]):
            tools_needed.append("calculator")
            
        if any(keyword in last_message_lower for keyword in ["검색", "알아봐", "찾아봐"]):
            tools_needed.append("web_search")
        
        # state에 tools_needed 설정
        state["tools_needed"] = tools_needed
        
        if tools_needed:
            return "tool_execution"
        else:
            return "general_response"
    else:
        # 일반 대화는 바로 general_response로
        state["tools_needed"] = []
        return "general_response"