# state.py
"""
LangGraph 기반 AI 웨딩플래너 에이전트의 완전한 상태 정의
- 모든 노드에서 사용하는 필드들을 통합
- 타입 안정성 보장
- 메모리 관리 및 툴 실행 결과 포함
"""

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

class State(TypedDict, total=False):
    """
    LangGraph의 메인 상태를 정의하는 TypedDict
    total=False로 모든 필드가 선택적(Optional)
    """
    
    # ===== 기본 식별 정보 =====
    user_id: str                             # 사용자 고유 ID
    user_input: str                          # 원본 사용자 입력
    session_id: Optional[str]                # 세션 ID (선택적)
    
    # ===== 메모리 관리 =====
    user_memo: Optional[UserMemo]            # 사용자 장기 메모리
    memo_file_path: Optional[str]            # 메모리 파일 경로
    memo_needs_update: bool                  # 메모리 업데이트 필요 여부
    memo_load_success: Optional[bool]        # 메모리 로드 성공 여부
    memo_updates_made: Optional[List[Dict]]  # 메모리 업데이트 내역
    
    # ===== 파싱 결과 =====
    intent_hint: Optional[Literal["recommend", "tool", "general"]]  # 의도 힌트
    vendor_type: Optional[str]               # 업체 타입 (wedding_hall, studio, etc.)
    region_keyword: Optional[str]            # 지역 키워드
    update_type: Optional[str]               # 업데이트 타입 (wedding_date, budget, etc.)
    parsing_confidence: Optional[float]      # 파싱 확신도
    raw_llm_response: Optional[Dict[str, Any]]  # 원본 LLM 응답
    
    # ===== 사용자 프로필 필드 (빠른 접근용) =====
    total_budget_manwon: Optional[int]       # 총 예산(만원)
    wedding_date: Optional[str]              # 결혼일
    guest_count: Optional[int]               # 하객 수
    preferred_locations: Annotated[List[str], add]  # 선호 지역들
    
    # ===== 라우팅 및 실행 관리 =====
    routing_decision: Optional[Literal["tool_execution", "general_response", "recommendation", "error_handler"]]
    tools_to_execute: Annotated[List[str], add]  # 실행할 툴 목록
    tool_results: Annotated[List[ToolResult], add]  # 툴 실행 결과들
    tool_execution_log: Optional[Dict[str, Dict]]  # 툴 실행 로그
    
    # ===== 응답 생성 =====
    response_content: Optional[str]          # 핵심 응답 내용
    final_response: Optional[str]            # 최종 포맷팅된 응답
    answer: Optional[str]                    # 답변 (response_content와 유사)
    conversation_summary: Optional[str]      # 대화 요약
    suggestions: Annotated[List[str], add]   # 다음 질문/액션 제안들
    quick_replies: Annotated[List[str], add] # 빠른 답변 버튼들
    
    # ===== 상태 및 에러 관리 =====
    status: Literal["ok", "empty", "error", "handled_error"]  # 처리 상태
    reason: Optional[str]                    # 상태 이유 (에러 메시지 등)
    error_info: Optional[Dict[str, Any]]     # 상세 에러 정보
    recovery_attempted: Optional[bool]       # 복구 시도 여부
    
    # ===== 시스템 추적 =====
    current_node: Optional[str]              # 현재 처리 중인 노드명
    processing_timestamp: Optional[str]      # 처리 시작 시간 (ISO 형식)
    processing_duration: Optional[float]     # 처리 소요 시간 (초)
    
    # ===== 데이터베이스 관련 =====
    sql: Optional[str]                       # 생성된 SQL 쿼리
    rows: Annotated[List[Dict[str, Any]], add]  # DB 조회 결과
    limit: Optional[int]                     # 결과 제한 수
    
    # ===== LangGraph 메시지 시스템 (수동 관리) =====
    messages: Annotated[List[Dict[str, Any]], add]  # 대화 메시지들
    
    # ===== 성능 및 분석 =====
    cache_hits: Optional[Dict[str, int]]     # 캐시 히트 카운트
    performance_metrics: Optional[Dict[str, float]]  # 성능 메트릭스

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