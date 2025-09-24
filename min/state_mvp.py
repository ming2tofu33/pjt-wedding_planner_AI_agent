from typing import Optional, List, Dict, Any, Literal
from typing import TypedDict
from typing_extensions import Annotated
from operator import add
from datetime import datetime
from langgraph.graph import MessagesState
import os

# ---------- MVP 설정 ----------
MVP_DEFAULT_USER_ID = "mvp_user_001"  # MVP 단계에서 사용할 고정 사용자 ID

# ---------- Long-term Memory ----------
class UserProfile(TypedDict):
    """
    사용자 기본 프로필 (모든 금액: '만원' 단위 정수)
    """
    user_id: str                              # 필수: 고유 식별자
    wedding_date: Optional[str]               # ISO 날짜, 예: "2026-05-30"
    total_budget_manwon: Optional[int]        # 총 예산(만원)
    guest_count: Optional[int]                # 하객 수
    preferred_locations: List[str]            # 선호 지역 키워드

class UserMemo(TypedDict):
    """
    장기 메모 컨테이너 (JSON 저장 대상)
    """
    profile: UserProfile                      # 필수: 사용자 프로필
    version: str                              # 필수: 스키마 버전
    conversation_summary: Optional[str]       # 최근 요약본

def create_empty_user_memo(user_id: str) -> UserMemo:
    """신규 사용자 초기 메모 생성 (만원 단위 규칙 적용)."""
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

def ensure_user_id(state: "State") -> str:
    """
    MVP용 user_id 보장 함수
    - State에 user_id가 없으면 MVP 기본값 설정
    - 대화 연속성을 위해 항상 동일한 ID 반환
    """
    if not state.get("user_id"):
        state["user_id"] = MVP_DEFAULT_USER_ID
    return state["user_id"]

# ---------- 메인 State (MessagesState 상속: 대화 기록 자동 관리) ----------
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
    user_id = ensure_user_id(state)  # user_id 보장
    if state.get("user_memo") is None:
        state["user_memo"] = create_empty_user_memo(user_id)
    state["user_memo"]["profile"]["total_budget_manwon"] = manwon
    state["memo_needs_update"] = True

def memo_set_wedding_date(state: State, date_iso: Optional[str]) -> None:
    """State와 메모 모두에 결혼일(ISO)을 반영."""
    user_id = ensure_user_id(state)  # user_id 보장
    if state.get("user_memo") is None:
        state["user_memo"] = create_empty_user_memo(user_id)
    state["user_memo"]["profile"]["wedding_date"] = date_iso
    state["memo_needs_update"] = True

def touch_processing_timestamp(state: State) -> None:
    """처리 시작 타임스탬프를 ISO 문자열로 기록."""
    state["processing_timestamp"] = datetime.now().isoformat(timespec="seconds")