# nodes.py
"""
LangGraph-based AI Wedding Planner Agent - Node Functions
=========================================================

This module contains all the node functions for the wedding planner AI agent.
Each node represents a specific processing step in the conversation flow.

Node Categories:
- Core Processing Nodes: parsing, memo_check, conditional_router
- Specialized Action Nodes: recommendation, tool_execution, memo_update  
- Response Generation Nodes: response_generation
- Error Handling Nodes: error_handler

All nodes follow the standard LangGraph pattern:
- Input: state (Dict) containing current conversation state
- Output: updated state (Dict) with processing results
- Error handling: sets state['status'] = 'error' and state['reason'] on failures
"""

import os
import json
import re
import traceback
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from tools import web_search_tool, calculator_tool, db_query_tool, user_db_update_tool


from openai import OpenAI
from dotenv import load_dotenv

# Project modules
from state import (
    State, create_empty_user_memo, get_memo_file_path, 
    touch_processing_timestamp, memo_set_budget, memo_set_wedding_date, memo_set_guest_count
)
from db import db
from tools import TOOL_REGISTRY

# LLM client initialization
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ============= SYSTEM PROMPTS (Separated for maintainability) =============

PARSING_SYSTEM_PROMPT = """You are a wedding planning assistant specializing in Korean wedding culture. 
Your primary task is to analyze user input and extract structured information for routing decisions.

Extract the following information from user input:

1. VENDOR_TYPE: Identify wedding service categories
   - wedding_hall: Wedding venues and reception halls
   - studio: Photography and videography studios  
   - wedding_dress: Bridal wear and dress shops
   - makeup: Beauty and makeup services
   - null: No specific vendor type mentioned

2. REGION: Korean location keywords  
   - Major areas: 강남, 청담, 압구정, 홍대, 명동, 잠실, 여의도, etc.
   - null: No location preference specified

3. INTENT_HINT: Classify user's primary intention
   - "recommend": User seeking venue/vendor recommendations
   - "tool": Requests requiring database updates, calculations, or searches
   - "general": General consultation, advice, or information requests

4. UPDATE_TYPE: Profile update requests (for tool routing)
   - "wedding_date": Date changes or scheduling
   - "budget": Budget modifications or financial planning  
   - "guest_count": Guest list size changes
   - "preferred_location": Location preference updates
   - null: No profile updates needed

5. BUDGET_MANWON: Extract budget information in Korean "만원" units
   - Convert various Korean expressions to integer values
   - Examples: "5천만원" → 5000, "2억" → 20000, "300만원" → 300
   - null: No budget information provided

6. CONFIDENCE: Your confidence in the extraction (0.0-1.0)

Respond in JSON format:
{
    "vendor_type": "wedding_hall|studio|wedding_dress|makeup|null",
    "region": "강남|청담|etc.|null", 
    "intent_hint": "recommend|tool|general",
    "update_type": "wedding_date|budget|guest_count|preferred_location|null",
    "budget_manwon": 5000,
    "confidence": 0.85
}"""

RESPONSE_GENERATION_SYSTEM_PROMPT = """You are a professional Korean wedding planner AI assistant.
Generate helpful, personalized responses based on the conversation context and tool results.

Guidelines:
1. Use a warm, professional tone appropriate for wedding planning
2. Incorporate user's specific information (budget, date, preferences) when available
3. Provide actionable advice and clear next steps
4. Include relevant suggestions for follow-up questions
5. Keep responses concise but comprehensive
6. Use Korean cultural context for wedding traditions and customs

Context Integration:
- Tool results: Incorporate database query results, calculations, and web search findings
- User memory: Reference previous conversations and established preferences  
- Current request: Address the specific user question or need

Response Structure:
1. Direct answer to user's question
2. Relevant details and explanations
3. Personalized recommendations based on user profile
4. Suggested next actions or follow-up questions

Generate responses in Korean with professional wedding planning expertise."""

ERROR_HANDLER_SYSTEM_PROMPT = """You are an error recovery specialist for a wedding planning AI system.
Your role is to provide helpful, user-friendly error messages and suggest recovery actions.

Error Categories:
1. Input validation errors: Guide users on proper input format
2. System connectivity issues: Explain temporary service interruptions  
3. Data conflicts: Help resolve conflicting information
4. Tool execution failures: Suggest alternative approaches

Response Principles:
1. Never expose technical error details to users
2. Always provide constructive next steps
3. Maintain a helpful, apologetic tone
4. Offer alternative ways to achieve the user's goal
5. Include contact information for persistent issues

Generate error responses in Korean with empathetic, solution-focused messaging."""

# ============= CORE PROCESSING NODES =============

def parsing_node(state: State) -> State:
    """
    Parsing Node - Input Analysis and Intent Recognition
    
    Purpose: Analyze user input to extract structured information for routing decisions.
    This node serves as the entry point for all user requests, transforming natural
    language input into structured data that other nodes can process.
    
    Key Functions:
    - Natural language intent classification
    - Entity extraction (venues, locations, dates, budgets)
    - User emotion and urgency detection  
    - Confidence scoring for parsing accuracy
    
    Input State:
    - user_input: Raw user message text
    - user_id: User identifier for context
    
    Output State:
    - vendor_type: Extracted service category 
    - region_keyword: Location preferences
    - intent_hint: Classified user intention
    - update_type: Profile update requirements
    - total_budget_manwon: Budget information
    - parsing_confidence: Extraction confidence score
    """
    
    touch_processing_timestamp(state)
    user_input = state.get('user_input', '')
    
    if not user_input or not user_input.strip():
        state['status'] = "error"
        state['reason'] = "Empty user input provided"
        return state

    try:
        # LLM-based parsing with structured output
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": PARSING_SYSTEM_PROMPT},
                {"role": "user", "content": f"사용자 입력: {user_input}"}
            ],
            temperature=0.1,
            max_tokens=500
        )
        
        # Parse LLM response
        parsed_response = json.loads(response.choices[0].message.content)
        
        # Update state with extracted information
        state['vendor_type'] = parsed_response.get('vendor_type')
        state['region_keyword'] = parsed_response.get('region') 
        state['intent_hint'] = parsed_response.get('intent_hint', 'general')
        state['update_type'] = parsed_response.get('update_type')
        state['parsing_confidence'] = parsed_response.get('confidence', 0.0)
        state['raw_llm_response'] = parsed_response
        
        # Handle budget extraction with proper conversion
        budget = parsed_response.get('budget_manwon')
        if budget and isinstance(budget, (int, float)):
            state['total_budget_manwon'] = int(budget)
        
        state['status'] = "ok"
        
    except Exception as e:
        state['status'] = "error"
        state['reason'] = f"Parsing node error: {str(e)}"
        state['intent_hint'] = "general"  # Fallback to general response
    
    return state


def memo_check_node(state: State) -> State:
    """
    Memory Check Node - User Context Loading and Validation
    
    Purpose: Load and validate user's long-term memory from persistent storage.
    This node ensures conversation continuity by retrieving historical context,
    preferences, and previous decisions.
    
    Key Functions:
    - JSON-based memory file loading and validation
    - New user initialization (create empty memo)
    - Memory integrity checking (user ID matching, schema validation)
    - Previous conversation context restoration
    
    Input State:
    - user_id: Unique user identifier
    
    Output State:
    - user_memo: Complete user memory structure
    - memo_file_path: File system path to memory storage
    - memo_needs_update: Flag indicating if memory requires updates
    - Profile fields copied for quick access (budget, wedding_date, guest_count)
    """
    
    user_id = state.get('user_id')
    if not user_id:
        # 환경 변수에서 user_id 가져오기
        user_id = os.getenv("DEFAULT_USER_ID", "mvp-test-user")
        
        # state에 user_id 설정
        state['user_id'] = user_id
        
        print(f"🔧 MVP 모드: 기본 user_id '{user_id}' 사용")
    
    if not user_id:
        state['status'] = "error"
        state['reason'] = "No user_id provided for memory check and no default user_id configured"
        return state
    
    try:
        memo_file_path = get_memo_file_path(user_id)
        state['memo_file_path'] = memo_file_path
        
        if os.path.exists(memo_file_path):
            # Load existing memory
            with open(memo_file_path, 'r', encoding='utf-8') as f:
                user_memo = json.load(f)
            
            # Validate memory structure
            if not isinstance(user_memo, dict) or 'profile' not in user_memo:
                raise ValueError("Invalid memory format: missing required structure")
            
            # Version compatibility check
            if 'version' not in user_memo:
                user_memo['version'] = "1.0"
            
            # User ID verification
            memo_user_id = user_memo.get('profile', {}).get('user_id')
            if memo_user_id != user_id:
                raise ValueError(f"User ID mismatch: expected {user_id}, found {memo_user_id}")
            
            state['user_memo'] = user_memo
            state['memo_needs_update'] = False
            
        else:
            # Create new user memory
            user_memo = create_empty_user_memo(user_id)
            state['user_memo'] = user_memo
            state['memo_needs_update'] = True
        
        # Copy profile data for quick access
        profile = user_memo.get('profile', {})
        if profile.get('total_budget_manwon'):
            state['total_budget_manwon'] = profile['total_budget_manwon']
        if profile.get('wedding_date'):
            state['wedding_date'] = profile['wedding_date']
        if profile.get('guest_count'):
            state['guest_count'] = profile['guest_count']
        if profile.get('preferred_locations'):
            state['preferred_locations'] = profile['preferred_locations']
        
        state['status'] = "ok"
        
    except Exception as e:
        state['status'] = "error"
        state['reason'] = f"Memory check error: {str(e)}"
        # Create fallback empty memory
        state['user_memo'] = create_empty_user_memo(user_id)
        state['memo_needs_update'] = True
        
    return state


def conditional_router(state: State) -> State:
    """
    Conditional Router - Intelligent Decision Hub
    
    Purpose: Analyze user intent and current context to determine the optimal
    processing path. This node serves as the central decision point that routes
    requests to appropriate specialized nodes.
    
    Key Functions:
    - Intent-based routing logic (recommend/tool/general)
    - Context-aware decision making using user memory
    - Tool requirement analysis and planning
    - Information gap detection and handling
    
    Routing Logic:
    - "recommendation": Venue/vendor suggestions with sufficient user profile
    - "tool_execution": Database updates, calculations, searches
    - "general_response": Advice, FAQ, general consultation
    - "error_handler": Invalid requests or system errors
    
    Input State:
    - intent_hint: Parsed user intention
    - vendor_type: Service category if specified
    - region_keyword: Location preference
    - user_memo: Historical user context
    
    Output State:
    - routing_decision: Selected processing path
    - tools_to_execute: List of required tools
    - reason: Explanation for routing decision
    """
    
    touch_processing_timestamp(state)
    intent_hint = state.get('intent_hint', 'general')
    vendor_type = state.get('vendor_type')
    region_keyword = state.get('region_keyword')
    user_memo = state.get('user_memo', {})
    user_input = state.get('user_input', '')

    try:
        # Route based on parsed intent
        if intent_hint == "recommend":
            state['routing_decision'] = "recommendation"
            state['tools_to_execute'] = []
            state['reason'] = "User seeking wedding vendor recommendations"
            
        elif intent_hint == "tool":
            state['routing_decision'] = "tool_execution"
            
            # Determine required tools based on request content
            tools_needed = []
            
            # Check for calculation needs
            if any(keyword in user_input for keyword in ['계산', '예산', '총액', '비용', '가격']):
                tools_needed.append("calculator_tool")
                tools_needed.append("db_query_tool")
            
            # Check for database query needs  
            if vendor_type or region_keyword:
                if "db_query_tool" not in tools_needed:
                    tools_needed.append("db_query_tool")
            
            # Check for web search needs
            if any(keyword in user_input for keyword in ['최신', '요즘', '트렌드', '후기', '리뷰']):
                tools_needed.append("web_search_tool")
            
            # Check for user data updates
            update_type = state.get('update_type')
            if update_type:
                tools_needed.append("user_db_update_tool")
            
            # Default to database query if no specific tools identified
            if not tools_needed:
                tools_needed.append("db_query_tool")
            
            state['tools_to_execute'] = tools_needed
            state['reason'] = f"Tool execution needed: {', '.join(tools_needed)}"
            
        else:  # intent_hint == "general"
            state['routing_decision'] = "general_response"
            state['tools_to_execute'] = []
            state['reason'] = "General conversation or FAQ request"
        
        # Information gap analysis for recommendations
        profile = user_memo.get('profile', {})
        missing_info = []
        if not profile.get('wedding_date'):
            missing_info.append("wedding_date")
        if not profile.get('total_budget_manwon'):
            missing_info.append("budget")
        if not profile.get('guest_count'):
            missing_info.append("guest_count")
        
        # Redirect insufficient profile recommendations to general response
        if (len(missing_info) >= 3 and 
            state.get('routing_decision') == "recommendation" and 
            not vendor_type):
            state['routing_decision'] = "general_response"
            state['tools_to_execute'] = []
            state['reason'] = "Insufficient profile info for recommendation, providing general advice"

        state['status'] = "ok"
    
    except Exception as e:
        state['status'] = "error"
        state['reason'] = f"Router error: {str(e)}"
        state['routing_decision'] = "error_handler"
    
    return state

# ============= SPECIALIZED ACTION NODES =============

def recommendation_node(state: State) -> State:
    """
    Recommendation Node - Personalized Wedding Vendor Suggestions
    
    Purpose: Generate tailored wedding vendor recommendations based on user
    preferences, budget constraints, and regional preferences. This node
    implements intelligent matching algorithms for optimal vendor selection.
    
    Key Functions:
    - Requirement analysis and parameter optimization
    - Memory-based personalized recommendation generation  
    - Recommendation parameter customization
    - Algorithm selection (trending/location/budget-based)
    
    Recommendation Scenarios:
    - Venue-based: "찾고 있는 예식장 추천해주세요"
    - Location-based: "강남 스튜디오 추천"
    - Budget-based: "예산 맞는 웨딩홀 찾아주세요"
    
    Input State:
    - vendor_type: Service category for recommendations
    - user_memo: User preferences and constraints
    - region_keyword: Location preferences
    - total_budget_manwon: Budget constraints
    
    Output State:
    - tools_to_execute: Updated with recommendation-specific tools
    - recommendation_params: Parameters for recommendation algorithm
    """
    
    touch_processing_timestamp(state)
    vendor_type = state.get('vendor_type')
    user_memo = state.get('user_memo', {})
    region_keyword = state.get('region_keyword')
    budget = state.get('total_budget_manwon')
    
    try:
        # For MVP, pass through to tool execution with enhanced parameters
        profile = user_memo.get('profile', {})
        
        # Build recommendation context
        recommendation_context = {
            'vendor_type': vendor_type,
            'region': region_keyword or profile.get('preferred_locations', []),
            'budget_manwon': budget or profile.get('total_budget_manwon'),
            'guest_count': profile.get('guest_count'),
            'wedding_date': profile.get('wedding_date'),
            'recommendation_type': 'personalized'
        }
        
        # Store recommendation parameters for tool execution
        state['recommendation_params'] = recommendation_context
        
        # Set tools for recommendation processing
        tools_needed = ["db_query_tool"]
        if any(keyword in state.get('user_input', '') for keyword in ['트렌드', '인기', '후기']):
            tools_needed.append("web_search_tool")
        
        state['tools_to_execute'] = tools_needed
        state['reason'] = f"Generating recommendations for {vendor_type or 'general wedding services'}"
        state['status'] = "ok"
        
    except Exception as e:
        state['status'] = "error"
        state['reason'] = f"Recommendation node error: {str(e)}"
        
    return state


def tool_execution_node(state: State) -> State:
    """
    Tool Execution Node - External Service Integration Hub
    
    Purpose: Execute external tools and services based on routing decisions.
    This node handles complex parameter generation, tool orchestration,
    and result aggregation for various wedding planning tasks.
    
    Key Functions:
    - LLM-based dynamic parameter generation for each tool
    - Parallel tool execution with error isolation
    - Result standardization and quality validation
    - Execution logging and performance monitoring
    
    Supported Tools:
    - db_query_tool: Wedding vendor database searches
    - web_search_tool: Current trends and review searches  
    - calculator_tool: Budget and timeline calculations
    - user_db_update_tool: Profile and preference updates
    
    Input State:
    - tools_to_execute: List of tools to run
    - user_input: Original user request for context
    - State context: All relevant user and session data
    
    Output State:
    - tool_results: Standardized results from all executed tools
    - tool_execution_log: Detailed execution metrics and logs
    """
    touch_processing_timestamp(state)
    tools_to_execute = state.get('tools_to_execute', [])
    
    # tool_results를 이제 리스트로 관리하여 이전 문제를 원천적으로 방지합니다.
    tool_results = []
    execution_log = []
    
    try:
        if not tools_to_execute:
            state['tool_results'] = []
            state['reason'] = "No tools to execute"
            state['status'] = "ok"
            return state
        
        print(f"🔧 실행할 툴: {tools_to_execute}")
        
        for tool_name in tools_to_execute:
            execution_start = datetime.now()
            result = {}
            
            try:
                print(f"⚡ {tool_name} 실행 중...")
                
                if tool_name == "db_query_tool":
                    result = execute_db_query_tool(state)
                elif tool_name == "web_search_tool":
                    result = execute_web_search_tool(state)
                elif tool_name == "calculator_tool":
                    result = execute_calculator_tool(state)
                elif tool_name == "user_db_update_tool":
                    result = execute_user_db_update_tool(state)
                else:
                    result = {
                        "success": False,
                        "error": f"Unknown tool: {tool_name}",
                        "data": None
                    }
                
                execution_end = datetime.now()
                execution_time = (execution_end - execution_start).total_seconds()
                
                # 결과를 리스트에 추가 (tool_name 포함)
                tool_results.append({
                    "tool_name": tool_name,
                    "output": result
                })
                
                log_entry = {
                    "tool_name": tool_name,
                    "execution_time": execution_time,
                    "success": result.get("success", False),
                    "timestamp": execution_end.isoformat()
                }
                execution_log.append(log_entry)
                
                print(f"✅ {tool_name} 완료 ({execution_time:.2f}초)")
                
                if not result.get("success", False):
                    print(f"⚠️ {tool_name} 실행 실패: {result.get('error', 'Unknown error')}")
                
            except Exception as e:
                error_result = {
                    "success": False,
                    "error": f"Tool execution failed: {str(e)}",
                    "data": None
                }
                tool_results.append({
                    "tool_name": tool_name,
                    "output": error_result
                })
                print(f"❌ {tool_name} 에러: {str(e)}")

        successful_tools_count = sum(1 for r in tool_results if r['output'].get("success"))
        
        state['tool_results'] = tool_results # 최종적으로 리스트를 state에 저장
        state['execution_log'] = execution_log
        state['status'] = "ok"
        state['reason'] = f"Executed {successful_tools_count}/{len(tools_to_execute)} tools successfully"
        
        print(f"📊 실행 완료: 성공 {successful_tools_count}, 실패 {len(tools_to_execute) - successful_tools_count}")
        
    except Exception as e:
        state['tool_results'] = []
        state['status'] = "error"
        state['reason'] = f"Tool execution node failed: {str(e)}"
        print(f"💥 tool_execution_node 전체 실패: {str(e)}")
    
    return state


def execute_db_query_tool(state: dict) -> dict:
    """
    데이터베이스 쿼리 툴을 실행하고 결과를 딕셔너리로 반환합니다.
    """
    from tools import db_query_tool
    
    try:
        vendor_type = state.get('vendor_type')
        region_keyword = state.get('region_keyword')
        budget = (state.get('user_memo', {}).get('profile', {})).get('total_budget_manwon')
        
        table_map = {
            "wedding_hall": "wedding_hall",
            "studio": "studio",
            "wedding_dress": "wedding_dress",
            "makeup": "makeup"
        }
        table_name = table_map.get(vendor_type, "wedding_hall") # 기본값 설정
        
        query = f"SELECT name, location, price_manwon FROM {table_name}"
        conditions = []
        
        if region_keyword:
            conditions.append(f"location LIKE '%{region_keyword}%'")
        if budget:
            conditions.append(f"price_manwon <= {budget}")
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY price_manwon DESC LIMIT 5"
        
        print(f"🗄️ DB 쿼리: {query}")
        
        # db_query_tool은 이제 딕셔너리를 반환하므로 그대로 반환합니다.
        return db_query_tool(query)
        
    except Exception as e:
        return {"success": False, "error": f"DB query execution failed: {str(e)}", "data": None}


def execute_web_search_tool(state: dict) -> dict:
    """
    웹 검색 툴을 실행하고 결과를 딕셔너리로 반환합니다.
    """
    from tools import web_search_tool
    
    try:
        vendor_type = state.get('vendor_type', '')
        region_keyword = state.get('region_keyword', '')
        user_input = state.get('user_input', '')
        
        search_terms = []
        if vendor_type:
            search_terms.append(f"{region_keyword} {vendor_type} 추천")
        if any(keyword in user_input for keyword in ['트렌드', '최신', '요즘', '인기']):
            search_terms.append("최신 웨딩 트렌드")
        if any(keyword in user_input for keyword in ['후기', '리뷰']):
            search_terms.append("후기")

        search_query = " ".join(search_terms) or "결혼 준비 정보"
        
        print(f"🌐 웹 검색: {search_query}")
        
        # web_search_tool은 딕셔너리를 반환하므로 그대로 반환합니다.
        return web_search_tool(search_query)
        
    except Exception as e:
        return {"success": False, "error": f"Web search execution failed: {str(e)}", "data": None}


def execute_calculator_tool(state: dict) -> dict:
    """
    계산기 툴을 실행하고 결과를 딕셔너리로 반환합니다.
    """
    from tools import calculator_tool
    
    try:
        user_input = state.get('user_input', '')
        
        # 사용자 입력에서 간단한 수학 표현식 찾기 (예: "총 예산 5000만원에서 300 빼면 얼마?")
        match = re.search(r'([\d\s\+\-\*\/\(\)]+)', user_input)
        if match:
            expression = match.group(1).strip()
            # 숫자만 있는 경우는 제외
            if any(op in expression for op in "+-*/"):
                print(f"🧮 계산기 실행: {expression}")
                return calculator_tool(expression)

        return {"success": False, "error": "No valid calculation expression found in user input", "data": None}

    except Exception as e:
        return {"success": False, "error": f"Calculator execution failed: {str(e)}", "data": None}


def execute_user_db_update_tool(state: dict) -> dict:
    """
    사용자 정보 업데이트 툴을 실행하고 결과를 딕셔너리로 반환합니다.
    """
    from tools import user_db_update_tool
    
    try:
        user_id = state.get('user_id')
        update_type = state.get('update_type')
        
        if not user_id or not update_type:
            return {"success": False, "error": "User ID or update type is missing", "data": None}

        # 상태에서 직접 값을 가져와 툴에 전달
        if update_type == "budget":
            new_value = state.get('total_budget_manwon')
            field_to_update = "total_budget_manwon"
        # 다른 업데이트 타입(wedding_date, guest_count)에 대한 로직 추가 가능
        else:
             return {"success": False, "error": f"Unsupported update type: {update_type}", "data": None}

        if new_value is not None:
             print(f"👤 프로필 업데이트: {field_to_update} -> {new_value}")
             return user_db_update_tool(state, user_id, field_to_update, new_value)
        
        return {"success": False, "error": "No value found in state for the requested update", "data": None}
    
    except Exception as e:
        return {"success": False, "error": f"User update execution failed: {str(e)}", "data": None}
    
def general_response_node(state: dict) -> dict:
    """
    General response node that handles non-specific queries with contextual wedding topic guidance.
    
    This node provides comprehensive responses to general questions while maintaining user engagement
    through natural conversation flow. The node serves as the fallback handler for queries that
    don't require specific tool execution or vendor recommendations.
    
    Core Functionality:
    - Processes general questions with thorough, helpful responses
    - Maintains natural conversation flow without forced topic redirection
    - Subtly guides conversation toward wedding planning topics when appropriate
    - Leverages user memory context to personalize responses
    - Provides FAQ-style answers for common wedding planning questions
    - Handles casual conversation and relationship-building interactions
    
    Response Strategy:
    - Primary Focus: Answer the user's actual question comprehensively
    - Secondary Goal: Natural topic bridging to wedding planning when contextually appropriate
    - Personalization: Incorporate user profile information when relevant
    - Tone Management: Maintain helpful, friendly, and professional tone
    - Engagement: End with gentle conversation steering toward wedding topics
    
    The node avoids forced topic changes but creates natural opportunities for wedding-related
    follow-up questions through contextual bridges and relevant suggestions.
    
    Args:
        state (dict): State containing user_input, user_memo, and conversation context
        
    Returns:
        dict: Updated state with response_content and conversation guidance
    """
    
    user_input = state.get('user_input', '').strip()
    user_memo = state.get('user_memo', {})
    user_id = state.get('user_id')
    
    try:
        if not user_input:
            state['status'] = "error"
            state['reason'] = "No user input provided for general response"
            return state
        
        # Analyze input to determine response approach
        response_context = _analyze_input_context(user_input, user_memo)
        
        # Generate core response based on question type
        core_response = _generate_core_response(user_input, response_context, user_memo)
        
        # Add natural wedding topic bridge if appropriate
        final_response = _add_wedding_topic_bridge(core_response, response_context, user_memo)
        
        # Update state with response
        state['response_content'] = final_response
        state['response_metadata'] = {
            'response_type': 'general_response',
            'topic_bridge_added': response_context.get('bridge_appropriate', False),
            'personalization_level': response_context.get('personalization_level', 'basic'),
            'generated_at': datetime.now().isoformat()
        }
        
        state['status'] = "ok"
        
        print(f"💬 일반 응답 생성 완료 (길이: {len(final_response)}자)")
        
        return state
        
    except Exception as e:
        state['status'] = "error"
        state['reason'] = f"General response generation failed: {str(e)}"
        print(f"❌ 일반 응답 생성 오류: {str(e)}")
        return state


def _analyze_input_context(user_input: str, user_memo: dict) -> dict:
    """Analyze user input to determine appropriate response strategy."""
    
    input_lower = user_input.lower()
    profile = user_memo.get('profile', {})
    
    context = {
        'question_type': 'general',
        'topic_category': 'other',
        'personalization_level': 'basic',
        'bridge_appropriate': True,
        'wedding_related': False
    }
    
    # Detect question types
    if any(word in input_lower for word in ['안녕', '하이', '좋은', '날씨', '기분']):
        context['question_type'] = 'greeting'
        context['topic_category'] = 'casual'
    
    elif any(word in input_lower for word in ['뭐', '무엇', '어떻게', '왜', '언제', '어디서']):
        context['question_type'] = 'inquiry'
        context['topic_category'] = 'informational'
    
    elif any(word in input_lower for word in ['결혼', '웨딩', '신혼', '결혼식', '예식', '신부', '신랑']):
        context['wedding_related'] = True
        context['question_type'] = 'wedding_general'
        context['topic_category'] = 'wedding'
        context['bridge_appropriate'] = False  # Already wedding-related
    
    elif any(word in input_lower for word in ['감사', '고마워', '도움', '좋아']):
        context['question_type'] = 'appreciation'
        context['topic_category'] = 'positive'
    
    elif any(word in input_lower for word in ['힘들', '어려워', '고민', '걱정']):
        context['question_type'] = 'concern'
        context['topic_category'] = 'supportive'
    
    # Determine personalization level based on available user info
    if profile.get('name') or profile.get('wedding_date'):
        context['personalization_level'] = 'high'
    elif profile.get('user_id'):
        context['personalization_level'] = 'medium'
    
    # Adjust bridge appropriateness based on context
    if context['question_type'] in ['appreciation', 'concern']:
        context['bridge_appropriate'] = True
    elif context['topic_category'] == 'casual':
        context['bridge_appropriate'] = True
    
    return context


def _generate_core_response(user_input: str, context: dict, user_memo: dict) -> str:
    """Generate core response based on question type and context."""
    
    question_type = context.get('question_type', 'general')
    profile = user_memo.get('profile', {})
    user_name = profile.get('name', '')
    
    # Response templates based on question type
    if question_type == 'greeting':
        responses = [
            f"안녕하세요{f' {user_name}님' if user_name else ''}! 오늘 하루는 어떻게 보내고 계신가요?",
            f"반가워요{f' {user_name}님' if user_name else ''}! 무엇을 도와드릴까요?",
            "좋은 하루네요! 오늘은 어떤 일이 있으셨나요?"
        ]
        return _select_appropriate_response(responses, context)
    
    elif question_type == 'wedding_general':
        return _handle_wedding_general_question(user_input, user_memo)
    
    elif question_type == 'inquiry':
        return _handle_general_inquiry(user_input, context, user_memo)
    
    elif question_type == 'appreciation':
        responses = [
            "도움이 되었다니 정말 기뻐요! 언제든 궁금한 것이 있으시면 말씀해 주세요.",
            "감사하다고 말씀해 주셔서 감동이에요. 더 도움이 필요하시면 언제든지 연락해 주세요!",
            "천만에요! 여러분의 만족스러운 반응이 저에게는 최고의 보상입니다."
        ]
        return _select_appropriate_response(responses, context)
    
    elif question_type == 'concern':
        responses = [
            "걱정이 많으시군요. 천천히 하나씩 해결해 나가면 분명히 좋은 결과가 있을 거예요.",
            "어려운 상황이시네요. 하지만 모든 문제에는 해결책이 있다고 생각해요. 함께 찾아볼까요?",
            "힘든 시간을 보내고 계신 것 같아요. 제가 도울 수 있는 부분이 있다면 언제든 말씀해 주세요."
        ]
        return _select_appropriate_response(responses, context)
    
    else:
        # General fallback response
        return _generate_general_fallback_response(user_input, user_memo)


def _handle_wedding_general_question(user_input: str, user_memo: dict) -> str:
    """Handle general wedding-related questions."""
    
    profile = user_memo.get('profile', {})
    input_lower = user_input.lower()
    
    if '준비' in input_lower and ('힘들' in input_lower or '어려워' in input_lower):
        return """결혼 준비가 힘드시죠? 정말 많은 분들이 같은 고민을 하세요. 
결혼식 준비는 단계적으로 접근하는 것이 중요해요. 
먼저 예산과 날짜, 하객 규모를 정하고, 그 다음에 예식장과 스튜디오를 선택하시는 것을 추천드려요."""
    
    elif '언제' in input_lower and '시작' in input_lower:
        wedding_date = profile.get('wedding_date')
        if wedding_date:
            return f"""결혼식이 {wedding_date}로 예정되어 있으시니, 지금부터 차근차근 준비하시면 충분해요.
보통 결혼식 3-6개월 전부터 본격적으로 준비하시는 분들이 많아요.
예식장 예약은 빠를수록 좋고, 드레스나 턱시도는 2-3개월 전에 준비하시면 됩니다."""
        else:
            return """결혼 준비는 보통 결혼식 3-6개월 전부터 시작하시는 것을 추천해요.
먼저 예식 날짜부터 정하시는 것이 좋겠네요."""
    
    else:
        return """결혼 준비에 대해 궁금한 점이 있으시군요! 
결혼식 준비는 생각보다 많은 것들을 고려해야 하지만, 체계적으로 접근하면 충분히 해낼 수 있어요.
예산, 날짜, 예식장, 스튜디오 등 어떤 부분이 가장 궁금하신가요?"""


def _handle_general_inquiry(user_input: str, context: dict, user_memo: dict) -> str:
    """Handle general inquiry questions."""
    
    input_lower = user_input.lower()
    
    # Common general questions with helpful responses
    if any(word in input_lower for word in ['날씨', '기온', '온도']):
        return """오늘 날씨 정보는 날씨 앱이나 포털 사이트에서 정확히 확인하실 수 있어요.
날씨가 좋은 날이면 야외 웨딩이나 스튜디오 촬영하기에도 좋겠네요!"""
    
    elif any(word in input_lower for word in ['시간', '몇시', '언제']):
        return """정확한 시간 정보가 필요하시군요. 
결혼식 시간 계획을 세우실 때는 보통 낮 12시나 2시, 4시에 예식을 많이 하세요."""
    
    elif any(word in input_lower for word in ['음식', '요리', '맛집']):
        return """맛있는 음식에 관심이 많으시네요! 
결혼식 피로연이나 신혼여행 맛집 투어도 미리 계획해 보시면 어떨까요?"""
    
    elif any(word in input_lower for word in ['돈', '비용', '가격']):
        return """비용에 대해 관심이 있으시군요. 
결혼 준비도 예산 계획을 미리 세워두시면 훨씬 수월하게 진행하실 수 있어요."""
    
    else:
        return f"""'{user_input}'에 대해 구체적인 정보를 제공해 드리기는 어렵지만, 
관련된 정보를 찾아서 도움을 드리고 싶어요."""


def _generate_general_fallback_response(user_input: str, user_memo: dict) -> str:
    """Generate fallback response for general questions."""
    
    profile = user_memo.get('profile', {})
    user_name = profile.get('name', '')
    
    responses = [
        f"흥미로운 질문이네요{f' {user_name}님' if user_name else ''}! 더 구체적으로 설명해 주시면 더 도움이 될 것 같아요.",
        f"좋은 점을 말씀해 주셨네요. 조금 더 자세히 알려주시면 더 정확한 답변을 드릴 수 있을 것 같아요.",
        f"그런 관점에서 생각해 보시는군요! 어떤 부분이 가장 궁금하신지 알려주시면 좋겠어요."
    ]
    
    return responses[hash(user_input) % len(responses)]


def _add_wedding_topic_bridge(core_response: str, context: dict, user_memo: dict) -> str:
    """Add natural wedding topic bridge to the response if appropriate."""
    
    if not context.get('bridge_appropriate', False):
        return core_response
    
    if context.get('wedding_related', False):
        return core_response  # Already wedding-related, no bridge needed
    
    profile = user_memo.get('profile', {})
    wedding_date = profile.get('wedding_date')
    
    # Generate contextual bridges based on user profile
    if wedding_date:
        bridge_options = [
            f" 그런데 {wedding_date} 결혼식 준비는 어떻게 진행되고 있나요?",
            f" 참, 결혼식 준비 중이신데 도움이 필요한 부분은 없으신가요?",
            f" 결혼 준비로 바쁘실 텐데, 다른 궁금한 점은 없으신지요?"
        ]
    elif profile.get('total_budget_manwon'):
        budget = profile.get('total_budget_manwon')
        bridge_options = [
            f" 결혼 준비 예산 {budget}만원으로 계획하고 계시는데, 어떤 부분부터 시작해볼까요?",
            " 결혼 준비는 어떻게 진행되고 있나요?",
            " 혹시 결혼 준비 관련해서 궁금한 점이 있으시면 언제든 물어보세요!"
        ]
    else:
        bridge_options = [
            " 혹시 결혼 준비 계획이 있으시다면 언제든 도움을 요청해 주세요!",
            " 결혼이나 웨딩과 관련된 궁금한 점이 있으시면 편하게 말씀해 주세요.",
            " 결혼 준비에 대한 조언이 필요하시면 언제든지 연락해 주세요!"
        ]
    
    # Select appropriate bridge based on context
    question_type = context.get('question_type', 'general')
    if question_type == 'concern':
        # More supportive bridge for concerns
        bridge = " 결혼 준비로 고민이 있으시다면 함께 해결책을 찾아보아요!"
    elif question_type == 'appreciation':
        # Encouraging bridge for positive interactions
        bridge = " 결혼 준비도 이렇게 긍정적인 마음으로 하시면 분명 멋진 결과가 있을 거예요!"
    else:
        bridge = bridge_options[hash(core_response) % len(bridge_options)]
    
    return core_response + bridge


def _select_appropriate_response(responses: List[str], context: dict) -> str:
    """Select most appropriate response based on context."""
    
    personalization = context.get('personalization_level', 'basic')
    
    if personalization == 'high':
        return responses[0]  # Most personalized
    elif personalization == 'medium':
        return responses[1] if len(responses) > 1 else responses[0]
    else:
        return responses[-1]  # Most generic

def memo_update_node(state: State) -> State:
    """
    Memory Update Node - Persistent Context Management
    
    Purpose: Update user's long-term memory with new information gathered
    during the conversation. This node ensures continuity across sessions
    and enables personalized experiences based on historical interactions.
    
    Key Functions:
    - Tool result processing and memory integration
    - User preference learning and adaptation
    - Conversation history summarization  
    - JSON file persistence with atomic updates
    
    Update Categories:
    - Profile updates: Budget, dates, guest counts, preferences
    - Search history: Query patterns and result preferences
    - Decision history: Choices made and reasoning
    - Interaction patterns: Communication preferences and timing
    
    Input State:
    - tool_results: Results from executed tools to process
    - user_memo: Current memory state to update
    - memo_needs_update: Flag indicating update requirements
    
    Output State:
    - Updated user_memo with new information
    - memo_needs_update: Reset to False after successful updates
    - memo_updates_made: Log of changes made during this session
    """
    
    touch_processing_timestamp(state)
    user_memo = state.get('user_memo')
    tool_results = state.get('tool_results', [])
    memo_file_path = state.get('memo_file_path')
    
    if not user_memo:
        state['status'] = "error"
        state['reason'] = "User memo is missing for update"
        return state
        
    try:
        updates_made = []
        
        # Process each tool result for memory updates
        for result in tool_results:
            if not result.get('success'):
                continue
                
            tool_name = result['tool_name']
            output = result['output']
            
            if tool_name == 'db_query_tool':
                # Record search patterns and preferences
                search_history = user_memo.setdefault('search_history', [])
                if isinstance(output, dict) and output.get('data'):
                    history_entry = {
                        'query_type': 'database_search',
                        'results_count': output['data'].get('total_count', 0),
                        'timestamp': datetime.now().isoformat()
                    }
                    search_history.append(history_entry)
                    updates_made.append({'category': 'search_history', 'action': 'add_search', 'data': history_entry})
                    
            elif tool_name == 'user_db_update_tool':
                # Process profile updates from user_db_update results
                if isinstance(output, dict) and output.get('success'):
                    updated_data = output.get('data', {})
                    profile = user_memo.setdefault('profile', {})
                    
                    # Update profile with new information
                    for key, value in updated_data.get('updated_profile', {}).items():
                        if value is not None:
                            profile[key] = value
                    
                    updates_made.append({
                        'category': 'profile', 
                        'action': 'update_profile', 
                        'data': updated_data
                    })
                    
            elif tool_name == 'web_search_tool':
                # Store external insights and trends
                if isinstance(output, dict) and output.get('success'):
                    preferences = user_memo.setdefault('preferences', {})
                    insights = preferences.setdefault('external_insights', [])
                    
                    search_data = output.get('data', {})
                    if search_data.get('results'):
                        insight_entry = {
                            'source': 'web_search',
                            'query': search_data.get('query', ''),
                            'results_count': search_data.get('total_count', 0),
                            'timestamp': datetime.now().isoformat()
                        }
                        insights.append(insight_entry)
                        updates_made.append({'category': 'preferences', 'action': 'add_insight', 'data': insight_entry})
                        
            elif tool_name == 'calculator_tool':
                # Record calculation history and financial planning
                if isinstance(output, dict) and output.get('success'):
                    calculations = user_memo.setdefault('calculations', [])
                    calc_data = output.get('data', {})
                    
                    calc_entry = {
                        'expression': calc_data.get('expression', ''),
                        'result': calc_data.get('result'),
                        'timestamp': datetime.now().isoformat()
                    }
                    calculations.append(calc_entry)
                    updates_made.append({'category': 'calculations', 'action': 'add_calculation', 'data': calc_entry})
        
        # Update conversation summary if significant changes occurred
        if updates_made:
            user_memo['last_updated'] = datetime.now().isoformat()
            
            # Save updated memory to file
            if memo_file_path:
                with open(memo_file_path, 'w', encoding='utf-8') as f:
                    json.dump(user_memo, f, ensure_ascii=False, indent=2)
                
            state['memo_needs_update'] = False
            state['memo_updates_made'] = updates_made
        
        state['status'] = "ok"
        
    except Exception as e:
        state['status'] = "error"
        state['reason'] = f"Memo update error: {str(e)}"
        
    return state

# ============= RESPONSE GENERATION NODES =============

def response_generation_node(state: State) -> State:
    """
    Response Generation Node - Final User Response Creation
    
    Purpose: Generate the final response to the user by synthesizing information
    from tool results, memory context, and conversation flow. This node creates
    personalized, helpful responses that address user needs comprehensively.
    
    Key Functions:
    - Multi-source content integration (tools + memory + context)
    - Personalized response generation using user preferences
    - Suggestion generation for follow-up actions
    - Response quality assurance and formatting
    
    Response Categories:
    - Tool-based responses: Incorporate database and calculation results
    - General responses: Advice and consultation without tool usage
    - Error recovery responses: User-friendly error communication
    - Mixed responses: Combination of tool results and general advice
    
    Input State:
    - tool_results: Results from executed tools (if any)
    - user_memo: User context and preferences
    - user_input: Original user request
    - routing_decision: Processing path taken
    
    Output State:
    - final_response: Complete formatted response for user
    - suggestions: Follow-up action recommendations
    - quick_replies: Quick response options for user convenience
    """
    
    touch_processing_timestamp(state)
    tool_results = state.get('tool_results', [])
    user_memo = state.get('user_memo', {})
    user_input = state.get('user_input', '')
    routing_decision = state.get('routing_decision', '')
    
    try:
        # Build context for response generation
        context_parts = []
        
        # Add user context
        profile = user_memo.get('profile', {})
        if profile:
            context_parts.append(f"사용자 프로필: {json.dumps(profile, ensure_ascii=False)}")
        
        successful_tools = [] 

        # Add tool results context
        if tool_results and isinstance(tool_results, dict):
            # 딕셔너리의 값(value)들을 순회하도록 수정
            successful_tools = [res for tool, res in tool_results.items() if isinstance(res, dict) and res.get('success')]
            
            if successful_tools:
                tools_summary = []
                # tool_results 딕셔너리를 올바르게 순회
                for tool_name, result_output in tool_results.items():
                    if isinstance(result_output, dict) and result_output.get('success'):
                        data = result_output.get('data', {})
                        if tool_name == 'db_query_tool':
                            count = data.get('total_count', 0)
                            tools_summary.append(f"데이터베이스 검색: {count}개 결과 발견")
                        elif tool_name == 'web_search_tool':
                            count = data.get('total_results', 0)
                            tools_summary.append(f"웹 검색: {count}개 관련 정보 수집")
                        elif tool_name == 'calculator_tool':
                            result_val = data.get('result')
                            tools_summary.append(f"계산 결과: {result_val}")
                        elif tool_name == 'user_db_update_tool':
                            update_details = data.get('update_details', [])
                            if update_details:
                                tools_summary.append(f"프로필 업데이트: {', '.join(update_details)}")
                
                if tools_summary:
                    context_parts.append("실행된 작업: " + ", ".join(tools_summary))
        
        # Create context string
        context_string = "\n\n".join(context_parts) if context_parts else "일반 상담 요청"
        
        # Generate response using LLM
        messages = [
            {"role": "system", "content": RESPONSE_GENERATION_SYSTEM_PROMPT},
            {"role": "user", "content": f"""
사용자 요청: {user_input}
처리 경로: {routing_decision}
컨텍스트: {context_string}

위 정보를 바탕으로 도움이 되는 응답을 생성해주세요.
"""}
        ]
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,
            max_tokens=1000
        )
        
        final_response = response.choices[0].message.content
        
        # Generate suggestions based on context
        suggestions = []
        if profile.get('wedding_date'):
            suggestions.append("D-day 계산 및 준비 일정 확인하기")
        if not profile.get('total_budget_manwon'):
            suggestions.append("예산 설정 및 항목별 분배 계획하기")
        if successful_tools:
            suggestions.append("더 구체적인 조건으로 재검색하기")
        
        # Default suggestions if none generated
        if not suggestions:
            suggestions = [
                "다른 업체 카테고리 알아보기",
                "예산 계획 상담받기", 
                "웨딩 준비 체크리스트 확인하기"
            ]
        
        # Generate quick replies based on routing decision
        quick_replies = []
        if routing_decision == "recommendation":
            quick_replies = ["더 많은 추천", "다른 지역 보기", "예산대 조정"]
        elif routing_decision == "tool_execution":
            quick_replies = ["결과 상세보기", "조건 변경하기", "저장하기"]
        else:
            quick_replies = ["업체 추천받기", "예산 계산하기", "일정 확인하기"]
        
        # Update state with generated response
        state['final_response'] = final_response
        state['suggestions'] = suggestions
        state['quick_replies'] = quick_replies
        state['status'] = "ok"
        
    except Exception as e:
        state['status'] = "error"
        state['reason'] = f"Response generation error: {str(e)}"
        # Fallback response
        state['final_response'] = "죄송합니다. 응답 생성 중 문제가 발생했습니다. 다시 시도해 주세요."
        state['suggestions'] = ["다시 질문하기", "도움말 보기"]
        state['quick_replies'] = ["재시도", "도움말"]
        
    return state

# ============= ERROR HANDLING NODES =============

def error_handler_node(state: State) -> State:
    """
    Error Handler Node - Comprehensive Error Recovery System
    
    Purpose: Handle various error scenarios gracefully and provide user-friendly
    error messages with constructive recovery suggestions. This node ensures
    the system remains helpful even when technical issues occur.
    
    Key Functions:
    - Error categorization and user-friendly message generation
    - Recovery action suggestions based on error type
    - System health monitoring and reporting
    - Graceful degradation with fallback responses
    
    Error Categories:
    - Input validation errors: Guide users on proper input format
    - System connectivity issues: Explain temporary service interruptions
    - Data conflicts: Help resolve conflicting user information  
    - Tool execution failures: Suggest alternative approaches
    - Memory errors: Handle corrupted or missing user data
    
    Input State:
    - status: "error" status indicating error condition
    - reason: Technical error description
    - error_info: Additional error context and metadata
    
    Output State:
    - final_response: User-friendly error message with next steps
    - suggestions: Recovery actions and alternatives
    - status: "handled_error" to indicate successful error processing
    """
    
    touch_processing_timestamp(state)
    error_reason = state.get('reason', 'Unknown error occurred')
    error_info = state.get('error_info', {})
    user_input = state.get('user_input', '')
    
    try:
        # Generate user-friendly error response based on error type
        messages = [
            {"role": "system", "content": ERROR_HANDLER_SYSTEM_PROMPT},
            {"role": "user", "content": f"""
에러 상황: {error_reason}
사용자 요청: {user_input}
추가 정보: {json.dumps(error_info, ensure_ascii=False)}

사용자에게 도움이 되는 에러 응답과 해결 방안을 제안해주세요.
"""}
        ]
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.3,
            max_tokens=500
        )
        
        error_response = response.choices[0].message.content
        
        # Generate recovery suggestions based on error type
        suggestions = []
        if "parsing" in error_reason.lower():
            suggestions = [
                "더 구체적으로 질문하기",
                "예시를 참고해서 다시 요청하기",
                "단계별로 나누어 질문하기"
            ]
        elif "memory" in error_reason.lower() or "memo" in error_reason.lower():
            suggestions = [
                "기본 정보부터 다시 설정하기",
                "프로필 정보 확인하기",
                "새로 시작하기"
            ]
        elif "tool" in error_reason.lower() or "database" in error_reason.lower():
            suggestions = [
                "조건을 단순화해서 다시 검색하기",
                "다른 방법으로 접근하기",
                "잠시 후 다시 시도하기"
            ]
        else:
            suggestions = [
                "다시 시도하기",
                "다른 방식으로 질문하기",
                "고객 지원팀에 문의하기"
            ]
        
        state['final_response'] = error_response
        state['suggestions'] = suggestions
        state['quick_replies'] = ["다시 시도", "도움말", "새로 시작"]
        state['status'] = "handled_error"
        
    except Exception as e:
        # Ultimate fallback for error handler itself failing
        state['final_response'] = """죄송합니다. 예상치 못한 문제가 발생했습니다.

결혼 준비와 관련해서 필요한 정보나 조언은 최대한 제공해 드릴 수 있어요.

어떤 부분이 가장 궁금하시거나 도움이 필요하신지 말씀해 주시면, 가능한 방법으로 도움을 드리겠습니다!"""
        
        state['suggestions'] = [
            "웨딩홀 추천받기",
            "예산 계획 상담받기", 
            "웨딩 준비 체크리스트 확인하기"
        ]
        state['quick_replies'] = ["웨딩홀", "예산", "체크리스트"]
        state['status'] = "handled_error"
        
    return state

# ============= NODE VALIDATION AND TESTING =============

def validate_all_nodes() -> Dict[str, bool]:
    """
    Validate that all required node functions are properly implemented
    and can handle basic state inputs without crashing.
    """
    
    from state import initialize_state
    
    test_state = initialize_state("test_user", "테스트 입력")
    
    nodes_to_test = {
        "parsing_node": parsing_node,
        "memo_check_node": memo_check_node,
        "conditional_router": conditional_router,
        "recommendation_node": recommendation_node,
        "tool_execution_node": tool_execution_node,
        "memo_update_node": memo_update_node,
        "response_generation_node": response_generation_node,
        "error_handler_node": error_handler_node
    }
    
    validation_results = {}
    
    for node_name, node_func in nodes_to_test.items():
        try:
            # Test with basic state
            result = node_func(test_state.copy())
            validation_results[node_name] = isinstance(result, dict) and 'status' in result
        except Exception as e:
            validation_results[node_name] = False
            print(f"❌ {node_name} validation failed: {e}")
    
    return validation_results

# ============= MODULE EXPORTS =============

__all__ = [
    'parsing_node',
    'memo_check_node', 
    'conditional_router',
    'recommendation_node',
    'tool_execution_node',
    'memo_update_node',
    'response_generation_node',
    'error_handler_node',
    'validate_all_nodes'
]