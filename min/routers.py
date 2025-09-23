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
    Intelligent Conditional Routing Node - System Decision Center
    
    This function represents the cognitive core of the wedding planning assistant,
    responsible for analyzing complex user contexts and making optimal routing
    decisions. It combines rule-based logic with LLM-powered reasoning to handle
    ambiguous situations and edge cases that traditional routing cannot address.
    
    Advanced Routing Capabilities:
    - Multi-dimensional context analysis (intent, user state, system capabilities)
    - LLM-powered disambiguation for complex or ambiguous user requests
    - Dynamic tool selection based on user profile completeness and preferences
    - Intelligent fallback strategies for system limitations or failures
    - Performance-optimized routing to minimize response latency
    - Context-aware priority assignment for competing processing pathways
    
    Decision Matrix Analysis:
    - User Intent Classification: recommend/tool/general with confidence scoring
    - Profile Completeness Assessment: determines information gathering needs
    - Tool Capability Mapping: matches user needs with available system tools
    - Resource Availability: considers system load and tool reliability
    - User Experience Optimization: prioritizes pathways leading to best UX
    
    Routing Outcomes:
    - tool_execution: Database queries, calculations, complex multi-step operations
    - general_response: FAQ answers, educational content, conversational support
    - recommendation: Vendor suggestions, planning advice (MVP: placeholder)
    - error_handler: Error recovery, system issues, malformed requests
    - memo_update: User profile updates, preference changes
    
    Input State Analysis:
    - intent_hint: Primary user intention from parsing_node
    - vendor_type: Specific service category interest
    - region_keyword: Geographic preferences for searches
    - update_type: Profile modification requirements
    - parsing_confidence: Reliability of intent classification
    - user_memo: Complete user context and preferences
    - profile_completeness_score: Information gathering needs assessment
    
    Output Guarantees:
    - routing_decision: Selected processing pathway
    - tools_to_execute: Optimized tool execution sequence
    - routing_priority: Decision urgency classification
    - routing_confidence: System confidence in routing choice
    - reasoning: Human-readable explanation of routing logic
    """
    
    touch_processing_timestamp(state)
    
    # Extract key routing factors from state
    intent_hint = state.get('intent_hint', 'general')
    vendor_type = state.get('vendor_type')
    region_keyword = state.get('region_keyword')
    update_type = state.get('update_type')
    parsing_confidence = state.get('parsing_confidence', 0.5)
    user_input = state.get('user_input', '')
    profile_completeness = state.get('profile_completeness_score', 0)
    
    # Check for system errors or invalid states
    if state.get('status') == 'error' and not state.get('recovery_attempted'):
        return _route_to_error_handler(state, "System error detected, initiating recovery")
    
    try:
        # Phase 1: Context Analysis and Intelligence Gathering
        routing_context = _analyze_routing_context(state)
        
        # Phase 2: LLM-Powered Routing Decision with Advanced Reasoning
        routing_analysis_prompt = f"""
        You are the central routing intelligence for a wedding planning AI assistant.
        Analyze this user interaction and determine the optimal processing pathway.
        
        USER REQUEST: "{user_input}"
        
        PARSED CONTEXT:
        - Intent: {intent_hint}
        - Vendor Type: {vendor_type or 'None'}
        - Region: {region_keyword or 'None'}
        - Update Type: {update_type or 'None'}
        - Parsing Confidence: {parsing_confidence}
        - Profile Completeness: {profile_completeness}/4
        
        SYSTEM CONTEXT:
        {routing_context}
        
        ROUTING OPTIONS:
        1. "tool_execution" - For database searches, calculations, profile updates
        2. "general_response" - For FAQ, advice, conversation
        3. "recommendation" - For vendor suggestions (MVP: basic guidance)
        4. "error_handler" - For unclear requests or system issues
        
        DECISION ANALYSIS REQUIRED:
        - Which route best serves the user's immediate need?
        - What tools (if any) should be executed: db_query_tool, calculator_tool, web_search_tool, user_db_update_tool?
        - What's the confidence level and priority of this decision?
        - How should the system explain this routing choice?
        
        Provide your analysis as a JSON object with:
        {{
            "routing_decision": "selected_route",
            "tools_needed": ["list", "of", "tools"],
            "priority": "high/medium/low",
            "confidence": 0.85,
            "reasoning": "Clear explanation of decision logic",
            "fallback_route": "backup_option_if_primary_fails"
        }}
        """
        
        # Get LLM routing decision with structured output
        analysis_llm = get_analysis_llm()
        routing_response = analysis_llm.invoke(routing_analysis_prompt)
        
        try:
            # Parse LLM routing decision
            routing_analysis = json.loads(routing_response.content)
            
            routing_decision = routing_analysis.get('routing_decision', 'general_response')
            tools_needed = routing_analysis.get('tools_needed', [])
            priority = routing_analysis.get('priority', 'medium')
            confidence = routing_analysis.get('confidence', 0.7)
            reasoning = routing_analysis.get('reasoning', 'Standard routing applied')
            fallback_route = routing_analysis.get('fallback_route', 'general_response')
            
        except (json.JSONDecodeError, AttributeError) as parse_error:
            print(f"⚠️ LLM routing response parsing failed: {parse_error}")
            # Intelligent fallback using rule-based logic
            routing_decision, tools_needed, reasoning = _fallback_routing_logic(state)
            priority = "medium"
            confidence = 0.6
            fallback_route = "general_response"
        
        # Phase 3: Advanced Tool Selection and Optimization
        optimized_tools = _optimize_tool_selection(state, tools_needed, routing_decision)
        
        # Phase 4: Routing Validation and Safety Checks
        validated_routing = _validate_routing_decision(
            state, routing_decision, optimized_tools, confidence
        )
        
        if validated_routing['requires_fallback']:
            routing_decision = validated_routing['fallback_route']
            optimized_tools = validated_routing['fallback_tools']
            reasoning += f" | Fallback: {validated_routing['fallback_reason']}"
        
        # Phase 5: Final State Updates with Comprehensive Metadata
        state.update({
            'routing_decision': routing_decision,
            'tools_to_execute': optimized_tools,
            'routing_priority': priority,
            'routing_confidence': confidence,
            'routing_reasoning': reasoning,
            'routing_fallback': fallback_route,
            'routing_metadata': {
                'analysis_timestamp': datetime.now().isoformat(),
                'context_factors': routing_context,
                'llm_analysis_available': True,
                'validation_passed': not validated_routing['requires_fallback']
            },
            'status': 'ok'
        })
        
        # Comprehensive logging for system monitoring
        print(f"🎯 ROUTING DECISION: {routing_decision}")
        print(f"🔧 TOOLS TO EXECUTE: {optimized_tools}")
        print(f"⚡ PRIORITY: {priority} | CONFIDENCE: {confidence}")
        print(f"💭 REASONING: {reasoning}")
        
        return state
        
    except Exception as e:
        print(f"💥 Critical routing failure: {e}")
        return _route_to_error_handler(
            state, 
            f"Routing system failure: {str(e)}",
            include_diagnostic=True
        )

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