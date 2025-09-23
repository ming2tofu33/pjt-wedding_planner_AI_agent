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
    
    # Import tools from tools.py
    from tools import web_search_tool, calculator_tool, db_query_tool, user_db_update_tool
    
    touch_processing_timestamp(state)
    tools_to_execute = state.get('tools_to_execute', [])
    user_memo = state.get('user_memo', {})
    user_input = state.get('user_input', '')
    user_id = state.get('user_id')
    
    # Tool execution results and logging
    tool_results = {}
    execution_log = []
    
    try:
        if not tools_to_execute:
            state['tool_results'] = {}
            state['reason'] = "No tools to execute"
            state['status'] = "ok"
            return state
        
        print(f"🔧 실행할 툴: {tools_to_execute}")
        
        # Execute each tool sequentially
        for tool_name in tools_to_execute:
            execution_start = datetime.now()
            
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
                
                # Store result
                tool_results[tool_name] = result
                
                # Log execution
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
                tool_results[tool_name] = error_result
                
                execution_end = datetime.now()
                execution_time = (execution_end - execution_start).total_seconds()
                
                log_entry = {
                    "tool_name": tool_name,
                    "execution_time": execution_time,
                    "success": False,
                    "error": str(e),
                    "timestamp": execution_end.isoformat()
                }
                execution_log.append(log_entry)
                
                print(f"❌ {tool_name} 에러: {str(e)}")
        
        # Summarize execution results
        successful_tools = [name for name, result in tool_results.items() if result.get("success")]
        failed_tools = [name for name, result in tool_results.items() if not result.get("success")]
        
        state['tool_results'] = tool_results
        state['execution_log'] = execution_log
        state['successful_tools'] = successful_tools
        state['failed_tools'] = failed_tools
        state['status'] = "ok"
        state['reason'] = f"Executed {len(successful_tools)}/{len(tools_to_execute)} tools successfully"
        
        print(f"📊 실행 완료: 성공 {len(successful_tools)}, 실패 {len(failed_tools)}")
        
    except Exception as e:
        state['tool_results'] = {}
        state['status'] = "error"
        state['reason'] = f"Tool execution node failed: {str(e)}"
        print(f"💥 tool_execution_node 전체 실패: {str(e)}")
    
    return state


def execute_db_query_tool(state: dict) -> dict:
    """
    Execute database query tool for wedding vendor information.
    
    Searches the database for venues, studios, dresses, makeup services
    based on user criteria like location, budget, style preferences.
    """
    from tools import db_query_tool
    
    try:
        # Extract query parameters
        vendor_type = state.get('vendor_type')
        region_keyword = state.get('region_keyword')
        user_memo = state.get('user_memo', {})
        profile = user_memo.get('profile', {})
        budget = profile.get('total_budget_manwon')
        
        # Build SQL query based on state
        if vendor_type == "wedding_hall":
            table_name = "wedding_halls"
        elif vendor_type == "studio":
            table_name = "studios"
        elif vendor_type == "wedding_dress":
            table_name = "wedding_dresses"
        elif vendor_type == "makeup":
            table_name = "makeup"
        else:
            table_name = "wedding_halls"  # Default
        
        # Construct base query
        query = f"SELECT * FROM {table_name}"
        conditions = []
        
        # Add location filter
        if region_keyword:
            conditions.append(f"location LIKE '%{region_keyword}%'")
        
        # Add budget filter
        if budget:
            conditions.append(f"price_manwon <= {budget}")
        
        # Add conditions to query
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " LIMIT 10"
        
        print(f"🗄️ DB 쿼리: {query}")
        
        # Execute query using tools.py function
        result_str = db_query_tool(query)
        
        # Parse results (simplified for demo)
        if "Error" in result_str or "failed" in result_str:
            return {
                "success": False,
                "error": result_str,
                "data": None
            }
        
        # Mock data parsing (in real implementation, parse the SQL result)
        mock_count = 1 if vendor_type else 0
        
        return {
            "success": True,
            "data": {
                "query_executed": query,
                "total_count": mock_count,
                "results": result_str[:100] + "..." if len(result_str) > 100 else result_str
            },
            "message": f"Found {mock_count} matching vendors"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Database query execution failed: {str(e)}",
            "data": None
        }


def execute_web_search_tool(state: dict) -> dict:
    """
    Execute web search tool for current trends and reviews.
    """
    from tools import web_search_tool
    
    try:
        # Generate search query based on state
        vendor_type = state.get('vendor_type', '')
        region_keyword = state.get('region_keyword', '')
        user_input = state.get('user_input', '')
        
        # Build search query
        search_terms = []
        
        if vendor_type:
            if vendor_type == "wedding_hall":
                search_terms.append("웨딩홀")
            elif vendor_type == "studio":
                search_terms.append("웨딩 스튜디오")
            elif vendor_type == "wedding_dress":
                search_terms.append("웨딩드레스")
            elif vendor_type == "makeup":
                search_terms.append("웨딩 메이크업")
        
        if region_keyword:
            search_terms.append(region_keyword)
        
        # Add trend keywords from user input
        if any(keyword in user_input for keyword in ['트렌드', '최신', '요즘', '인기']):
            search_terms.append("2025 트렌드")
        
        if any(keyword in user_input for keyword in ['후기', '리뷰']):
            search_terms.append("후기 리뷰")
        
        search_query = " ".join(search_terms) or "웨딩 정보"
        
        print(f"🌐 웹 검색: {search_query}")
        
        # Execute search using tools.py function
        search_results = web_search_tool(search_query)
        
        return {
            "success": True,
            "data": {
                "search_query": search_query,
                "total_results": 3,  # Tavily returns max 3 results
                "results": str(search_results)[:200] + "..." if len(str(search_results)) > 200 else str(search_results)
            },
            "message": "Found 3 recent web results"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Web search execution failed: {str(e)}",
            "data": None
        }


def execute_calculator_tool(state: dict) -> dict:
    """
    Execute calculator tool for budget and timeline calculations.
    """
    from tools import calculator_tool
    
    try:
        user_memo = state.get('user_memo', {})
        profile = user_memo.get('profile', {})
        user_input = state.get('user_input', '')
        
        total_budget = profile.get('total_budget_manwon', 0)
        guest_count = profile.get('guest_count', 100)
        
        # Determine calculation type based on input
        if any(keyword in user_input for keyword in ['1인당', '인당', '게스트']):
            # Per-person calculation
            if total_budget:
                expression = f"{total_budget * 10000} / {guest_count}"
                calc_result = calculator_tool(expression)
                
                return {
                    "success": True,
                    "data": {
                        "calculation_type": "per_person_budget",
                        "expression": expression,
                        "result": calc_result,
                        "total_budget_manwon": total_budget,
                        "guest_count": guest_count
                    },
                    "message": f"Per-person budget: {calc_result}원"
                }
        
        # Default: Budget breakdown calculation
        if total_budget:
            # Wedding budget breakdown (Korean standard)
            venue_pct = 40  # 40% for venue
            photography_pct = 15  # 15% for photography
            dress_pct = 10  # 10% for dress
            makeup_pct = 5   # 5% for makeup
            etc_pct = 30     # 30% for others
            
            venue_budget = calculator_tool(f"{total_budget} * {venue_pct} / 100")
            photo_budget = calculator_tool(f"{total_budget} * {photography_pct} / 100")
            dress_budget = calculator_tool(f"{total_budget} * {dress_pct} / 100")
            makeup_budget = calculator_tool(f"{total_budget} * {makeup_pct} / 100")
            etc_budget = calculator_tool(f"{total_budget} * {etc_pct} / 100")
            
            # Calculate potential savings (assume 15% negotiation potential)
            savings = calculator_tool(f"{total_budget} * 15 / 100")
            
            return {
                "success": True,
                "data": {
                    "calculation_type": "budget_breakdown",
                    "total_budget_manwon": total_budget,
                    "venue_budget_manwon": venue_budget,
                    "photography_budget_manwon": photo_budget,
                    "dress_budget_manwon": dress_budget,
                    "makeup_budget_manwon": makeup_budget,
                    "etc_budget_manwon": etc_budget,
                    "total_potential_savings": savings
                },
                "message": f"Budget calculation completed for {total_budget}만원 total budget"
            }
        
        # Fallback: Simple calculation from user input
        # Extract numbers and operators from user input for basic math
        import re
        math_pattern = r'[\d+\-*/().\s]+'
        math_expressions = re.findall(math_pattern, user_input)
        
        if math_expressions:
            expression = ''.join(math_expressions).strip()
            if expression:
                calc_result = calculator_tool(expression)
                return {
                    "success": True,
                    "data": {
                        "calculation_type": "user_expression",
                        "expression": expression,
                        "result": calc_result
                    },
                    "message": f"Calculation result: {calc_result}"
                }
        
        return {
            "success": False,
            "error": "No valid calculation parameters found",
            "data": None
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Calculator execution failed: {str(e)}",
            "data": None
        }


def execute_user_db_update_tool(state: dict) -> dict:
    """
    Execute user database update tool for profile changes.
    """
    from tools import user_db_update_tool
    
    try:
        user_id = state.get('user_id')
        update_type = state.get('update_type')
        user_input = state.get('user_input', '')
        
        if not user_id:
            return {
                "success": False,
                "error": "No user_id provided for update",
                "data": None
            }
        
        changes_made = 0
        update_details = []
        
        # Process different update types
        if update_type == "wedding_date":
            # Extract date from user input (simplified)
            import re
            date_patterns = [
                r'(\d{4})[년-](\d{1,2})[월-](\d{1,2})',  # 2025년12월25일
                r'(\d{1,2})[월-](\d{1,2})[일]',          # 12월25일
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, user_input)
                if match:
                    if len(match.groups()) == 3:
                        year, month, day = match.groups()
                        date_value = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                    else:
                        year = "2025"  # Default year
                        month, day = match.groups()
                        date_value = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                    
                    result = user_db_update_tool(state, user_id, "wedding_date", date_value)
                    if "Successfully" in result:
                        changes_made += 1
                        update_details.append(f"wedding_date: {date_value}")
                    break
        
        elif update_type == "budget":
            # Extract budget from user input
            import re
            budget_patterns = [
                r'(\d+)억',     # 2억
                r'(\d+)천만',   # 5천만
                r'(\d+)만원?',  # 3000만원
            ]
            
            for pattern in budget_patterns:
                match = re.search(pattern, user_input)
                if match:
                    value = int(match.group(1))
                    if '억' in pattern:
                        budget_manwon = value * 10000
                    elif '천만' in pattern:
                        budget_manwon = value * 1000
                    else:
                        budget_manwon = value
                    
                    result = user_db_update_tool(state, user_id, "total_budget_manwon", budget_manwon)
                    if "Successfully" in result:
                        changes_made += 1
                        update_details.append(f"budget: {budget_manwon}만원")
                    break
        
        elif update_type == "guest_count":
            # Extract guest count
            import re
            guest_match = re.search(r'(\d+)명?[의]?.*[손님|게스트|하객]', user_input)
            if guest_match:
                guest_count = int(guest_match.group(1))
                result = user_db_update_tool(state, user_id, "guest_count", guest_count)
                if "Successfully" in result:
                    changes_made += 1
                    update_details.append(f"guest_count: {guest_count}명")
        
        if changes_made > 0:
            return {
                "success": True,
                "data": {
                    "changes_made": changes_made,
                    "update_details": update_details,
                    "user_id": user_id
                },
                "message": f"Successfully updated {changes_made} profile fields"
            }
        else:
            return {
                "success": False,
                "error": "No valid update information found in user input",
                "data": None
            }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"User update execution failed: {str(e)}",
            "data": None
        }


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
        
        # Add tool results context
        successful_tools = [r for r in tool_results if r.get('success')]
        if successful_tools:
            tools_summary = []
            for result in successful_tools:
                tool_name = result['tool_name']
                output = result.get('output', {})
                
                if isinstance(output, dict) and output.get('success'):
                    data = output.get('data', {})
                    if tool_name == 'db_query_tool':
                        count = data.get('total_count', 0)
                        tools_summary.append(f"데이터베이스 검색: {count}개 결과 발견")
                    elif tool_name == 'web_search_tool':
                        count = data.get('total_count', 0)
                        tools_summary.append(f"웹 검색: {count}개 관련 정보 수집")
                    elif tool_name == 'calculator_tool':
                        result_val = data.get('result')
                        tools_summary.append(f"계산 결과: {result_val}")
                    elif tool_name == 'user_db_update_tool':
                        field = data.get('field', 'unknown')
                        tools_summary.append(f"프로필 업데이트: {field} 정보 저장")
                else:
                    tools_summary.append(f"{tool_name}: 실행됨")
            
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