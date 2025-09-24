# routers.py - Intelligent Routing System
"""
LangGraph-based AI Wedding Planner - Core Routing Intelligence
=============================================================

This module contains the central decision-making logic that determines the optimal
processing pathway for every user interaction. The routing system leverages advanced
LLM reasoning to analyze user intent, context, and system state to make intelligent
decisions about which nodes and tools should be activated.

The conditional_router serves as the cognitive center of the entire system,
orchestrating complex multi-step workflows and ensuring optimal user experience.
"""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from copy import deepcopy

# Project imports
from state import State, touch_processing_timestamp
from llm import (
    get_analysis_llm, 
    get_parsing_llm,
    ToolDecision, 
    llm_with_structured_output, 
    safe_llm_invoke
)

# ============= ROUTING DECISION CLASSES =============

class RoutingDecision:
    """Type definitions for routing decisions"""
    TOOL_EXECUTION = "tool_execution"
    GENERAL_RESPONSE = "general_response" 
    RECOMMENDATION = "recommendation"
    ERROR_HANDLER = "error_handler"
    MEMO_UPDATE = "memo_update"

class RoutingPriority:
    """Priority levels for routing decisions"""
    CRITICAL = "critical"      # Errors, urgent updates
    HIGH = "high"             # Specific tool requests, vendor searches
    MEDIUM = "medium"         # General recommendations  
    LOW = "low"              # FAQ, casual conversation

# ============= CORE ROUTING INTELLIGENCE =============

def conditional_router(state: State) -> State:
    """
    Simple and Reliable Conditional Routing Node
    
    parsing_node에서 이미 분석한 결과를 기반으로 단순하고 확실한 라우팅 결정
    """
    
    print("🔀 conditional_router 시작")
    
    touch_processing_timestamp(state)
    
    # parsing_node에서 이미 분석된 결과 가져오기
    intent_hint = state.get('intent_hint', 'general')
    routing_decision_from_parsing = state.get('routing_decision', '')
    vendor_type = state.get('vendor_type')
    region_keyword = state.get('region_keyword')
    user_input = state.get('user_input', '')
    
    print(f"🔍 입력 분석: intent={intent_hint}, parsing_routing={routing_decision_from_parsing}")
    
    # 에러 상태 체크
    if state.get('status') == 'error':
        print("❌ 에러 상태 감지 → error_handler로 라우팅")
        state.update({
            'routing_decision': 'error_handler',
            'tools_to_execute': [],
            'routing_priority': 'high',
            'routing_confidence': 1.0,
            'routing_reasoning': 'Error state detected'
        })
        return state
    
    try:
        # 1단계: parsing_node 결과 우선 사용
        if routing_decision_from_parsing:
            routing_decision = routing_decision_from_parsing
            print(f"✅ parsing_node 결과 사용: {routing_decision}")
        else:
            # 2단계: 폴백 로직 (간단한 규칙 기반)
            if intent_hint == 'general':
                routing_decision = 'general_response'
            elif intent_hint == 'wedding':
                if vendor_type or region_keyword:
                    routing_decision = 'recommendation'  # 구체적인 요청
                else:
                    routing_decision = 'recommendation'  # 일반적인 웨딩 상담
            else:
                routing_decision = 'general_response'  # 기본값
            
            print(f"🔄 폴백 로직 사용: {routing_decision}")
        
        # 3단계: 툴 선택 (단순 규칙 기반)
        tools_to_execute = []
        
        if routing_decision == 'recommendation':
            if vendor_type or region_keyword:
                tools_to_execute = ['db_query_tool', 'web_search_tool']
            # 일반적인 추천은 툴 없이 진행
        elif routing_decision == 'tool_execution':
            # 직접적인 툴 실행 요청
            tools_to_execute = ['db_query_tool', 'web_search_tool']
        # general_response는 툴 불필요
        
        # 4단계: 우선순위와 신뢰도 설정
        if routing_decision == 'recommendation':
            priority = 'medium'
            confidence = 0.8
            reasoning = f"Wedding-related request: vendor={vendor_type}, region={region_keyword}"
        elif routing_decision == 'general_response':
            priority = 'medium'
            confidence = 0.9
            reasoning = "General conversation or FAQ"
        elif routing_decision == 'tool_execution':
            priority = 'high'
            confidence = 0.8
            reasoning = "Direct tool execution required"
        else:
            priority = 'medium'
            confidence = 0.6
            reasoning = "Default routing applied"
        
        # 5단계: State 업데이트
        state.update({
            'routing_decision': routing_decision,
            'tools_to_execute': tools_to_execute,
            'routing_priority': priority,
            'routing_confidence': confidence,
            'routing_reasoning': reasoning,
            'status': 'ok'
        })
        
        # 로깅
        print(f"🎯 ROUTING DECISION: {routing_decision}")
        print(f"🔧 TOOLS TO EXECUTE: {tools_to_execute}")
        print(f"⚡ PRIORITY: {priority} | CONFIDENCE: {confidence}")
        print(f"💭 REASONING: {reasoning}")
        
        return state
        
    except Exception as e:
        print(f"🚨 conditional_router 에러: {e}")
        
        # 안전한 폴백
        state.update({
            'routing_decision': 'general_response',
            'tools_to_execute': [],
            'routing_priority': 'low',
            'routing_confidence': 0.5,
            'routing_reasoning': f'Router error fallback: {str(e)}',
            'status': 'ok'  # 계속 진행
        })
        
        import traceback
        print(f"🚨 전체 스택: {traceback.format_exc()}")
        
        return state


# 헬퍼 함수들 (기존 코드에서 필요한 경우)
def _analyze_routing_context(state):
    """단순한 컨텍스트 분석"""
    return f"User input analysis for routing"

def _fallback_routing_logic(state):
    """단순한 폴백 로직"""
    intent = state.get('intent_hint', 'general')
    if intent == 'general':
        return 'general_response', [], 'Fallback general routing'
    else:
        return 'recommendation', [], 'Fallback wedding routing'

def _optimize_tool_selection(state, tools_needed, routing_decision):
    """툴 선택 최적화"""
    return tools_needed

def _validate_routing_decision(state, routing_decision, tools, confidence):
    """라우팅 검증"""
    return {
        'requires_fallback': False,
        'fallback_route': 'general_response',
        'fallback_tools': [],
        'fallback_reason': ''
    }

def _route_to_error_handler(state, reason, include_diagnostic=False):
    """에러 핸들러로 라우팅"""
    state.update({
        'routing_decision': 'error_handler',
        'status': 'error',
        'reason': reason,
        'tools_to_execute': []
    })
    return state

# ============= ROUTING INTELLIGENCE HELPERS =============

def _analyze_routing_context(state: State) -> str:
    """Generate comprehensive context analysis for routing decisions"""
    
    context_factors = []
    
    # User profile analysis
    user_memo = state.get('user_memo', {})
    profile = user_memo.get('profile', {}) if user_memo else {}
    
    if profile:
        profile_items = []
        if profile.get('wedding_date'):
            profile_items.append(f"Date: {profile['wedding_date']}")
        if profile.get('total_budget_manwon'):
            profile_items.append(f"Budget: {profile['total_budget_manwon']}만원")
        if profile.get('preferred_locations'):
            profile_items.append(f"Preferred: {', '.join(profile['preferred_locations'][:2])}")
        
        if profile_items:
            context_factors.append(f"User Profile: {' | '.join(profile_items)}")
    
    # System state analysis
    status = state.get('status', 'unknown')
    if status != 'ok':
        context_factors.append(f"System Status: {status}")
    
    # Previous interactions
    if state.get('tool_results'):
        context_factors.append(f"Previous Tools: {len(state['tool_results'])} executed")
    
    return ' | '.join(context_factors) if context_factors else "New user session"

def _optimize_tool_selection(state: State, requested_tools: List[str], routing_decision: str) -> List[str]:
    """Intelligently optimize tool selection based on context and performance"""
    
    # Available tools with their capabilities
    TOOL_CAPABILITIES = {
        'db_query_tool': ['vendor_search', 'location_based', 'budget_filtering'],
        'web_search_tool': ['real_time_info', 'reviews', 'pricing'],
        'calculator_tool': ['budget_planning', 'guest_calculations', 'timeline'],
        'user_db_update_tool': ['profile_updates', 'preference_changes']
    }
    
    optimized_tools = []
    
    # Smart tool optimization logic
    for tool in requested_tools:
        if tool in TOOL_CAPABILITIES:
            # Check if tool is appropriate for current context
            if tool == 'db_query_tool' and state.get('vendor_type'):
                optimized_tools.append(tool)
            elif tool == 'web_search_tool' and routing_decision == 'tool_execution':
                optimized_tools.append(tool)
            elif tool == 'calculator_tool' and ('예산' in state.get('user_input', '') or '계산' in state.get('user_input', '')):
                optimized_tools.append(tool)
            elif tool == 'user_db_update_tool' and state.get('update_type'):
                optimized_tools.append(tool)
    
    # Add intelligent tool combinations
    if state.get('vendor_type') and state.get('region_keyword'):
        if 'db_query_tool' not in optimized_tools:
            optimized_tools.append('db_query_tool')
        if 'web_search_tool' not in optimized_tools:
            optimized_tools.append('web_search_tool')
    
    return optimized_tools[:4]  # Limit to prevent overload

def _validate_routing_decision(state: State, routing_decision: str, tools: List[str], confidence: float) -> Dict[str, Any]:
    """Validate routing decisions and provide fallback options"""
    
    validation_result = {
        'requires_fallback': False,
        'fallback_route': 'general_response',
        'fallback_tools': [],
        'fallback_reason': None
    }
    
    # Validate tool availability for tool_execution
    if routing_decision == 'tool_execution' and not tools:
        validation_result.update({
            'requires_fallback': True,
            'fallback_route': 'general_response',
            'fallback_reason': 'No valid tools available for execution'
        })
    
    # Validate confidence levels
    if confidence < 0.3:
        validation_result.update({
            'requires_fallback': True,
            'fallback_route': 'general_response',
            'fallback_reason': f'Low routing confidence: {confidence}'
        })
    
    # Validate recommendation route (MVP limitation)
    if routing_decision == 'recommendation':
        # Keep recommendation but add note
        print("📝 Note: Recommendation node in MVP mode")
    
    return validation_result

def _fallback_routing_logic(state: State) -> tuple:
    """Rule-based fallback routing when LLM analysis fails"""
    
    intent_hint = state.get('intent_hint', 'general')
    vendor_type = state.get('vendor_type')
    update_type = state.get('update_type')
    
    # Simple rule-based routing
    if intent_hint == 'tool':
        if update_type:
            return 'tool_execution', ['user_db_update_tool'], 'Profile update request detected'
        elif vendor_type:
            return 'tool_execution', ['db_query_tool'], 'Vendor search request detected'
        else:
            return 'tool_execution', ['calculator_tool'], 'Tool execution requested'
    
    elif intent_hint == 'recommend':
        if vendor_type:
            return 'tool_execution', ['db_query_tool', 'web_search_tool'], 'Specific vendor recommendation'
        else:
            return 'recommendation', [], 'General recommendation request'
    
    else:  # general or unknown
        return 'general_response', [], 'General conversation or FAQ'

def _route_to_error_handler(state: State, error_reason: str, include_diagnostic: bool = False) -> State:
    """Route to error handler with comprehensive error context"""
    
    state.update({
        'routing_decision': 'error_handler',
        'tools_to_execute': [],
        'routing_priority': 'critical',
        'routing_confidence': 1.0,
        'routing_reasoning': error_reason,
        'status': 'error',
        'reason': error_reason,
        'recovery_attempted': True
    })
    
    if include_diagnostic:
        state['diagnostic_info'] = {
            'original_intent': state.get('intent_hint'),
            'parsing_confidence': state.get('parsing_confidence'),
            'error_timestamp': datetime.now().isoformat()
        }
    
    return state

# ============= ROUTING SYSTEM VALIDATION =============

def validate_routing_system() -> Dict[str, bool]:
    """Validate that the routing system is properly configured"""
    
    validation_results = {
        'llm_integration': False,
        'tool_mapping': False,
        'fallback_logic': False,
        'error_handling': False
    }
    
    try:
        # Test LLM integration
        test_llm = get_analysis_llm()
        validation_results['llm_integration'] = test_llm is not None
        
        # Test tool mapping
        from tools import db_query_tool, calculator_tool
        validation_results['tool_mapping'] = callable(db_query_tool) and callable(calculator_tool)
        
        # Test fallback logic
        test_state = {'intent_hint': 'tool', 'vendor_type': 'wedding_hall'}
        result = _fallback_routing_logic(test_state)
        validation_results['fallback_logic'] = len(result) == 3
        
        # Test error handling
        error_state = _route_to_error_handler({}, "Test error")
        validation_results['error_handling'] = error_state.get('routing_decision') == 'error_handler'
        
    except Exception as e:
        print(f"Routing system validation failed: {e}")
    
    return validation_results