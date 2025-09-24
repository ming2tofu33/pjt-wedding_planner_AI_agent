from langgraph.graph import MessagesState
from typing import Dict, Any, List

class State(MessagesState):
    """웨딩 챗봇 상태 - MessagesState 기반으로 대화 히스토리 자동 관리"""
    
    # 누적 메모 (대화할 때마다 업데이트) - 기본값 설정
    memo: Dict[str, Any] = {
        "budget": "",
        "preferred_location": "",
        "wedding_date": "",
        "style": "",
        "confirmed_vendors": {},
        "notes": []
    }
    
    # 매번 새로 설정되는 필드들 - 기본값 설정
    intent: str = ""  # "wedding" or "general"
    tools_needed: List[str] = []  # ["db_query", "calculator", "web_search"] 등
    tool_results: Dict[str, Any] = {}  # 툴 실행 결과