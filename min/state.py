"""
Wedding Chatbot State Definition
================================

LangGraph 기반 AI 웨딩플래너 챗봇의 완전한 상태 구조 정의
- MessagesState 기반으로 메시지 자동 관리
- 4가지 페르소나 시스템 (시간부족형, 개성추구형, 합리적소비형, 알잘딱깔센형)
- 온보딩 시스템 및 메모리 관리
- 웨딩 특화 도메인 정보
- 툴별 타입 안정성 보장
"""

from typing import TypedDict, List, Dict, Optional, Union, Literal
from datetime import datetime
from langgraph.graph import MessagesState
from enum import Enum

# ============= 기본 상수 및 ENUM =============

class PersonaType(str, Enum):
    """사용자 페르소나 타입"""
    TIME_PRESSED = "time_pressed"        # 🏃‍♀️ 준비 시간이 부족하고 너무 바빠요
    UNIQUENESS_SEEKER = "uniqueness_seeker"  # ✨ 개성 있고 특별한 웨딩을 원해요
    RATIONAL_CONSUMER = "rational_consumer"  # 💡 합리적이고 계획적인 소비가 목표예요
    EASY_GOING = "easy_going"            # 😎 다 귀찮고 알잘딱깔센

class WeddingCategoryType(str, Enum):
    """웨딩 카테고리 타입 (CSV 테이블과 매칭)"""
    WEDDING_HALL = "wedding_hall"        # 웨딩홀
    STUDIO = "studio"                    # 스튜디오
    DRESS = "wedding_dress"              # 웨딩드레스
    MAKEUP = "makeup"                    # 메이크업

class OnboardingStep(str, Enum):
    """온보딩 단계"""
    WELCOME = "welcome"                  # 웰컴 메시지
    PERSONA_SELECTION = "persona_selection"  # 페르소나 선택
    BASIC_INFO = "basic_info"           # 기본 정보 수집
    COMPLETED = "completed"              # 온보딩 완료

# ============= 페르소나 시스템 =============

class UserPersona(TypedDict):
    """사용자 페르소나 정보"""
    # 선택된 페르소나
    selected_type: Optional[PersonaType]
    
    # AI 자동 분류 결과
    ai_inferred_type: Optional[PersonaType]
    confidence_score: float              # 추론 확신도 (0.0-1.0)
    
    # 선택 방식 및 이력
    selection_method: Optional[Literal["user_selected", "ai_inferred", "mixed"]]
    selection_history: List[Dict[str, str]]  # 변경 이력
    
    # 페르소나별 맞춤 설정
    response_style: Literal["quick", "detailed", "creative", "comprehensive"]
    recommendation_count: int            # 추천 개수 (3, 5, 10 등)
    decision_support_level: Literal["minimal", "moderate", "high"]
    
    # 행동 패턴 분석
    decision_speed: Literal["fast", "medium", "slow"]
    detail_preference: Literal["high", "medium", "low"]
    comparison_tendency: bool            # 비교검토 성향

class OnboardingState(TypedDict):
    """온보딩 진행 상태"""
    is_new_user: bool                    # 신규 사용자 여부
    current_step: OnboardingStep         # 현재 온보딩 단계
    welcome_shown: bool                  # 웰컴 메시지 표시됨
    persona_selected: bool               # 페르소나 선택 완료
    basic_info_collected: bool           # 기본 정보 수집 완료
    onboarding_completed: bool           # 온보딩 완료
    steps_completed: List[str]           # 완료된 단계들

# ============= 사용자 프로필 및 선호도 =============

class UserProfile(TypedDict):
    """사용자 기본 프로필"""
    user_id: str                         # UID 기반 고유 ID
    
    # 선택적 개인정보 (나중에 입력 가능)
    personal_info: Optional[Dict[str, str]]  # 이름, 성별, 생년월일, 주소, 직장 등
    couple_names: Optional[List[str]]        # [신랑명, 신부명]
    contact_info: Optional[str]              # 연락처
    
    # 웨딩 기본 정보
    wedding_date: Optional[str]          # ISO format date
    total_budget: Optional[int]          # 총 예산 (만원 단위)
    guest_count: Optional[int]           # 하객 수
    preferred_locations: List[str]       # 선호 지역 ["강남구", "서초구"]
    
    # 메타 정보
    created_at: str                      # 계정 생성 시간
    last_active: str                     # 마지막 활동 시간

class WeddingPreferences(TypedDict):
    """웨딩 스타일 및 선호도"""
    # 스타일 선호도
    style_preferences: List[str]         # ["모던한", "클래식", "로맨틱"]
    priority_factors: List[str]          # ["예산", "위치", "분위기"] 우선순위
    venue_type: Optional[str]            # "웨딩홀", "호텔", "스몰웨딩" 등
    season_preference: Optional[str]     # "봄", "여름", "가을", "겨울"
    
    # 페르소나별 특화 선호도
    speed_preference: Literal["fast", "thorough", "flexible"]
    detail_level: Literal["summary", "moderate", "comprehensive"]
    comparison_style: Literal["side_by_side", "pros_cons", "scores"]

# ============= 웨딩 카테고리 관리 =============

class WeddingCategoryInfo(TypedDict):
    """웨딩 카테고리별 상세 정보"""
    category_type: WeddingCategoryType   # 카테고리 타입
    selected_vendor: Optional[str]      # 선택된 업체명
    budget_allocated: Optional[int]     # 해당 카테고리 할당 예산
    budget_spent: Optional[int]         # 사용한 예산
    confirmed: bool                     # 확정 여부
    candidates: List[Dict[str, any]]    # 후보 업체들 (DB 조회 결과)
    requirements: List[str]             # 요구사항 ["원본 제공", "주차 가능" 등]
    search_history: List[Dict[str, any]]  # 검색 이력
    last_updated: str                   # 마지막 업데이트 시간

class WeddingCategories(TypedDict):
    """웨딩 준비 카테고리별 상태 (CSV 테이블과 매칭)"""
    wedding_hall: WeddingCategoryInfo   # 웨딩홀
    studio: WeddingCategoryInfo         # 스튜디오
    wedding_dress: WeddingCategoryInfo  # 웨딩드레스
    makeup: WeddingCategoryInfo         # 메이크업
    # 확장 가능: hanbok, rings, honeymoon 등

# ============= 툴 결과 타입 정의 =============

class DBQueryResult(TypedDict):
    """데이터베이스 조회 결과"""
    table_name: str                     # 조회한 테이블명
    query_type: str                     # "search", "filter", "recommend" 등
    results: List[Dict[str, any]]       # 검색된 업체/상품들
    total_count: int                    # 총 개수
    filters_applied: Dict[str, any]     # 적용된 필터 조건
    search_criteria: Dict[str, any]     # 검색 기준
    execution_time: float               # 쿼리 실행 시간
    cached: bool                        # 캐시된 결과인지

class WebSearchResult(TypedDict):
    """웹 검색 결과"""
    search_query: str                   # 검색어
    search_type: str                    # "reviews", "trends", "news" 등
    articles: List[Dict[str, any]]      # 검색된 기사/정보들
    source_urls: List[str]              # 출처 URL들
    sentiment_score: Optional[float]    # 감정 점수 (-1.0 ~ 1.0)
    relevance_score: float              # 관련성 점수 (0.0 ~ 1.0)
    search_timestamp: str               # 검색 시간

class CalculatorResult(TypedDict):
    """계산기 툴 결과"""
    calculation_type: str               # "budget_breakdown", "dday_calc", "cost_analysis"
    input_values: Dict[str, any]        # 입력값들
    result: Union[float, int, Dict[str, any]]  # 계산 결과
    breakdown: Optional[Dict[str, float]]       # 상세 분해 (예산 분배 등)
    recommendations: List[str]          # 계산 기반 추천사항
    warnings: List[str]                 # 주의사항 (예산 초과 등)
    calculation_timestamp: str          # 계산 시간

class UserDBUpdateResult(TypedDict):
    """사용자 DB 업데이트 결과"""
    update_type: str                    # "profile", "preferences", "booking" 등
    updated_fields: List[str]           # 업데이트된 필드들
    previous_values: Dict[str, any]     # 이전 값들 (롤백용)
    new_values: Dict[str, any]          # 새로운 값들
    validation_passed: bool             # 유효성 검사 통과 여부
    warnings: List[str]                 # 경고사항
    update_timestamp: str               # 업데이트 시간

class ToolResults(TypedDict):
    """모든 툴 실행 결과"""
    db_query: Optional[DBQueryResult]
    web_search: Optional[WebSearchResult]
    calculator: Optional[CalculatorResult]
    user_db_update: Optional[UserDBUpdateResult]

# ============= 의도 분석 및 라우팅 =============

class ParsedIntent(TypedDict):
    """파싱된 사용자 의도"""
    intent_type: str                    # "search_venue", "budget_inquiry", "general_question"
    entities: Dict[str, any]            # 추출된 엔티티들
    confidence: float                   # 의도 분류 확신도 (0.0-1.0)
    intent_category: Literal["search_request", "calculation", "general_chat", "booking_action"]
    extracted_info: Dict[str, any]      # 추출된 구조화 정보
    requires_tools: List[str]           # 필요한 툴들
    urgency_level: Literal["low", "medium", "high"]  # 긴급도

class ResponseStrategy(TypedDict):
    """페르소나 기반 응답 전략"""
    response_format: str                # "quick_summary", "detailed_analysis", "step_by_step"
    include_reasoning: bool             # 추천 이유 포함 여부
    comparison_style: str               # 비교 방식
    recommendation_count: int           # 추천 개수
    detail_level: str                   # 상세도
    follow_up_questions: List[str]      # 후속 질문들

# ============= 메모리 및 컨텍스트 =============

class UserMemo(TypedDict):
    """완전한 사용자 메모리 구조 (JSON 파일로 저장)"""
    # 기본 정보
    profile: UserProfile
    persona: UserPersona
    preferences: WeddingPreferences
    categories: WeddingCategories
    onboarding: OnboardingState
    
    # 대화 및 세션 관리
    conversation_summary: Optional[str]  # AI가 생성한 대화 요약 (핵심 내용만)
    session_count: int                   # 총 세션 횟수
    total_messages: int                  # 총 메시지 수
    
    # 메타 정보
    created_at: str                      # 메모 생성 시간
    last_updated: str                    # 마지막 업데이트 시간
    version: str                         # 메모 버전 (호환성 관리)

class ErrorInfo(TypedDict):
    """에러 정보"""
    error_type: str                     # "parsing_failed", "tool_execution_failed", "llm_error"
    error_message: str                  # 에러 메시지
    node_name: str                      # 에러 발생 노드
    recovery_action: Optional[str]      # 복구 액션
    timestamp: str                      # 에러 발생 시간
    stack_trace: Optional[str]          # 스택 트레이스 (디버깅용)

# ============= 메인 STATE 클래스 =============

class WeddingChatbotState(MessagesState):
    """
    웨딩 챗봇 메인 상태 클래스 (MessagesState 상속)
    
    자동 제공되는 필드:
    - messages: List[BaseMessage] - HumanMessage, AIMessage 등이 자동 누적
    
    커스텀 필드들:
    """
    
    # ===== 사용자 식별 및 세션 =====
    user_id: str                        # UID 기반 고유 사용자 ID
    session_id: str                     # 현재 세션 ID
    
    # ===== 온보딩 및 페르소나 =====
    onboarding: OnboardingState         # 온보딩 진행 상태
    persona: UserPersona                # 사용자 페르소나 정보
    
    # ===== 입력 처리 =====
    user_input: str                     # 원본 사용자 입력
    parsed_intent: Optional[ParsedIntent]  # 파싱된 의도 및 엔티티
    
    # ===== 메모리 관리 =====
    user_memo: Optional[UserMemo]       # 영구 메모리 (JSON 파일)
    memo_file_path: str                 # 메모리 파일 경로
    memo_needs_update: bool             # 메모리 업데이트 필요 여부
    memo_load_success: bool             # 메모리 로드 성공 여부
    
    # ===== 라우팅 및 실행 관리 =====
    routing_decision: Optional[str]     # "tool_execution", "general_response", "recommendation"
    tools_to_execute: List[str]         # 실행할 툴 목록
    tool_results: ToolResults           # 툴 실행 결과들
    response_strategy: Optional[ResponseStrategy]  # 페르소나 기반 응답 전략
    
    # ===== 응답 생성 =====
    response_content: Optional[str]     # 핵심 응답 내용
    final_response: str                 # 최종 포맷팅된 응답
    suggestions: List[str]              # 다음 질문/액션 제안들
    quick_replies: List[str]            # 빠른 답변 버튼들
    
    # ===== 시스템 추적 =====
    current_node: Optional[str]         # 현재 처리 중인 노드명
    processing_timestamp: str           # 처리 시작 시간
    processing_duration: Optional[float]  # 처리 소요 시간
    
    # ===== 에러 처리 =====
    error_info: Optional[ErrorInfo]     # 에러 정보
    recovery_attempted: bool            # 복구 시도 여부
    
    # ===== 성능 및 분석 =====
    cache_hits: Dict[str, int]          # 캐시 히트 카운트
    performance_metrics: Dict[str, float]  # 성능 메트릭스

# ============= 페르소나별 기본 설정 =============

PERSONA_CONFIGS = {
    PersonaType.TIME_PRESSED: {
        "response_style": "quick",
        "recommendation_count": 3,
        "decision_support_level": "high",
        "detail_level": "summary",
        "comparison_style": "side_by_side"
    },
    PersonaType.UNIQUENESS_SEEKER: {
        "response_style": "creative",
        "recommendation_count": 5,
        "decision_support_level": "moderate",
        "detail_level": "comprehensive",
        "comparison_style": "pros_cons"
    },
    PersonaType.RATIONAL_CONSUMER: {
        "response_style": "detailed",
        "recommendation_count": 5,
        "decision_support_level": "comprehensive",
        "detail_level": "comprehensive",
        "comparison_style": "scores"
    },
    PersonaType.EASY_GOING: {
        "response_style": "comprehensive",
        "recommendation_count": 3,
        "decision_support_level": "high",
        "detail_level": "moderate",
        "comparison_style": "side_by_side"
    }
}

# ============= 유틸리티 함수들 =============

def create_empty_user_memo(user_id: str) -> UserMemo:
    """새 사용자를 위한 빈 메모 생성"""
    now = datetime.now().isoformat()
    
    return UserMemo(
        profile=UserProfile(
            user_id=user_id,
            personal_info=None,
            couple_names=None,
            contact_info=None,
            wedding_date=None,
            total_budget=None,
            guest_count=None,
            preferred_locations=[],
            created_at=now,
            last_active=now
        ),
        persona=UserPersona(
            selected_type=None,
            ai_inferred_type=None,
            confidence_score=0.0,
            selection_method=None,
            selection_history=[],
            response_style="detailed",
            recommendation_count=3,
            decision_support_level="moderate",
            decision_speed="medium",
            detail_preference="medium",
            comparison_tendency=False
        ),
        preferences=WeddingPreferences(
            style_preferences=[],
            priority_factors=[],
            venue_type=None,
            season_preference=None,
            speed_preference="flexible",
            detail_level="moderate",
            comparison_style="side_by_side"
        ),
        categories=WeddingCategories(
            wedding_hall=WeddingCategoryInfo(
                category_type=WeddingCategoryType.WEDDING_HALL,
                selected_vendor=None,
                budget_allocated=None,
                budget_spent=None,
                confirmed=False,
                candidates=[],
                requirements=[],
                search_history=[],
                last_updated=now
            ),
            studio=WeddingCategoryInfo(
                category_type=WeddingCategoryType.STUDIO,
                selected_vendor=None,
                budget_allocated=None,
                budget_spent=None,
                confirmed=False,
                candidates=[],
                requirements=[],
                search_history=[],
                last_updated=now
            ),
            wedding_dress=WeddingCategoryInfo(
                category_type=WeddingCategoryType.DRESS,
                selected_vendor=None,
                budget_allocated=None,
                budget_spent=None,
                confirmed=False,
                candidates=[],
                requirements=[],
                search_history=[],
                last_updated=now
            ),
            makeup=WeddingCategoryInfo(
                category_type=WeddingCategoryType.MAKEUP,
                selected_vendor=None,
                budget_allocated=None,
                budget_spent=None,
                confirmed=False,
                candidates=[],
                requirements=[],
                search_history=[],
                last_updated=now
            )
        ),
        onboarding=OnboardingState(
            is_new_user=True,
            current_step=OnboardingStep.WELCOME,
            welcome_shown=False,
            persona_selected=False,
            basic_info_collected=False,
            onboarding_completed=False,
            steps_completed=[]
        ),
        conversation_summary=None,
        session_count=1,
        total_messages=0,
        created_at=now,
        last_updated=now,
        version="1.0"
    )

def get_persona_config(persona_type: Optional[PersonaType]) -> Dict[str, any]:
    """페르소나별 기본 설정 반환"""
    if persona_type and persona_type in PERSONA_CONFIGS:
        return PERSONA_CONFIGS[persona_type]
    
    # 기본값 (페르소나 미선택시)
    return PERSONA_CONFIGS[PersonaType.RATIONAL_CONSUMER]

def get_memo_file_path(user_id: str) -> str:
    """사용자 메모리 파일 경로 생성"""
    import os
    
    memories_dir = "memories"
    if not os.path.exists(memories_dir):
        os.makedirs(memories_dir)
    
    return os.path.join(memories_dir, f"user_{user_id}_memo.json")
