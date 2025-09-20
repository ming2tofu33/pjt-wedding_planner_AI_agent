# state.py (MVP)
from typing import Optional, List, Dict, Any, Literal
from typing_extensions import Annotated
from operator import add
from langgraph.graph import MessagesState

# ---------- Memory schemas (재사용) ----------
class UserProfile(Dict[str, Any]):
    """name, wedding_date(ISO), total_budget(KRW), guest_count, partner_name"""
    pass

class UserPreferences(Dict[str, Any]):
    """style_preferences: List[str], location_preferences: List[str], priority_factors: List[str]"""
    pass

class UserMemo(Dict[str, Any]):
    """
    profile: UserProfile
    preferences: UserPreferences
    confirmed_bookings: List[Dict[str,str]]
    search_history: List[Dict[str,str]]
    conversation_summary: Optional[str]
    """
    pass

class ErrorInfo(Dict[str, Any]):
    """error_type, error_message, node_name, recovery_action, timestamp"""
    pass

# ---------- Intent (축소형) ----------
IntentCategory = Literal["search_request", "calculation", "general_chat", "recommendation"]
class Intent(Dict[str, Any]):
    """intent(str), entities(dict), confidence(float), intent_category(IntentCategory)"""
    pass

# ---------- Main State ----------
class State(MessagesState):
    # 기본 대화(messages)는 MessagesState가 관리

    # 식별/메모
    user_id: Optional[str] = None
    user_memo: Optional[UserMemo] = None

    # 입력/파싱
    user_input: Optional[str] = None
    parsed_intent: Optional[Intent] = None
    # 간단 파라미터 (parsing_node가 채움)
    vendor_type: Optional[str] = None          # 'hall'|'studio'|'dress'|'makeup'
    region_keyword: Optional[str] = None       # 예: '강남'
    limit: int = 5
    intent_hint: Optional[Literal["recommend","tool","general"]] = None

    # 라우팅
    routing_decision: Optional[Literal["tool_execution","general_response","recommendation"]] = None
    tools_to_execute: List[str] = []           # 예: ["db_query_tool"]
    
    # 툴 결과 (누적 가능)
    tool_results: Annotated[List[Dict[str, Any]], add] = []

    # 응답 생성
    response_content: Optional[str] = None
    final_response: Optional[str] = None

    # 상태/에러
    status: Literal["ok","empty","error"] = "ok"
    reason: Optional[str] = None
    error_info: Optional[ErrorInfo] = None
