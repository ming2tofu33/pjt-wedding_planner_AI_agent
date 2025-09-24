# llm.py - LLM 설정 모듈
"""
LangGraph-based AI Wedding Planner - LLM Configuration
=====================================================

ChatOpenAI를 사용한 LLM 설정 및 유틸리티 함수들
"""

import os
from langchain_openai import ChatOpenAI
from typing_extensions import TypedDict
from dotenv import load_dotenv

load_dotenv()

# LLM 인스턴스 생성 (15-code_interpreter 방식)
def get_llm() -> ChatOpenAI:
    """LLM 인스턴스 반환"""
    return ChatOpenAI(
        model=os.getenv("LLM_MODEL", "gpt-4o"), 
        temperature=0
    )

# 기본 LLM 인스턴스
llm = get_llm()

# 다양한 용도별 LLM 인스턴스
def get_parsing_llm() -> ChatOpenAI:
    """파싱용 LLM - 더 정확한 결과를 위해 temperature 낮게"""
    return ChatOpenAI(model="gpt-4o-mini", temperature=0)

def get_creative_llm() -> ChatOpenAI:
    """창의적 응답용 LLM - 약간의 창의성 허용"""
    return ChatOpenAI(model="gpt-4o", temperature=0.3)

def get_analysis_llm() -> ChatOpenAI:
    """분석용 LLM - 정확한 분석 필요"""
    return ChatOpenAI(model="gpt-4o", temperature=0)

# 구조화된 출력을 위한 TypedDict 클래스들
class ParsingResult(TypedDict):
    vendor_type: str | None
    region: str | None  
    intent_hint: str
    update_type: str | None
    budget_manwon: int | None
    confidence: float

class RecommendationResult(TypedDict):
    recommendations: list[dict]
    reasoning: str
    additional_questions: list[str]

class ToolDecision(TypedDict):
    tools_needed: list[str]
    reasoning: str
    priority: str

class ErrorAnalysis(TypedDict):
    error_type: str
    user_friendly_message: str
    suggestions: list[str]
    recovery_options: list[str]

# LLM 호출 유틸리티 함수들
def llm_with_structured_output(output_class):
    """구조화된 출력을 위한 LLM 반환"""
    return llm.with_structured_output(output_class)

def safe_llm_invoke(messages, fallback_response="죄송합니다. 일시적인 문제가 발생했습니다."):
    """안전한 LLM 호출 - 에러 처리 포함"""
    try:
        response = llm.invoke(messages)
        return response.content if hasattr(response, 'content') else str(response)
    except Exception as e:
        print(f"LLM 호출 에러: {e}")
        return fallback_response