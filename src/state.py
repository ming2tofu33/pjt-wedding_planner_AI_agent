# state.py
from langgraph.graph import MessagesState
from typing import Dict, Any, List

class State(MessagesState):
    """웨딩 챗봇 상태 - MessagesState 기반으로 대화 히스토리 자동 관리"""
    
    # 누적 메모 (대화할 때마다 업데이트) - 새로운 구조
    memo: Dict[str, Any] = {
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
        "type": "",                    # 고객 유형 (시간부족형, 개성추구형, 합리적소비형, 알잘딱깔센형)
        "preferred_locations": [],     # 선호 지역
        "wedding_date": "",           # 웨딩 날짜
        "preferences": [],            # 취향 정보
        "confirmed_vendors": {},      # 예약 확정 업체 정보
        "changes": []                 # 메모 변경 이력
    }
    
    # 매번 새로 설정되는 필드들
    intent: str = ""                  # "wedding" or "general"
    tools_needed: List[str] = []      # ["db_query", "calculator", "web_search"] 등
    tool_results: Dict[str, Any] = {} # 툴 실행 결과
    
    # memo_check_node에서 사용할 새로운 필드
    enhanced_context: str = ""        # 메모 기반으로 보강된 컨텍스트
    memo_insights: Dict[str, Any] = {}  # 메모에서 추출한 인사이트