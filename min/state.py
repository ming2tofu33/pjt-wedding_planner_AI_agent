# state.py
"""
LangGraph 기반 AI 웨딩플래너 에이전트의 완전한 상태 정의
- 모든 노드에서 사용하는 필드들을 통합
- 타입 안정성 보장
- 메모리 관리 및 툴 실행 결과 포함
"""
from langgraph.graph import MessagesState
from typing import Optional, List, Dict, Any, Literal, Union
from typing import TypedDict
from typing_extensions import Annotated
from operator import add
from datetime import datetime
import os

# ============= 기본 타입 정의 =============

class UserProfile(TypedDict):
    """사용자 기본 프로필 (모든 금액: '만원' 단위 정수)"""
    user_id: str                              # 필수: 고유 식별자
    wedding_date: Optional[str]               # ISO 날짜, 예: "2026-05-30"
    total_budget_manwon: Optional[int]        # 총 예산(만원)
    guest_count: Optional[int]                # 하객 수
    preferred_locations: List[str]            # 선호 지역 키워드

class UserMemo(TypedDict):
    """장기 메모 컨테이너 (JSON 저장 대상)"""
    profile: UserProfile                      # 필수: 사용자 프로필
    version: str                              # 필수: 스키마 버전
    conversation_summary: Optional[str]       # 최근 요약본

class ToolResult(TypedDict):
    """개별 툴 실행 결과"""
    tool_name: str                           # 실행된 툴 이름
    success: bool                            # 성공 여부
    output: Optional[Any]                    # 성공 시 결과
    error: Optional[str]                     # 실패 시 에러 메시지

# ============= 메인 State 클래스 =============

class State(MessagesState):
    # 0) 식별/메모
    user_id: Optional[str] = None
    user_memo: Optional[UserMemo] = None
    memo_file_path: Optional[str] = None         # 예: ./memories/user_{id}_memo.json
    memo_needs_update: bool = False
    
    # 1) 입력/파싱 결과
    user_input: Optional[str] = None
    vendor_type: Optional[str] = None            # 'wedding_hall'|'studio'|'wedding_dress'|'makeup'
    region_keyword: Optional[str] = None         # 예: '강남', '청담', '압구정'
    limit: int = 5
    
    # 2) 라우팅 힌트/의사결정
    intent_hint: Optional[Literal["recommend", "tool", "general"]] = None
    routing_decision: Optional[Literal["tool_execution", "general_response", "recommendation"]] = None
    
    # 3) 실행 계획(선택)
    sql: Optional[str] = None
    
    # 4) 툴/DB 결과
    tools_to_execute: Annotated[List[str], add] = []
    rows: Annotated[List[Dict[str, Any]], add] = []   # DB 결과 레코드
    
    # 5) 응답 생성
    response_content: Optional[str] = None
    answer: Optional[str] = None
    conversation_summary: Optional[str] = None
    suggestions: Annotated[List[str], add] = []
    quick_replies: Annotated[List[str], add] = []
    
    # 6) 상태/에러/추적
    status: Literal["ok", "empty", "error"] = "ok"
    reason: Optional[str] = None
    error_info: Optional[Dict[str, Any]] = None
    processing_timestamp: Optional[str] = None  # ISO 문자열로 저장
    
    # ---------- 메모리 접근 프로퍼티 (데이터 일관성 보장) ----------
    @property
    def total_budget_manwon(self) -> Optional[int]:
        """총 예산 접근 (메모리에서 직접 읽기)"""
        if not self.get("user_memo"):
            return None
        return self["user_memo"]["profile"]["total_budget_manwon"]
    
    @total_budget_manwon.setter
    def total_budget_manwon(self, value: Optional[int]):
        """총 예산 설정 (메모리 동기화)"""
        memo_set_budget(self, value)
    
    @property
    def wedding_date(self) -> Optional[str]:
        """결혼 날짜 접근 (메모리에서 직접 읽기)"""
        if not self.get("user_memo"):
            return None
        return self["user_memo"]["profile"]["wedding_date"]
    
    @wedding_date.setter
    def wedding_date(self, value: Optional[str]):
        """결혼 날짜 설정 (메모리 동기화)"""
        memo_set_wedding_date(self, value)

# ---------- (선택) 편의 유틸 ----------
def memo_set_budget(state: State, manwon: Optional[int]) -> None:
    """State와 메모 모두에 예산(만원)을 반영."""
    if state.get("user_memo") is None:
        if state.get("user_id") is None:
            return
        state["user_memo"] = create_empty_user_memo(state["user_id"])
    state["user_memo"]["profile"]["total_budget_manwon"] = manwon
    state["memo_needs_update"] = True

def memo_set_wedding_date(state: State, date_iso: Optional[str]) -> None:
    """State와 메모 모두에 결혼일(ISO)을 반영."""
    if state.get("user_memo") is None:
        if state.get("user_id") is None:
            return
        state["user_memo"] = create_empty_user_memo(state["user_id"])
    state["user_memo"]["profile"]["wedding_date"] = date_iso
    state["memo_needs_update"] = True

def touch_processing_timestamp(state: State) -> None:
    """처리 시작 타임스탬프를 ISO 문자열로 기록."""
    state["processing_timestamp"] = datetime.now().isoformat(timespec="seconds")


# ============= 유틸리티 함수들 =============

def create_empty_user_memo(user_id: str) -> UserMemo:
    """신규 사용자 초기 메모 생성 (만원 단위 규칙 적용)"""
    return UserMemo(
        profile=UserProfile(
            user_id=user_id,
            wedding_date=None,
            total_budget_manwon=None,
            guest_count=None,
            preferred_locations=[],
        ),
        conversation_summary=None,
        version="1.0",
    )

def get_memo_file_path(user_id: str) -> str:
    """사용자 메모리 파일 경로 생성"""
    memories_dir = "memories"
    if not os.path.exists(memories_dir):
        os.makedirs(memories_dir)
    return os.path.join(memories_dir, f"user_{user_id}_memo.json")

def touch_processing_timestamp(state: State) -> None:
    """처리 시작 타임스탬프를 ISO 문자열로 기록"""
    state['processing_timestamp'] = datetime.now().isoformat(timespec="seconds")

def memo_set_budget(state: State, manwon: Optional[int]) -> None:
    """State와 메모 모두에 예산(만원)을 반영"""
    if state.get('user_memo') is None:
        if state.get('user_id') is None:
            return
        state['user_memo'] = create_empty_user_memo(state['user_id'])
    
    state['user_memo']['profile']['total_budget_manwon'] = manwon
    state['total_budget_manwon'] = manwon  # 빠른 접근용
    state['memo_needs_update'] = True

def memo_set_wedding_date(state: State, date_iso: Optional[str]) -> None:
    """State와 메모 모두에 결혼일(ISO)을 반영"""
    if state.get('user_memo') is None:
        if state.get('user_id') is None:
            return
        state['user_memo'] = create_empty_user_memo(state['user_id'])
    
    state['user_memo']['profile']['wedding_date'] = date_iso
    state['wedding_date'] = date_iso  # 빠른 접근용
    state['memo_needs_update'] = True

def memo_set_guest_count(state: State, count: Optional[int]) -> None:
    """State와 메모 모두에 하객 수를 반영"""
    if state.get('user_memo') is None:
        if state.get('user_id') is None:
            return
        state['user_memo'] = create_empty_user_memo(state['user_id'])
    
    state['user_memo']['profile']['guest_count'] = count
    state['guest_count'] = count  # 빠른 접근용
    state['memo_needs_update'] = True

def initialize_state(user_id: str, user_input: str) -> State:
    """새로운 State 객체 초기화"""
    return State(
        user_id=user_id,
        user_input=user_input,
        status="ok",
        memo_needs_update=False,
        tools_to_execute=[],
        tool_results=[],
        suggestions=[],
        quick_replies=[],
        rows=[],
        messages=[],
        preferred_locations=[],
    )

# ============= 상태 검증 함수들 =============

def validate_state(state: State) -> bool:
    """State 객체의 기본 유효성 검사"""
    required_fields = ['user_id', 'status']
    for field in required_fields:
        if field not in state:
            return False
    return True

def is_error_state(state: State) -> bool:
    """에러 상태인지 확인"""
    return state.get('status') == 'error'

def has_user_memo(state: State) -> bool:
    """사용자 메모가 로드되었는지 확인"""
    return state.get('user_memo') is not None

def get_user_profile(state: State) -> Optional[UserProfile]:
    """사용자 프로필 가져오기"""
    memo = state.get('user_memo')
    if memo:
        return memo.get('profile')
    return None

# ============= 기본값 설정 =============

def set_default_values(state: State) -> None:
    """State의 기본값들 설정"""
    if 'status' not in state:
        state['status'] = 'ok'
    if 'memo_needs_update' not in state:
        state['memo_needs_update'] = False
    if 'tools_to_execute' not in state:
        state['tools_to_execute'] = []
    if 'tool_results' not in state:
        state['tool_results'] = []
    if 'suggestions' not in state:
        state['suggestions'] = []
    if 'quick_replies' not in state:
        state['quick_replies'] = []
    if 'rows' not in state:
        state['rows'] = []
    if 'messages' not in state:
        state['messages'] = []
    if 'preferred_locations' not in state:
        state['preferred_locations'] = []
        
