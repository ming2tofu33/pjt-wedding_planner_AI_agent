# state.py
from langgraph.graph import MessagesState
from typing import Dict, Any, List

class State(MessagesState):
    """웨딩 챗봇 상태 - MessagesState 기반으로 대화 히스토리 자동 관리"""
    
    # 누적 메모 (대화할 때마다 업데이트) - 일정 관리 추가
    memo: Dict[str, Any] = {
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
        "changes": [],
        "schedule": {                   # 일정 관리 추가
            "sync_with_db": True,      # DB와 동기화 여부
            "last_sync": "",           # 마지막 동기화 시간
            "cache": []                # 임시 캐시 (성능용)
        }
    }
    
    # 매번 새로 설정되는 필드들
    intent: str = ""
    tools_needed: List[str] = []
    tool_results: Dict[str, Any] = {}
    
    # memo_check_node에서 사용할 새로운 필드
    enhanced_context: str = ""
    memo_insights: Dict[str, Any] = {}