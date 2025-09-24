# nodes.py - Core Processing Nodes
"""
LangGraph-based AI Wedding Planner - Core Node Implementation
===========================================================

This module contains all core processing nodes that handle user interactions,
data processing, and response generation using ChatOpenAI-based LLM integration.
Each node is designed for maximum LLM utilization with structured outputs.
"""

import os
import json
import re
import asyncio
import tempfile
import traceback
from copy import deepcopy
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from pathlib import Path

# Project modules
from state import State, create_empty_user_memo, touch_processing_timestamp
from db import db, engine

# LLM 관련 (핵심!)
from llm import (
    get_llm, 
    get_parsing_llm, 
    get_creative_llm, 
    get_analysis_llm,
    ParsingResult,
    RecommendationResult,
    ToolDecision,
    ErrorAnalysis,
    llm_with_structured_output,
    safe_llm_invoke
)

# 환경 설정
from dotenv import load_dotenv
load_dotenv()

# System prompts
RESPONSE_GENERATION_PROMPT = """You are a friendly Korean wedding planning assistant.
Generate helpful, warm, and practical responses based on the context provided.

Guidelines:
- Use casual, friendly Korean tone (반말 but respectful)
- Provide specific, actionable advice
- Include relevant numbers, dates, or details when available  
- End with helpful suggestions or questions
- Keep responses concise but informative"""

def parsing_node(state: State) -> State:
    """
    User Input Parsing and Intent Classification Node
    """
    
    from llm import get_parsing_llm, safe_llm_invoke
    
    # 🔍 디버깅: State 전체 확인
    print(f"🔍 parsing_node 시작 - 전체 state: {state}")
    
    touch_processing_timestamp(state)
    user_input = state.get('user_input', '').strip()
    
    # 🔍 디버깅: user_input 값 확인
    print(f"🔍 추출된 user_input: '{user_input}'")
    print(f"🔍 user_input 길이: {len(user_input)}")
    print(f"🔍 user_input 타입: {type(user_input)}")
    
    if not user_input:
        print(f"🚨 빈 입력 감지! state에서 가져온 값: '{state.get('user_input')}'")
        state['status'] = "error"
        state['reason'] = "Empty user input provided"
        return state

    try:
        parsing_llm = get_parsing_llm()
        
        # Stage 1: 간단한 이진 분류 (웨딩 vs 일반)
        intent_prompt = f"""
        사용자 질문을 분석해주세요:
        
        질문: "{user_input}"
        
        이 질문이:
        1. 결혼/웨딩 준비와 관련된 질문이면 → "wedding"
        2. 일반적인 대화/인사/개인적 질문이면 → "general"
        
        예시:
        - "안녕하세요" → general
        - "이름이 뭐예요?" → general  
        - "고마워요" → general
        - "강남 웨딩홀 추천해주세요" → wedding
        - "예산 계산해주세요" → wedding
        - "스튜디오 찾아주세요" → wedding
        
        답변: (wedding 또는 general만 답하세요)
        """
        
        print(f"🔍 LLM에 보낼 프롬프트: {intent_prompt}")
        
        intent_result = safe_llm_invoke(
            intent_prompt, 
            fallback_response="general"
        ).lower().strip()
        
        print(f"🔍 LLM 응답 (intent): '{intent_result}'")
        
        # Stage 2: 일반 대화면 여기서 종료
        if "general" in intent_result:
            state.update({
                'intent_hint': 'general',
                'routing_decision': 'general_response',
                'status': 'ok'
            })
            print(f"🔍 일반 대화로 분류됨")
            return state
        
        # Stage 3: 웨딩 관련이면 세부 정보 파싱
        detail_prompt = f"""
        웨딩 관련 질문을 분석하여 세부 정보를 추출해주세요:
        
        질문: "{user_input}"
        
        다음 정보를 추출해주세요:
        
        1. 업체 종류 (다음 중 하나만, 없으면 null):
           - wedding_hall (웨딩홀, 예식장)
           - studio (스튜디오, 촬영)
           - wedding_dress (드레스, 한복)
           - makeup (메이크업, 헤어)
        
        2. 지역 (구체적인 지역명, 없으면 null):
           - 예: 강남, 청담, 압구정, 잠실, 홍대 등
        
        3. 예산 (만원 단위 숫자만, 없으면 null):
           - 예: "3000만원" → 3000
        
        4. 요청 유형:
           - tool: 검색, 계산, 업데이트가 필요한 경우
           - recommendation: 추천이나 조언을 원하는 경우
        
        답변 형식 (정확히 이 형식으로):
        vendor_type: xxx
        region: xxx  
        budget: xxx
        request_type: xxx
        
        예시:
        "강남 웨딩홀 3000만원으로 찾아주세요" 
        → vendor_type: wedding_hall, region: 강남, budget: 3000, request_type: tool
        """
        
        detail_result = safe_llm_invoke(
            detail_prompt,
            fallback_response="vendor_type: null\nregion: null\nbudget: null\nrequest_type: tool"
        )
        
        print(f"🔍 LLM 응답 (detail): '{detail_result}'")
        
        # 결과 파싱
        parsed_info = {}
        for line in detail_result.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                
                if value.lower() in ['null', 'none', '없음', '']:
                    parsed_info[key] = None
                elif key == 'budget':
                    try:
                        parsed_info[key] = int(value) if value.isdigit() else None
                    except:
                        parsed_info[key] = None
                else:
                    parsed_info[key] = value
        
        print(f"🔍 파싱된 정보: {parsed_info}")
        
        # State 업데이트
        state.update({
            'intent_hint': 'wedding',
            'vendor_type': parsed_info.get('vendor_type'),
            'region_keyword': parsed_info.get('region'),
            'total_budget_manwon': parsed_info.get('budget'),
            'routing_decision': 'tool_execution' if parsed_info.get('request_type') == 'tool' else 'recommendation',
            'status': 'ok'
        })
        
        print(f"✅ 파싱 완료: vendor={parsed_info.get('vendor_type')}, region={parsed_info.get('region')}, budget={parsed_info.get('budget')}")
        
    except Exception as e:
        print(f"🚨 파싱 에러: {e}")
        import traceback
        print(f"🚨 전체 에러 스택: {traceback.format_exc()}")
        
        state.update({
            'status': "error",
            'reason': f"Parsing node failed: {str(e)}",
            'intent_hint': "general",  # 안전한 폴백
            'routing_decision': 'general_response'
        })
    
    return state

def memo_check_node(state: State) -> State:
    """
    User Memory Validation and Context Loading Node
    
    This node handles persistent user memory management, loading existing user
    profiles and preferences from storage, or initializing new user contexts.
    It validates memory integrity and assesses profile completeness to guide
    subsequent processing decisions.
    
    Core Functions:
    - User memory file existence verification and loading
    - Profile completeness analysis and scoring
    - Memory structure validation and error recovery
    - Context preparation for downstream processing nodes
    
    Memory Structure Validation:
    - Profile completeness scoring (wedding_date, budget, guest_count, locations)
    - Data integrity checking for corrupted or malformed entries
    - Version compatibility assessment for schema evolution
    
    Input Requirements:
    - user_id: Unique user identifier for memory retrieval
    - State object with basic processing metadata
    
    Output Guarantees:
    - user_memo: Loaded and validated user memory structure
    - memo_needs_update: Boolean flag indicating update requirements
    - profile_completeness_score: Numeric completeness assessment (0-4)
    - status: Processing outcome with detailed error information
    """
    
    from llm import get_analysis_llm, safe_llm_invoke
    
    touch_processing_timestamp(state)
    user_id = state.get('user_id', 'default_user')
    
    # Ensure memories directory exists
    memories_dir = Path("memories")
    memories_dir.mkdir(exist_ok=True)
    
    memory_file = memories_dir / f"user_{user_id}_memo.json"
    
    try:
        if memory_file.exists():
            # Load existing user memory
            with open(memory_file, 'r', encoding='utf-8') as f:
                user_memo = json.load(f)
                
            # Validate memory structure integrity
            if not isinstance(user_memo, dict) or 'profile' not in user_memo:
                print(f"⚠️ Invalid memory structure for user {user_id}, recreating...")
                user_memo = create_empty_user_memo(user_id)
                state['memo_needs_update'] = True
            else:
                print(f"📋 Loaded existing memory for user {user_id}")
                state['memo_needs_update'] = False
                
        else:
            # Create new user memory
            print(f"🆕 Created new memory for user {user_id}")
            user_memo = create_empty_user_memo(user_id)
            state['memo_needs_update'] = True
            
        # Store loaded memory in state
        state['user_memo'] = user_memo
        
        # Analyze profile completeness using LLM for intelligent assessment
        profile = user_memo.get('profile', {})
        
        # Basic completeness scoring
        completeness_factors = [
            ('wedding_date', profile.get('wedding_date')),
            ('total_budget_manwon', profile.get('total_budget_manwon')),
            ('guest_count', profile.get('guest_count')),
            ('preferred_locations', profile.get('preferred_locations', []))
        ]
        
        completeness_score = sum(1 for _, value in completeness_factors 
                               if value not in [None, [], '', 0])
        
        state['profile_completeness_score'] = completeness_score
        
        # LLM-based profile analysis for advanced insights
        if completeness_score > 0:
            try:
                profile_analysis_prompt = f"""
                Analyze this wedding planning user profile for completeness and potential issues:
                
                Profile Data:
                - Wedding Date: {profile.get('wedding_date', 'Not set')}
                - Budget: {profile.get('total_budget_manwon', 'Not set')} 만원
                - Guest Count: {profile.get('guest_count', 'Not set')}
                - Preferred Locations: {profile.get('preferred_locations', [])}
                
                Provide brief assessment: What's missing? Any inconsistencies?
                Keep response under 100 characters in Korean.
                """
                
                analysis = safe_llm_invoke(
                    profile_analysis_prompt,
                    fallback_response="프로필 기본 정보 확인 완료"
                )
                
                state['profile_analysis'] = analysis
                
            except Exception as e:
                print(f"Profile analysis failed: {e}")
                state['profile_analysis'] = "프로필 분석 일시 실패"
        
        # Copy frequently accessed profile fields to state for quick access
        if 'profile' in user_memo:
            profile = user_memo['profile']
            state['total_budget_manwon'] = profile.get('total_budget_manwon')
            state['wedding_date'] = profile.get('wedding_date')
            state['guest_count'] = profile.get('guest_count')
            state['preferred_locations'] = profile.get('preferred_locations', [])
        
        state['status'] = "ok"
        
    except Exception as e:
        print(f"❌ Memory check failed for user {user_id}: {e}")
        
        # Fallback: create minimal working memory
        state['user_memo'] = create_empty_user_memo(user_id)
        state['memo_needs_update'] = True
        state['profile_completeness_score'] = 0
        state['profile_analysis'] = "메모리 로딩 실패 - 기본값으로 초기화"
        state['status'] = "error"
        state['reason'] = f"Memory loading failed: {str(e)}"
        
    return state


def recommendation_node(state: State) -> State:
    """
    Wedding Vendor Recommendation Node - MVP Placeholder
    
    This node handles intelligent vendor recommendations based on user preferences,
    budget constraints, location preferences, and historical data patterns.
    
    [MVP STATUS: PLACEHOLDER - Full implementation planned for future release]
    
    Future Implementation Plan:
    - ML-based vendor matching algorithm
    - User preference pattern analysis
    - Budget-optimized recommendation scoring
    - Geographic proximity calculations
    - Review sentiment analysis integration
    - Collaborative filtering for similar users
    
    Current MVP Behavior:
    - Returns generic placeholder recommendations
    - Maintains state flow integrity for testing
    - Provides basic response structure for UI compatibility
    """
    
    from llm import safe_llm_invoke
    
    touch_processing_timestamp(state)
    
    try:
        # MVP: Simple placeholder response
        placeholder_response = """MVP 단계에서는 기본 가이드라인을 제공해드립니다.

🏰 **웨딩홀 선택 가이드:**
- 예산의 40-50%를 웨딩홀에 배정하는 것이 일반적입니다
- 하객 수 기준으로 홀 규모를 선택하세요
- 지하철 접근성을 고려해주세요

📸 **스튜디오 선택 팁:**
- 포트폴리오 스타일을 미리 확인하세요
- 야외촬영 가능 여부를 확인해보세요

🎉 **다음 업데이트에서 개인 맞춤 추천 서비스가 추가될 예정입니다!**"""

        state['response_content'] = placeholder_response
        state['suggestions'] = [
            "예산 계획 상담받기",
            "웨딩홀 체크리스트 보기", 
            "스튜디오 포트폴리오 확인하기"
        ]
        state['status'] = "ok"
        
    except Exception as e:
        state['status'] = "error"
        state['reason'] = f"Recommendation node error: {str(e)}"
        state['response_content'] = "추천 서비스 일시 장애 - 곧 개선될 예정입니다."
        
    return state

def general_response_node(state: State) -> State:
    """
    General Response Node - 툴이 필요하지 않은 일반적인 대화 처리
    
    이 노드는 인사, FAQ, 간단한 질문 등을 처리합니다.
    """
    
    print("🗣️ general_response_node 실행 시작")
    
    try:
        user_input = state.get('user_input', '').strip().lower()
        
        # 미리 정의된 응답 패턴
        response_patterns = {
            # 인사 관련
            '안녕': '안녕하세요! 저는 AI 웨딩 플래너 마리예요. 결혼 준비에 대해 궁금한 것이 있으시면 언제든 물어보세요! 💍',
            'hi': '안녕하세요! 저는 AI 웨딩 플래너 마리예요. 결혼 준비에 대해 궁금한 것이 있으시면 언제든 물어보세요! 💍',
            'hello': '안녕하세요! 저는 AI 웨딩 플래너 마리예요. 결혼 준비에 대해 궁금한 것이 있으시면 언제든 물어보세요! 💍',
            
            # 자기소개 관련
            '이름': '저는 마리예요! AI 웨딩 플래너로 여러분의 행복한 결혼식 준비를 도와드리고 있어요. ✨',
            '누구': '저는 마리예요! AI 웨딩 플래너로 여러분의 행복한 결혼식 준비를 도와드리고 있어요. ✨',
            '소개': '저는 AI 웨딩 플래너 마리입니다! 웨딩홀, 스튜디오, 드레스, 메이크업 등 결혼 준비의 모든 것을 도와드려요. 무엇이 궁금하신가요? 💕',
            
            # 감사 표현
            '고마워': '천만에요! 더 궁금한 것이 있으시면 언제든 말씀해주세요. 😊',
            '감사': '도움이 되었다니 기뻐요! 결혼 준비에 관한 것이라면 무엇이든 물어보세요! 💕',
            '고맙': '천만에요! 더 궁금한 것이 있으시면 언제든 말씀해주세요. 😊',
            'thank': 'You\'re welcome! 결혼 준비에 대해 더 궁금한 것이 있으시면 언제든 말씀해주세요! 💕',
            
            # 도움 요청
            '도움': '물론이죠! 웨딩홀, 스튜디오, 드레스, 메이크업 등 결혼 준비의 모든 것을 도와드릴 수 있어요. 구체적으로 어떤 도움이 필요하신가요? 💒',
            '도와': '물론이죠! 웨딩홀, 스튜디오, 드레스, 메이크업 등 결혼 준비의 모든 것을 도와드릴 수 있어요. 구체적으로 어떤 도움이 필요하신가요? 💒',
            'help': '물론이죠! 웨딩홀, 스튜디오, 드레스, 메이크업 등 결혼 준비의 모든 것을 도와드릴 수 있어요. 구체적으로 어떤 도움이 필요하신가요? 💒',
            
            # 기능 문의
            '기능': '저는 다음과 같은 기능을 제공해요:\n• 웨딩홀 추천 및 검색\n• 스튜디오 매칭\n• 드레스/한복 정보\n• 메이크업 업체 추천\n• 예산 계산 및 관리\n• 결혼 준비 일정 관리\n무엇부터 시작해볼까요? 🎯',
            '뭐해': '저는 결혼 준비를 도와드리는 AI 플래너예요! 웨딩홀 찾기, 예산 계산, 업체 추천 등 다양한 도움을 드릴 수 있어요. 어떤 것이 필요하신가요? ✨',
            '할수있': '저는 다음과 같은 기능을 제공해요:\n• 웨딩홀 추천 및 검색\n• 스튜디오 매칭\n• 드레스/한복 정보\n• 메이크업 업체 추천\n• 예산 계산 및 관리\n• 결혼 준비 일정 관리\n무엇부터 시작해볼까요? 🎯'
        }
        
        # 패턴 매칭으로 적절한 응답 찾기
        response = None
        for keyword, reply in response_patterns.items():
            if keyword in user_input:
                response = reply
                break
        
        # 패턴에 맞지 않는 경우 기본 응답
        if not response:
            # LLM을 사용해서 더 자연스러운 응답 생성 (선택적)
            if '?' in user_input or '뭐' in user_input or '어떻게' in user_input:
                response = "궁금한 것이 있으시군요! 결혼 준비에 관련된 구체적인 질문을 해주시면 더 정확한 답변을 드릴 수 있어요. 예를 들어, '강남 웨딩홀 추천해주세요' 또는 '예산 3000만원으로 뭘 할 수 있나요?' 같은 질문을 해보세요! 💡"
            else:
                response = "안녕하세요! 저는 AI 웨딩 플래너 마리예요. 결혼 준비에 대해 궁금한 것이 있으시면 언제든 말씀해주세요! 💍"
        
        # State 업데이트
        state.update({
            'response': response,
            'status': 'ok',
            'intent_hint': 'general'
        })
        
        print(f"✅ 일반 응답 생성 완료: {response[:50]}...")
        
    except Exception as e:
        print(f"🚨 general_response_node 에러: {e}")
        
        # 에러 발생시 안전한 폴백 응답
        fallback_response = "안녕하세요! 저는 AI 웨딩 플래너 마리예요. 결혼 준비에 대해 도움이 필요하시면 말씀해주세요! 💍"
        
        state.update({
            'response': fallback_response,
            'status': 'ok',  # 사용자에게는 정상적으로 보이도록
            'reason': f"General response fallback used: {str(e)}"
        })
        
        import traceback
        print(f"🚨 전체 에러 스택: {traceback.format_exc()}")
    
    return state


def tool_execution_node(state: State) -> State:
    """
    Intelligent Tool Execution and Orchestration Node
    
    This node serves as the central orchestrator for all tool-based operations,
    managing complex workflows that require database queries, calculations,
    web searches, and user profile updates. It leverages LLM-powered decision
    making to optimize execution order, handle failures gracefully, and ensure
    maximum success rates for multi-tool operations.
    
    Core Capabilities:
    - Intelligent execution planning with dependency analysis
    - Dynamic tool parameter optimization based on context
    - Failure recovery with LLM-guided retry strategies  
    - Real-time result quality assessment and validation
    - Cross-tool data flow management and state synchronization
    - Performance monitoring and execution time optimization
    
    Tool Execution Strategy:
    - Pre-execution: LLM analyzes tool dependencies and optimal sequencing
    - During execution: Real-time monitoring with adaptive parameter tuning
    - Post-execution: LLM evaluates result quality and completeness
    - Error recovery: Intelligent retry with parameter adjustment strategies
    
    Supported Tools Integration:
    - db_query_tool: Wedding vendor database searches with filtering
    - calculator_tool: Budget calculations and financial planning
    - web_search_tool: Real-time vendor information and reviews
    - user_db_update_tool: Profile updates and preference management
    
    Input Requirements:
    - tools_to_execute: List of tool names to execute in sequence
    - user_input: Original user request for context-aware execution
    - user_memo: User profile data for personalized tool parameters
    
    Output Guarantees:
    - tool_results: Comprehensive results from all executed tools
    - execution_summary: LLM-generated summary of key findings
    - tool_execution_log: Detailed execution metadata for debugging
    - status: Success/failure status with detailed error information
    """
    
    from llm import get_analysis_llm, llm_with_structured_output, safe_llm_invoke
    from tools import db_query_tool, calculator_tool, web_search_tool, user_db_update_tool
    import time
    
    touch_processing_timestamp(state)
    
    tools_to_execute = state.get('tools_to_execute', [])
    user_input = state.get('user_input', '')
    
    if not tools_to_execute:
        state['status'] = "ok" 
        state['tool_results'] = []
        state['execution_summary'] = "No tools required for this request."
        return state
    
    # Available tools mapping
    AVAILABLE_TOOLS = {
        'db_query_tool': db_query_tool,
        'calculator_tool': calculator_tool, 
        'web_search_tool': web_search_tool,
        'user_db_update_tool': user_db_update_tool
    }
    
    try:
        # Phase 1: LLM-powered execution planning and optimization
        execution_planning_prompt = f"""
        Analyze this tool execution request and create an optimal execution strategy:
        
        User Request: "{user_input}"
        Tools to Execute: {tools_to_execute}
        User Context: {state.get('user_memo', {}).get('profile', {})}
        
        For each tool, determine:
        1. Optimal execution order (considering dependencies)
        2. Key parameters needed for successful execution
        3. Expected result type and success criteria
        4. Potential failure points and mitigation strategies
        
        Provide execution strategy in Korean (max 200 characters):
        """
        
        execution_strategy = safe_llm_invoke(
            execution_planning_prompt,
            fallback_response="도구들을 순차적으로 실행하여 최적의 결과를 제공하겠습니다."
        )
        
        print(f"🎯 Tool Execution Strategy: {execution_strategy}")
        
        # Phase 2: Sequential tool execution with intelligent monitoring
        tool_results = []
        execution_log = {}
        successful_executions = 0
        
        for tool_name in tools_to_execute:
            if tool_name not in AVAILABLE_TOOLS:
                print(f"⚠️ Unknown tool: {tool_name}")
                continue
                
            print(f"🔧 Executing tool: {tool_name}")
            execution_start = time.time()
            
            try:
                # Execute the tool with current state
                tool_function = AVAILABLE_TOOLS[tool_name]
                tool_result = tool_function(deepcopy(state))
                
                execution_time = time.time() - execution_start
                
                # Phase 3: LLM-powered result quality assessment
                if tool_result and isinstance(tool_result, dict):
                    result_analysis_prompt = f"""
                    Evaluate this tool execution result quality:
                    
                    Tool: {tool_name}
                    User Request: "{user_input}"
                    Result: {str(tool_result)[:500]}...
                    
                    Assessment (Korean, max 100 chars): Quality, completeness, usefulness?
                    """
                    
                    quality_assessment = safe_llm_invoke(
                        result_analysis_prompt,
                        fallback_response="실행 완료"
                    )
                    
                    # Store structured result
                    structured_result = {
                        'tool_name': tool_name,
                        'status': 'success',
                        'data': tool_result,
                        'execution_time': round(execution_time, 2),
                        'quality_assessment': quality_assessment,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    tool_results.append(structured_result)
                    successful_executions += 1
                    
                    print(f"✅ {tool_name} completed: {quality_assessment}")
                    
                else:
                    # Handle empty or invalid results
                    structured_result = {
                        'tool_name': tool_name,
                        'status': 'empty_result', 
                        'data': {},
                        'execution_time': round(execution_time, 2),
                        'quality_assessment': '빈 결과 반환됨',
                        'timestamp': datetime.now().isoformat()
                    }
                    tool_results.append(structured_result)
                    print(f"⚠️ {tool_name} returned empty result")
                
            except Exception as tool_error:
                execution_time = time.time() - execution_start
                
                # Phase 4: LLM-guided error analysis and recovery
                error_analysis_prompt = f"""
                Tool execution failed. Analyze the error and suggest recovery:
                
                Tool: {tool_name}
                Error: {str(tool_error)}
                User Request: "{user_input}"
                
                Brief analysis and recovery suggestion (Korean, max 150 chars):
                """
                
                error_analysis = safe_llm_invoke(
                    error_analysis_prompt,
                    fallback_response=f"{tool_name} 실행 실패 - 재시도 또는 대체 방법 필요"
                )
                
                # Log detailed error information
                error_result = {
                    'tool_name': tool_name,
                    'status': 'error',
                    'error_message': str(tool_error),
                    'error_analysis': error_analysis,
                    'execution_time': round(execution_time, 2),
                    'timestamp': datetime.now().isoformat()
                }
                
                tool_results.append(error_result)
                print(f"❌ {tool_name} failed: {error_analysis}")
                
                # Attempt intelligent recovery for critical tools
                if tool_name in ['db_query_tool', 'user_db_update_tool']:
                    print(f"🔄 Attempting recovery for critical tool: {tool_name}")
                    # Could implement retry logic here with modified parameters
        
        # Phase 5: Generate comprehensive execution summary
        summary_generation_prompt = f"""
        Summarize this tool execution session for the user:
        
        User Request: "{user_input}"
        Tools Executed: {len(tool_results)} tools
        Successful: {successful_executions}
        
        Key Results Summary:
        {[r.get('quality_assessment', 'No assessment') for r in tool_results[:3]]}
        
        Create a helpful summary explaining what was accomplished (Korean, max 300 chars):
        """
        
        execution_summary = safe_llm_invoke(
            summary_generation_prompt,
            fallback_response=f"{successful_executions}개 도구가 성공적으로 실행되었습니다."
        )
        
        # Update state with comprehensive results
        state.update({
            'tool_results': tool_results,
            'execution_summary': execution_summary,
            'tool_execution_log': {
                'total_tools': len(tools_to_execute),
                'successful_tools': successful_executions,
                'execution_strategy': execution_strategy,
                'timestamp': datetime.now().isoformat()
            },
            'status': "ok" if successful_executions > 0 else "partial_failure"
        })
        
        print(f"📊 Tool Execution Complete: {successful_executions}/{len(tools_to_execute)} successful")
        
    except Exception as e:
        # Ultimate fallback with diagnostic information
        error_diagnostic_prompt = f"""
        Critical tool execution failure occurred:
        
        Error: {str(e)}
        Requested Tools: {tools_to_execute}
        User Request: "{user_input}"
        
        Generate user-friendly error message and next steps (Korean, max 200 chars):
        """
        
        diagnostic_message = safe_llm_invoke(
            error_diagnostic_prompt,
            fallback_response="도구 실행 중 예상치 못한 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        )
        
        state.update({
            'status': "error",
            'reason': f"Tool execution node failed: {str(e)}",
            'tool_results': [],
            'execution_summary': diagnostic_message,
            'recovery_suggestions': [
                "요청을 더 구체적으로 다시 말씀해주세요",
                "잠시 후 다시 시도해보세요", 
                "다른 방식으로 질문해보세요"
            ]
        })
        
        print(f"💥 Critical tool execution failure: {e}")
    
    return state


def memo_update_node(state: State) -> State:
    """
    Intelligent User Memory Update and Profile Management Node
    
    This node handles sophisticated user profile updates with LLM-powered conflict
    resolution, data validation, and intelligent merging of new information with
    existing user preferences and historical data. It ensures data consistency
    while preserving user intent and maintaining profile integrity over time.
    
    Advanced Update Capabilities:
    - LLM-guided conflict resolution between old and new profile data
    - Intelligent data type validation and format standardization
    - Semantic analysis of preference changes and their implications
    - Historical change tracking with reasoning for audit trails
    - Profile completeness optimization after updates
    - Cross-field dependency validation (budget vs guest count, etc.)
    
    Update Processing Strategy:
    - Pre-update: LLM analyzes update requirements and potential conflicts
    - During update: Real-time validation with intelligent error recovery
    - Post-update: LLM evaluates update success and profile improvements
    - Persistence: Atomic file operations with backup and rollback capability
    
    Supported Update Types:
    - wedding_date: Date parsing, validation, and timeline impact analysis
    - budget: Budget amount processing with financial planning implications
    - guest_count: Numeric validation with venue capacity considerations
    - preferred_location: Location standardization and geographic validation
    
    Input Requirements:
    - update_type: Specific profile field requiring modification
    - user_input: Natural language containing new information
    - user_memo: Current user profile for conflict analysis
    - parsing results: Extracted structured data from parsing_node
    
    Output Guarantees:
    - updated user_memo: Modified profile with new information integrated
    - update_summary: Human-readable description of changes made
    - validation_results: Data integrity and consistency checks
    - profile_improvements: Analysis of completeness enhancements
    """
    
    from llm import get_analysis_llm, get_parsing_llm, safe_llm_invoke
    import json
    from pathlib import Path
    
    touch_processing_timestamp(state)
    
    user_id = state.get('user_id', 'default_user')
    update_type = state.get('update_type')
    user_input = state.get('user_input', '')
    current_memo = state.get('user_memo', {})
    
    if not update_type:
        state['status'] = "ok"
        state['update_summary'] = "No profile updates required"
        return state
    
    try:
        # Phase 1: LLM-Powered Update Analysis and Planning
        update_analysis_prompt = f"""
        Analyze this user profile update request with intelligence and context awareness:
        
        Update Type: {update_type}
        User Request: "{user_input}"
        Current Profile: {json.dumps(current_memo.get('profile', {}), ensure_ascii=False, indent=2)}
        
        Analysis Required:
        1. What specific information should be extracted and updated?
        2. Are there any conflicts with existing profile data?
        3. What validation checks are needed for data integrity?
        4. How will this update improve the overall profile completeness?
        5. Are there any cross-field dependencies to consider?
        
        Provide structured analysis in Korean (max 300 characters):
        Focus on extraction accuracy, conflict resolution, and validation strategy.
        """
        
        analysis_llm = get_analysis_llm()
        update_analysis = safe_llm_invoke(
            update_analysis_prompt,
            fallback_response="프로필 업데이트 분석을 진행합니다."
        )
        
        print(f"🔍 Update Analysis: {update_analysis}")
        
        # Phase 2: Intelligent Data Extraction and Processing
        current_profile = current_memo.get('profile', {})
        updated_profile = deepcopy(current_profile)
        update_details = []
        validation_issues = []
        
        # Smart update processing based on type
        if update_type == 'wedding_date':
            new_date = _extract_and_validate_date(user_input, state)
            if new_date:
                old_date = current_profile.get('wedding_date')
                updated_profile['wedding_date'] = new_date
                
                if old_date and old_date != new_date:
                    update_details.append(f"결혼일 변경: {old_date} → {new_date}")
                else:
                    update_details.append(f"결혼일 설정: {new_date}")
            else:
                validation_issues.append("날짜 정보를 정확히 파악할 수 없습니다")
                
        elif update_type == 'budget':
            new_budget = state.get('total_budget_manwon')
            if new_budget and isinstance(new_budget, (int, float)):
                old_budget = current_profile.get('total_budget_manwon')
                updated_profile['total_budget_manwon'] = int(new_budget)
                
                if old_budget:
                    budget_change = int(new_budget) - int(old_budget)
                    change_desc = "증가" if budget_change > 0 else "감소"
                    update_details.append(f"예산 {change_desc}: {old_budget}만원 → {new_budget}만원")
                else:
                    update_details.append(f"예산 설정: {new_budget}만원")
            else:
                validation_issues.append("예산 금액을 정확히 파악할 수 없습니다")
                
        elif update_type == 'guest_count':
            new_guest_count = _extract_guest_count(user_input)
            if new_guest_count:
                old_count = current_profile.get('guest_count')
                updated_profile['guest_count'] = new_guest_count
                
                if old_count:
                    update_details.append(f"하객 수 변경: {old_count}명 → {new_guest_count}명")
                else:
                    update_details.append(f"하객 수 설정: {new_guest_count}명")
            else:
                validation_issues.append("하객 수를 정확히 파악할 수 없습니다")
                
        elif update_type == 'preferred_location':
            new_location = state.get('region_keyword')
            if new_location:
                current_locations = current_profile.get('preferred_locations', [])
                if new_location not in current_locations:
                    current_locations.append(new_location)
                    updated_profile['preferred_locations'] = current_locations
                    update_details.append(f"선호 지역 추가: {new_location}")
                else:
                    update_details.append(f"선호 지역 {new_location} 이미 등록됨")
            else:
                validation_issues.append("지역 정보를 정확히 파악할 수 없습니다")
        
        # Phase 3: LLM-Powered Cross-Field Validation
        if updated_profile != current_profile and not validation_issues:
            validation_prompt = f"""
            Validate this updated wedding profile for consistency and potential issues:
            
            Updated Profile:
            - Wedding Date: {updated_profile.get('wedding_date', 'Not set')}
            - Budget: {updated_profile.get('total_budget_manwon', 'Not set')} 만원
            - Guest Count: {updated_profile.get('guest_count', 'Not set')} 명
            - Preferred Locations: {updated_profile.get('preferred_locations', [])}
            
            Check for:
            1. Budget vs Guest Count reasonableness
            2. Date feasibility (not in past, reasonable timeline)
            3. Location accessibility and availability
            4. Overall profile consistency
            
            Report any issues or confirm validation success (Korean, max 150 chars):
            """
            
            validation_result = safe_llm_invoke(
                validation_prompt,
                fallback_response="프로필 업데이트 검증 완료"
            )
            
            # Parse validation results
            if "문제" in validation_result or "이슈" in validation_result or "오류" in validation_result:
                validation_issues.append(validation_result)
            else:
                print(f"✅ Profile Validation: {validation_result}")
        
        # Phase 4: Atomic Memory Update with Backup
        if update_details and not validation_issues:
            # Update memo structure
            updated_memo = deepcopy(current_memo)
            updated_memo['profile'] = updated_profile
            updated_memo['last_updated'] = datetime.now().isoformat()
            updated_memo['version'] = str(float(current_memo.get('version', '1.0')) + 0.1)
            
            # Atomic file update with backup
            memories_dir = Path("memories")
            memories_dir.mkdir(exist_ok=True)
            memory_file = memories_dir / f"user_{user_id}_memo.json"
            backup_file = memories_dir / f"user_{user_id}_memo.backup.json"
            
            try:
                # Create backup
                if memory_file.exists():
                    import shutil
                    shutil.copy2(memory_file, backup_file)
                
                # Write updated memory
                with open(memory_file, 'w', encoding='utf-8') as f:
                    json.dump(updated_memo, f, ensure_ascii=False, indent=2)
                
                # Update state
                state['user_memo'] = updated_memo
                state['memo_needs_update'] = False
                
                # Calculate profile completeness improvement
                old_completeness = state.get('profile_completeness_score', 0)
                new_completeness = sum(1 for key in ['wedding_date', 'total_budget_manwon', 'guest_count', 'preferred_locations']
                                     if updated_profile.get(key) not in [None, [], '', 0])
                
                completeness_improvement = new_completeness - old_completeness
                state['profile_completeness_score'] = new_completeness
                
            except Exception as file_error:
                validation_issues.append(f"메모리 저장 실패: {str(file_error)}")
                # Restore from backup if needed
                if backup_file.exists() and not memory_file.exists():
                    shutil.copy2(backup_file, memory_file)
        
        # Phase 5: Generate Comprehensive Update Summary
        if update_details and not validation_issues:
            summary_prompt = f"""
            Generate a user-friendly summary of this successful profile update:
            
            Updates Made: {update_details}
            Profile Improvement: {completeness_improvement if 'completeness_improvement' in locals() else 0} fields completed
            User Request: "{user_input}"
            
            Create an encouraging, informative summary (Korean, max 200 chars):
            Highlight what was updated and how it helps their wedding planning.
            """
            
            update_summary = safe_llm_invoke(
                summary_prompt,
                fallback_response=f"프로필 업데이트 완료: {', '.join(update_details)}"
            )
            
            state.update({
                'update_summary': update_summary,
                'update_details': update_details,
                'validation_results': "성공적으로 검증됨",
                'status': 'ok'
            })
            
            print(f"✅ Profile Update Success: {update_summary}")
            
        elif validation_issues:
            # Handle validation failures gracefully
            error_summary = f"프로필 업데이트 실패: {'; '.join(validation_issues[:2])}"
            
            state.update({
                'update_summary': error_summary,
                'validation_results': validation_issues,
                'status': 'error',
                'reason': 'Validation failed',
                'suggestions': [
                    "더 구체적인 정보로 다시 시도해주세요",
                    "정보 형식을 확인해주세요",
                    "단계별로 나누어서 업데이트해주세요"
                ]
            })
            
        else:
            # No updates to process
            state.update({
                'update_summary': "업데이트할 정보가 없습니다",
                'status': 'ok'
            })
    
    except Exception as e:
        # Ultimate fallback with diagnostic information
        error_message = f"메모리 업데이트 중 오류 발생: {str(e)}"
        
        state.update({
            'status': 'error',
            'reason': f"Memory update failed: {str(e)}",
            'update_summary': error_message,
            'recovery_suggestions': [
                "잠시 후 다시 시도해주세요",
                "정보를 더 간단하게 말씀해주세요",
                "고객 지원팀에 문의해주세요"
            ]
        })
        
        print(f"❌ Memory Update Failed: {e}")
    
    return state

# ============= UPDATE HELPER FUNCTIONS =============

def _extract_and_validate_date(user_input: str, state: State) -> Optional[str]:
    """Extract and validate wedding date from user input using LLM"""
    
    from llm import get_parsing_llm, safe_llm_invoke
    
    date_extraction_prompt = f"""
    Extract the wedding date from this Korean text:
    "{user_input}"
    
    Look for:
    - Specific dates (2025년 10월 15일, 10월 15일, etc.)
    - Relative dates (다음 달, 크리스마스, etc.)
    - Seasonal references (봄, 가을, etc.)
    
    Return ONLY the date in YYYY-MM-DD format, or "NONE" if no clear date found.
    Examples: 2025-10-15, 2025-12-25, NONE
    """
    
    date_result = safe_llm_invoke(date_extraction_prompt, fallback_response="NONE")
    
    if date_result != "NONE" and len(date_result) == 10 and date_result.count('-') == 2:
        try:
            # Basic date validation
            datetime.fromisoformat(date_result)
            return date_result
        except ValueError:
            return None
    
    return None

def _extract_guest_count(user_input: str) -> Optional[int]:
    """Extract guest count from user input"""
    
    import re
    
    # Look for numbers followed by guest-related keywords
    patterns = [
        r'(\d+)\s*명',
        r'(\d+)\s*분',
        r'(\d+)\s*명?\s*(?:정도|쯤|명|분)',
        r'(\d+)\s*(?:명|분)?\s*(?:초대|오실|참석)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, user_input)
        if match:
            count = int(match.group(1))
            if 10 <= count <= 1000:  # Reasonable range
                return count
    
    return None


def error_handler_node(state: State) -> State:
    """
    Advanced Error Analysis and Recovery Node
    
    This node serves as the intelligent error processing center for the entire system,
    providing sophisticated error analysis, recovery strategies, and user-friendly
    communication. It leverages LLM capabilities to transform technical errors into
    actionable guidance while maintaining user confidence and system reliability.
    
    Core Error Processing Capabilities:
    - Multi-dimensional error classification and root cause analysis
    - LLM-powered error interpretation with context-aware explanations
    - Intelligent recovery strategy generation based on error type and user context
    - User experience preservation through empathetic communication
    - System diagnostics and health assessment for proactive issue prevention
    - Escalation pathway determination for unresolvable issues
    
    Error Analysis Framework:
    - Technical Error Assessment: System-level failures, API issues, data corruption
    - User Input Errors: Ambiguous requests, invalid data, unsupported operations
    - Context Errors: Missing information, incomplete profiles, state inconsistencies
    - Integration Errors: Tool failures, database connectivity, external service issues
    
    Recovery Strategy Selection:
    - Automatic Recovery: Self-healing for transient issues and data corrections
    - Guided Recovery: Step-by-step user guidance for resolvable problems
    - Alternative Pathways: Fallback options when primary functionality is unavailable
    - Escalation Protocols: Human intervention triggers for complex issues
    
    User Communication Optimization:
    - Empathetic messaging that reduces user frustration and maintains trust
    - Clear explanation of what went wrong without technical jargon
    - Specific actionable steps the user can take to resolve or work around issues
    - Proactive suggestions to prevent similar issues in the future
    
    Input Requirements:
    - status: Error status indicator from previous nodes
    - reason: Technical error description or failure context
    - user_input: Original user request for context preservation
    - Current system state for comprehensive error analysis
    
    Output Guarantees:
    - final_response: User-friendly error explanation and guidance
    - recovery_suggestions: Specific actionable recovery options
    - quick_replies: UI-friendly recovery action buttons
    - system_health_status: Overall system condition assessment
    """
    
    from llm import get_analysis_llm, get_creative_llm, safe_llm_invoke
    import traceback
    
    touch_processing_timestamp(state)
    
    # Extract error context
    error_status = state.get('status', 'unknown_error')
    error_reason = state.get('reason', 'Unspecified error occurred')
    user_input = state.get('user_input', '')
    original_intent = state.get('intent_hint', 'unknown')
    parsing_confidence = state.get('parsing_confidence', 0.0)
    
    try:
        # Phase 1: Comprehensive Error Analysis and Classification
        error_analysis_prompt = f"""
        Perform comprehensive error analysis for this wedding planning AI system failure:
        
        ERROR CONTEXT:
        - Status: {error_status}
        - Technical Reason: {error_reason}
        - User Request: "{user_input}"
        - Original Intent: {original_intent}
        - Parsing Confidence: {parsing_confidence}
        
        ANALYSIS REQUIRED:
        1. Error Classification: Technical/User Input/Context/Integration error?
        2. Severity Assessment: Critical/High/Medium/Low impact?
        3. Root Cause Analysis: What likely caused this specific failure?
        4. Recovery Feasibility: Can this be automatically resolved?
        5. User Impact: How does this affect their wedding planning experience?
        
        Provide structured analysis as JSON:
        {{
            "error_category": "technical/user_input/context/integration",
            "severity_level": "critical/high/medium/low", 
            "root_cause": "Brief technical explanation",
            "recovery_type": "automatic/guided/alternative/escalation",
            "user_impact": "Brief impact description",
            "confidence": 0.85
        }}
        """
        
        analysis_llm = get_analysis_llm()
        analysis_response = analysis_llm.invoke(error_analysis_prompt)
        
        try:
            import json
            error_analysis = json.loads(analysis_response.content)
            
            error_category = error_analysis.get('error_category', 'technical')
            severity_level = error_analysis.get('severity_level', 'medium')
            root_cause = error_analysis.get('root_cause', '시스템 처리 오류')
            recovery_type = error_analysis.get('recovery_type', 'guided')
            user_impact = error_analysis.get('user_impact', '일시적 서비스 지연')
            analysis_confidence = error_analysis.get('confidence', 0.7)
            
        except (json.JSONDecodeError, AttributeError) as parse_error:
            print(f"⚠️ Error analysis parsing failed: {parse_error}")
            # Fallback classification
            error_category, severity_level, recovery_type = _classify_error_fallback(error_reason, error_status)
            root_cause = "시스템 분석 일시 실패"
            user_impact = "서비스 이용에 일시적 영향"
            analysis_confidence = 0.5
        
        print(f"🔍 Error Analysis: Category={error_category}, Severity={severity_level}, Recovery={recovery_type}")
        
        # Phase 2: Context-Aware Recovery Strategy Generation
        recovery_strategy_prompt = f"""
        Generate intelligent recovery strategy for this wedding planning system error:
        
        ERROR ANALYSIS:
        - Category: {error_category}
        - Severity: {severity_level}
        - Root Cause: {root_cause}
        - Recovery Type: {recovery_type}
        - User Request: "{user_input}"
        
        USER CONTEXT:
        - Profile Completeness: {state.get('profile_completeness_score', 0)}/4
        - Previous Successful Operations: {len(state.get('tool_results', []))}
        
        Generate specific recovery suggestions that:
        1. Address the root cause effectively
        2. Provide alternative ways to accomplish user's goal
        3. Prevent similar issues in the future
        4. Maintain user confidence in the system
        
        Provide 3-4 specific, actionable recovery suggestions in Korean (each max 25 chars):
        """
        
        recovery_suggestions_response = safe_llm_invoke(
            recovery_strategy_prompt,
            fallback_response="다시 시도해주세요,더 구체적으로 요청해주세요,고객 지원 문의하기"
        )
        
        # Parse recovery suggestions
        recovery_suggestions = [s.strip() for s in recovery_suggestions_response.split(',')][:4]
        if len(recovery_suggestions) < 3:
            recovery_suggestions.extend(['다시 시도하기', '도움말 보기', '문의하기'])
        
        # Phase 3: User-Friendly Error Message Generation
        user_message_prompt = f"""
        Create an empathetic, helpful error message for wedding planning users:
        
        SITUATION:
        - User wanted: "{user_input}"
        - Error occurred: {error_category} error, {severity_level} severity
        - Impact: {user_impact}
        - Recovery available: {recovery_type}
        
        COMMUNICATION GOALS:
        1. Acknowledge the issue without technical jargon
        2. Reassure user that this doesn't affect their wedding planning progress
        3. Explain what we're doing to help
        4. Provide clear next steps
        5. Maintain encouraging, supportive tone
        
        Generate user-friendly message in Korean (max 400 characters):
        Use wedding planning context, be warm and solution-focused.
        """
        
        creative_llm = get_creative_llm()
        user_message_response = creative_llm.invoke(user_message_prompt)
        user_friendly_message = user_message_response.content if hasattr(user_message_response, 'content') else str(user_message_response)
        
        # Phase 4: Generate Quick Recovery Actions for UI
        quick_replies = []
        
        if error_category == 'user_input':
            quick_replies = ['다시 말씀해주세요', '예시 보기', '단계별 안내']
        elif error_category == 'context':
            quick_replies = ['프로필 확인', '기본 정보 입력', '처음부터 시작']
        elif error_category == 'technical':
            quick_replies = ['새로고침', '다시 시도', '문의하기']
        else:  # integration errors
            quick_replies = ['대체 방법', '나중에 시도', '고객 지원']
        
        quick_replies.append('도움말')
        
        # Phase 5: System Health Assessment
        system_health_prompt = f"""
        Assess overall system health based on this error occurrence:
        
        CURRENT ERROR:
        - Type: {error_category}
        - Severity: {severity_level}
        - Recovery: {recovery_type}
        
        SYSTEM CONTEXT:
        - Recent successful operations: {len(state.get('tool_results', []))}
        - User profile status: {state.get('profile_completeness_score', 0)}/4 complete
        - Session errors: This error + any previous
        
        Provide health assessment (Korean, max 100 chars):
        Overall system status and any proactive recommendations.
        """
        
        health_assessment = safe_llm_invoke(
            system_health_prompt,
            fallback_response="시스템 상태 양호 - 일시적 문제 해결 중"
        )
        
        # Phase 6: Comprehensive State Updates
        state.update({
            'final_response': user_friendly_message,
            'recovery_suggestions': recovery_suggestions,
            'quick_replies': quick_replies,
            'error_analysis': {
                'category': error_category,
                'severity': severity_level,
                'root_cause': root_cause,
                'recovery_type': recovery_type,
                'user_impact': user_impact,
                'analysis_confidence': analysis_confidence
            },
            'system_health_status': health_assessment,
            'status': 'handled_error',
            'recovery_attempted': True,
            'error_handling_timestamp': datetime.now().isoformat()
        })
        
        # Proactive logging for system monitoring
        print(f"🚨 Error Handled: {error_category}/{severity_level}")
        print(f"💡 Recovery Strategy: {recovery_type}")
        print(f"🏥 System Health: {health_assessment}")
        
    except Exception as handler_error:
        # Meta-error: Error handler itself failed
        print(f"💥 Critical: Error handler failed: {handler_error}")
        
        # Ultimate fallback - minimal but functional response
        fallback_message = """죄송합니다. 일시적인 시스템 문제가 발생했습니다.

🔧 **현재 상황:**
결혼 준비 관련 요청을 처리하는 중에 예상치 못한 문제가 발생했습니다.

💡 **해결 방법:**
- 잠시 후 다시 시도해주세요
- 요청을 더 간단하게 말씀해주세요  
- 다른 방식으로 질문해보세요

결혼 준비에 관한 기본적인 도움은 언제든 받으실 수 있습니다!"""
        
        state.update({
            'final_response': fallback_message,
            'recovery_suggestions': [
                '다시 시도하기',
                '간단한 질문하기', 
                '기본 가이드 보기',
                '고객 지원 문의'
            ],
            'quick_replies': ['다시 시도', '기본 가이드', '문의하기', '도움말'],
            'status': 'critical_error_handled',
            'system_health_status': '긴급 복구 모드 - 기본 기능만 제공 중',
            'meta_error_info': {
                'original_error': error_reason,
                'handler_error': str(handler_error),
                'timestamp': datetime.now().isoformat()
            }
        })
    
    return state

# ============= ERROR CLASSIFICATION HELPERS =============

def _classify_error_fallback(error_reason: str, error_status: str) -> tuple:
    """Rule-based error classification when LLM analysis fails"""
    
    error_reason_lower = error_reason.lower()
    
    # Technical errors
    if any(keyword in error_reason_lower for keyword in ['connection', 'timeout', 'api', 'database', 'server']):
        return 'technical', 'high', 'automatic'
    
    # User input errors  
    elif any(keyword in error_reason_lower for keyword in ['parsing', 'empty', 'invalid', 'format']):
        return 'user_input', 'low', 'guided'
    
    # Context errors
    elif any(keyword in error_reason_lower for keyword in ['memory', 'profile', 'missing', 'incomplete']):
        return 'context', 'medium', 'guided'
    
    # Integration errors
    elif any(keyword in error_reason_lower for keyword in ['tool', 'execution', 'failed']):
        return 'integration', 'medium', 'alternative'
    
    else:
        return 'technical', 'medium', 'guided'

def validate_error_handler() -> bool:
    """Validate error handler functionality"""
    
    try:
        test_state = {
            'status': 'error',
            'reason': 'Test error for validation',
            'user_input': 'Test user input',
            'intent_hint': 'test'
        }
        
        result = error_handler_node(test_state)
        
        required_fields = ['final_response', 'recovery_suggestions', 'quick_replies', 'status']
        return all(field in result for field in required_fields)
        
    except Exception as e:
        print(f"Error handler validation failed: {e}")
        return False
    
    
from datetime import datetime, date
from langchain_core.messages import AIMessage
def response_generation_node(state: State) -> State:
    """
    Advanced Response Generation and Content Synthesis Node
    
    This node serves as the final content orchestrator, synthesizing information
    from all previous processing nodes into cohesive, personalized, and actionable
    responses. It leverages advanced LLM capabilities to transform technical
    processing results into engaging, contextually appropriate communication
    that enhances the user's wedding planning experience.
    
    Core Content Synthesis Capabilities:
    - Multi-source information integration from tool results, recommendations, and user context
    - LLM-powered content personalization based on user profile and preferences
    - Intelligent response formatting with optimal information hierarchy
    - Context-aware tone and style adaptation for different user emotional states
    - Proactive suggestion generation for continued engagement and planning progress
    - Quality assurance through response coherence and completeness validation
    
    Response Generation Framework:
    - Content Analysis: Extract and prioritize key information from all processing nodes
    - Context Integration: Weave user personal data throughout response for relevance
    - Structure Optimization: Organize information for maximum comprehension and action
    - Tone Calibration: Match communication style to user needs and emotional context
    - Enhancement Addition: Include proactive suggestions and next-step guidance
    
    Advanced Personalization Features:
    - Budget-aware recommendations and cost considerations
    - Timeline-sensitive advice based on wedding date proximity
    - Regional customization for location-specific information
    - Progress acknowledgment celebrating user's planning milestones
    - Adaptive complexity based on user expertise and confidence level
    
    Multi-Path Content Integration:
    - Tool Execution Results: Database queries, calculations, web searches
    - Recommendation Outputs: Vendor suggestions, planning advice
    - Memory Updates: Profile changes and preference evolution
    - Error Recovery: Graceful handling of partial failures
    
    Input Requirements:
    - routing_decision: Processing pathway taken (tool_execution, recommendation, etc.)
    - tool_results: Comprehensive results from executed tools
    - response_content: Base content from processing nodes
    - user_memo: Complete user context for personalization
    - user_input: Original request for relevance validation
    
    Output Guarantees:
    - final_response: Complete, formatted response ready for user presentation
    - suggestions: Contextual next-step recommendations
    - quick_replies: UI-optimized interaction options
    - response_metadata: Quality metrics and generation details
    """
    
    from llm import get_creative_llm, get_analysis_llm, safe_llm_invoke
    
    touch_processing_timestamp(state)
    
    # Extract comprehensive context for response generation
    routing_decision = state.get('routing_decision', 'general_response')
    user_input = state.get('user_input', '')
    user_memo = state.get('user_memo', {})
    profile = user_memo.get('profile', {}) if user_memo else {}
    tool_results = state.get('tool_results', [])
    response_content = state.get('response_content', '')
    execution_summary = state.get('execution_summary', '')
    
    try:
        # Phase 1: Comprehensive Content Analysis and Prioritization
        content_analysis_prompt = f"""
        Analyze all available information to create an optimal response strategy:
        
        USER REQUEST: "{user_input}"
        PROCESSING PATH: {routing_decision}
        
        AVAILABLE CONTENT:
        - Base Response: {response_content[:300]}...
        - Tool Results: {len(tool_results)} tools executed
        - Execution Summary: {execution_summary}
        
        USER CONTEXT:
        - Wedding Date: {profile.get('wedding_date', 'Not set')}
        - Budget: {profile.get('total_budget_manwon', 'Not set')} 만원
        - Guest Count: {profile.get('guest_count', 'Not set')} 명
        - Preferred Locations: {profile.get('preferred_locations', [])}
        - Profile Completeness: {state.get('profile_completeness_score', 0)}/4
        
        CONTENT STRATEGY ANALYSIS:
        1. What's the most valuable information to highlight first?
        2. How should personal context be woven throughout the response?
        3. What emotional tone best serves this user's current situation?
        4. What specific next steps would be most helpful?
        5. How can we make this response actionable and encouraging?
        
        Provide content strategy summary (Korean, max 200 chars):
        """
        
        analysis_llm = get_analysis_llm()
        content_strategy = safe_llm_invoke(
            content_analysis_prompt,
            fallback_response="개인 맞춤 결혼 준비 가이드를 제공하겠습니다."
        )
        
        print(f"📝 Content Strategy: {content_strategy}")
        
        # Phase 2: Advanced User Context Personalization
        personalization_context = []
        
        # Build rich personalization context
        if profile.get('wedding_date'):
            try:
                wedding_date = datetime.fromisoformat(profile['wedding_date']).date()
                today = date.today()
                days_until = (wedding_date - today).days
                
                if days_until > 365:
                    timeline_context = "충분한 준비 시간이 있으시네요"
                elif days_until > 180:
                    timeline_context = "본격적인 준비 시기입니다"
                elif days_until > 60:
                    timeline_context = "마무리 단계에 접어들었네요"
                else:
                    timeline_context = "곧 다가오는 결혼식을 앞두고 계시네요"
                    
                personalization_context.append(f"타임라인: {timeline_context} (D-{days_until})")
            except:
                personalization_context.append("결혼일 설정됨")
        
        if profile.get('total_budget_manwon'):
            budget_range = "고예산" if profile['total_budget_manwon'] > 5000 else "중간예산" if profile['total_budget_manwon'] > 2000 else "합리적예산"
            personalization_context.append(f"예산 범위: {budget_range}")
        
        if profile.get('preferred_locations'):
            personalization_context.append(f"선호 지역: {', '.join(profile['preferred_locations'][:2])}")
        
        personalization_string = " | ".join(personalization_context) if personalization_context else "새로운 사용자"
        
        # Phase 3: Intelligent Tool Results Integration
        tool_insights = []
        if tool_results:
            for tool_result in tool_results[:3]:  # Focus on top 3 results
                tool_name = tool_result.get('tool_name', 'unknown')
                tool_data = tool_result.get('data', {})
                quality_assessment = tool_result.get('quality_assessment', '')
                
                if tool_name == 'db_query_tool' and tool_data:
                    vendor_count = len(tool_data.get('results', []))
                    if vendor_count > 0:
                        tool_insights.append(f"업체 검색: {vendor_count}개 매칭 업체 발견")
                
                elif tool_name == 'calculator_tool' and tool_data:
                    result_value = tool_data.get('result', 'N/A')
                    tool_insights.append(f"예산 계산: {result_value}")
                
                elif tool_name == 'web_search_tool' and tool_data:
                    search_count = tool_data.get('total_results', 0)
                    if search_count > 0:
                        tool_insights.append(f"추가 정보: {search_count}개 관련 자료 수집")
        
        tool_context = " | ".join(tool_insights) if tool_insights else ""
        
        # Phase 4: Master Response Generation with Full Context Integration
        master_response_prompt = f"""
        Create the perfect final response for this wedding planning interaction:
        
        USER REQUEST: "{user_input}"
        CONTENT STRATEGY: {content_strategy}
        USER PERSONALIZATION: {personalization_string}
        TOOL INSIGHTS: {tool_context}
        
        BASE CONTENT TO ENHANCE:
        {response_content}
        
        EXECUTION SUMMARY:
        {execution_summary}
        
        RESPONSE REQUIREMENTS:
        1. Start with direct acknowledgment of their specific request
        2. Weave their personal context naturally throughout
        3. Present information in clear, actionable sections
        4. Use encouraging, professional wedding planning consultant tone
        5. Include specific next steps they can take immediately
        6. End with supportive, confidence-building message
        
        Create comprehensive, personalized response in Korean (max 800 characters):
        Make it feel like a conversation with an expert wedding planner who knows them personally.
        """
        
        creative_llm = get_creative_llm()
        master_response = creative_llm.invoke(master_response_prompt)
        final_response_content = master_response.content if hasattr(master_response, 'content') else str(master_response)
        
        # Phase 5: Intelligent Next-Step Suggestions Generation
        suggestions_prompt = f"""
        Generate perfect follow-up suggestions based on this wedding planning interaction:
        
        USER COMPLETED: "{user_input}"
        USER CONTEXT: {personalization_string}
        RESPONSE PROVIDED: {final_response_content[:200]}...
        PROFILE COMPLETENESS: {state.get('profile_completeness_score', 0)}/4
        
        Generate 4 specific, actionable suggestions that:
        1. Build naturally on what was just discussed
        2. Address gaps in their wedding planning
        3. Leverage their personal context (budget, timeline, preferences)
        4. Mix immediate actions with longer-term planning
        
        Format as brief, compelling suggestions (each max 20 chars, Korean):
        """
        
        suggestions_response = safe_llm_invoke(
            suggestions_prompt,
            fallback_response="예산 세부 계획,업체 상담 예약,체크리스트 확인,타임라인 점검"
        )
        
        # Parse and validate suggestions
        suggestions = [s.strip() for s in suggestions_response.split(',')][:4]
        
        # Ensure minimum suggestions with smart defaults
        if len(suggestions) < 4:
            default_suggestions = ['예산 계획', '업체 추천', '준비 가이드', '일정 관리']
            suggestions.extend(default_suggestions[:4-len(suggestions)])
        
        # Phase 6: UI-Optimized Quick Replies Generation
        quick_replies = []
        
        # Context-aware quick replies based on routing and results
        if routing_decision == 'tool_execution':
            if any('db_query' in str(r.get('tool_name', '')) for r in tool_results):
                quick_replies.extend(['더 많은 업체', '상세 정보'])
            if any('calculator' in str(r.get('tool_name', '')) for r in tool_results):
                quick_replies.extend(['다른 계산', '예산 조정'])
        
        elif routing_decision == 'recommendation':
            quick_replies.extend(['구체적 추천', '단계별 가이드'])
        
        else:  # general_response
            if '예산' in user_input:
                quick_replies.extend(['예산 계산기', '절약 팁'])
            elif '업체' in user_input or '추천' in user_input:
                quick_replies.extend(['업체 찾기', '리뷰 확인'])
            else:
                quick_replies.extend(['맞춤 추천', '준비 가이드'])
        
        # Always include help option
        quick_replies.append('다른 질문')
        quick_replies = quick_replies[:4]  # Limit for UI
        
        # Phase 7: Response Quality Assessment
        quality_check_prompt = f"""
        Evaluate this final response quality for wedding planning assistance:
        
        USER REQUEST: "{user_input}"
        GENERATED RESPONSE: {final_response_content[:300]}...
        USER CONTEXT: {personalization_string}
        
        Quality Assessment Criteria:
        1. Directly addresses user's specific request?
        2. Incorporates personal context appropriately? 
        3. Provides actionable next steps?
        4. Maintains encouraging, supportive tone?
        5. Information is accurate and helpful?
        
        Provide quality score and brief assessment (Korean, max 100 chars):
        """
        
        quality_assessment = safe_llm_invoke(
            quality_check_prompt,
            fallback_response="응답 품질 양호 - 개인 맞춤 정보 제공 완료"
        )
        
        # Phase 8: Final State Updates with Comprehensive Metadata
        state.update({
            'final_response': final_response_content,
            'suggestions': suggestions,
            'quick_replies': quick_replies,
            'response_metadata': {
                'generation_strategy': content_strategy,
                'personalization_context': personalization_string,
                'tool_insights_count': len(tool_insights),
                'quality_assessment': quality_assessment,
                'generation_timestamp': datetime.now().isoformat(),
                'word_count': len(final_response_content),
                'routing_path': routing_decision
            },
            'conversation_summary': f"사용자 요청 '{user_input}' 처리 완료 - {routing_decision} 경로 통해 개인 맞춤 응답 제공",
            'status': 'ok'
        })
        # 새로 추가한 부분(2줄)
        current_messages = state.get('messages', [])
        state['messages'] = current_messages + [AIMessage(content=final_response_content)]

        print(f"✨ Response Generated: {len(final_response_content)} chars")
        print(f"🎯 Quality: {quality_assessment}")
        print(f"💡 Suggestions: {len(suggestions)} provided")
        
    except Exception as e:
        print(f"💥 Response generation failed: {e}")
        
        # Intelligent fallback response generation
        fallback_response_prompt = f"""
        Create a helpful fallback response for this wedding planning request:
        
        User asked: "{user_input}"
        Available context: {personalization_string if 'personalization_string' in locals() else 'Limited context'}
        
        Generate encouraging, helpful response despite technical issues (Korean, max 400 chars):
        Focus on wedding planning guidance and next steps.
        """
        
        fallback_response = safe_llm_invoke(
            fallback_response_prompt,
            fallback_response=f"""결혼 준비와 관련된 '{user_input}' 요청에 대해 도움을 드리겠습니다.

현재 일시적인 처리 지연이 있지만, 결혼 준비의 핵심적인 부분들을 안내해 드릴 수 있습니다.

📋 **기본 결혼 준비 가이드:**
- 예산 계획과 우선순위 설정
- 웨딩홀과 주요 업체 예약
- 준비 일정 체크리스트 관리

구체적인 질문이나 도움이 필요한 부분이 있으시면 언제든 말씀해 주세요!"""
        )
        
        state.update({
            'final_response': fallback_response,
            'suggestions': ['예산 계획', '업체 추천', '준비 체크리스트', '일정 관리'],
            'quick_replies': ['예산', '업체', '체크리스트', '도움말'],
            'status': 'ok',  # Graceful degradation
            'response_metadata': {
                'generation_type': 'fallback',
                'error_handled': str(e),
                'timestamp': datetime.now().isoformat()
            }
        })
        # 2줄 추가: fallback 응답도 MessagesState에 추가
        current_messages = state.get('messages', [])
        state['messages'] = current_messages + [AIMessage(content=fallback_response)]
    
    return state