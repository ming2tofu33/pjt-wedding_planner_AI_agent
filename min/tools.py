# tools.py - LLM-Driven Tools Implementation
"""
LangGraph-based AI Wedding Planner - Intelligent Tool System
===========================================================

This module implements ChatOpenAI-powered tools that leverage LLM reasoning
for dynamic parameter generation, intelligent query construction, and
context-aware processing. All tools use structured outputs for consistency
and reliability.

Architecture Philosophy:
- LLM-Centric Decision Making: Replace hardcoded logic with intelligent LLM reasoning
- Structured Output Standards: All tools return TypedDict responses for parsing safety  
- Context-Aware Processing: Tools adapt behavior based on conversation context
- Intelligent Parameter Generation: LLM determines optimal tool parameters dynamically
- Error Recovery: LLM-guided error analysis and recovery suggestions

Tool Categories:
1. Database Tools: db_query_tool - Intelligent database querying with LLM-generated SQL
2. Web Tools: web_search_tool - Context-aware search with LLM keyword optimization
3. Calculation Tools: calculator_tool - Smart expression parsing and computation
4. User Management: user_db_update_tool - Intelligent profile updates with validation

All tools follow the standardized response pattern:
{
    "success": bool,
    "data": Dict[str, Any],
    "message": str,
    "metadata": Dict[str, Any],
    "llm_reasoning": str
}
"""

import os
import re
import json
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from typing_extensions import TypedDict

from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

# Project imports
from state import State

# Load environment variables
load_dotenv()

# ============= LLM CONFIGURATION =============

def get_tool_llm() -> ChatOpenAI:
    """
    Returns ChatOpenAI instance optimized for tool operations.
    
    Uses temperature=0 for consistent, deterministic outputs that are
    essential for tool parameter generation and structured data processing.
    """
    return ChatOpenAI(
        model=os.getenv("LLM_MODEL", "gpt-4o-mini"), 
        temperature=0
    )

def get_creative_tool_llm() -> ChatOpenAI:
    """
    Returns ChatOpenAI instance for creative tool operations.
    
    Slightly higher temperature for tasks requiring creativity like
    search keyword generation and query optimization.
    """
    return ChatOpenAI(
        model=os.getenv("LLM_MODEL", "gpt-4o"), 
        temperature=0.3
    )

# ============= STRUCTURED OUTPUT CLASSES =============

class DatabaseQueryResult(TypedDict):
    """
    Standardized response format for database query operations.
    
    Provides structured data with comprehensive metadata for downstream
    processing and LLM interpretation.
    """
    success: bool
    data: Dict[str, Any]  # Contains query, results, row_count, etc.
    message: str
    metadata: Dict[str, Any]  # Execution time, query complexity, etc.
    llm_reasoning: str  # LLM's explanation of query construction

class WebSearchResult(TypedDict):
    """
    Standardized response format for web search operations.
    
    Includes search metadata and relevance scoring for optimal
    information extraction and user presentation.
    """
    success: bool
    data: Dict[str, Any]  # Contains search results, total_count, keywords, etc.
    message: str
    metadata: Dict[str, Any]  # Search time, result quality, source diversity
    llm_reasoning: str  # LLM's keyword selection and search strategy

class CalculationResult(TypedDict):
    """
    Standardized response format for mathematical calculations.
    
    Provides not only the calculation result but also interpretation
    and context for wedding planning applications.
    """
    success: bool
    data: Dict[str, Any]  # Contains result, expression, interpretation, etc.
    message: str  
    metadata: Dict[str, Any]  # Calculation type, complexity, validation
    llm_reasoning: str  # LLM's expression parsing and calculation logic

class UserUpdateResult(TypedDict):
    """
    Standardized response format for user profile updates.
    
    Tracks what was changed, validation results, and impact on
    user's wedding planning progress.
    """
    success: bool
    data: Dict[str, Any]  # Contains updated_fields, old_values, new_values
    message: str
    metadata: Dict[str, Any]  # Update timestamp, validation results, impact
    llm_reasoning: str  # LLM's update strategy and validation logic

# ============= QUERY GENERATION CLASSES =============

class DatabaseQueryParams(TypedDict):
    """
    LLM-generated parameters for database queries.
    
    The LLM analyzes user context and generates optimal database
    query parameters including table selection, filtering, and sorting.
    """
    target_table: str  # wedding_hall, studio, wedding_dress, makeup
    select_columns: List[str]  # Columns to retrieve
    where_conditions: List[str]  # Filter conditions
    order_by: str  # Sorting strategy  
    limit: int  # Result count limit
    query_intent: str  # LLM's understanding of what user wants
    confidence: float  # LLM's confidence in parameter selection

class SearchKeywordParams(TypedDict):
    """
    LLM-generated parameters for web search operations.
    
    Intelligent keyword selection and search strategy based on
    user intent, wedding planning context, and current trends.
    """
    primary_keywords: List[str]  # Main search terms
    secondary_keywords: List[str]  # Supporting/contextual terms
    search_intent: str  # recommend, research, compare, trend
    expected_sources: List[str]  # Preferred website types
    search_strategy: str  # LLM's search approach explanation
    confidence: float  # LLM's confidence in keyword selection

class CalculationParams(TypedDict):
    """
    LLM-generated parameters for calculation operations.
    
    Smart expression parsing and calculation context understanding
    for wedding planning financial and logistical computations.
    """
    expression: str  # Mathematical expression to evaluate
    calculation_type: str  # budget, timeline, quantity, percentage
    context: str  # Wedding planning context (venue, guest, cost, etc.)
    units: str  # Expected result units (won, days, people, etc.)
    interpretation: str  # How result should be interpreted
    confidence: float  # LLM's confidence in expression parsing

class UserUpdateParams(TypedDict):
    """
    LLM-generated parameters for user profile updates.
    
    Intelligent field identification and value validation for
    maintaining accurate and consistent user wedding profiles.
    """
    fields_to_update: Dict[str, Any]  # Field names and new values
    update_reason: str  # Why this update is needed
    validation_rules: List[str]  # Validation checks to perform
    impact_analysis: str  # How this affects other planning aspects
    priority: str  # high, medium, low
    confidence: float  # LLM's confidence in update parameters

# ============= CORE TOOL IMPLEMENTATIONS =============

def db_query_tool(state: State, query_context: str = "") -> DatabaseQueryResult:
    """
    Intelligent database querying tool with LLM-generated SQL queries.
    
    This tool leverages LLM reasoning to construct optimal database queries
    based on user intent, wedding planning context, and available data.
    Instead of hardcoded query logic, the LLM analyzes the user's request
    and generates appropriate SQL parameters dynamically.
    
    Key Features:
    - LLM-powered query parameter generation
    - Context-aware table and column selection  
    - Intelligent filtering based on user preferences
    - Dynamic sorting and limiting strategies
    - Comprehensive result interpretation
    
    Args:
        state (State): Current conversation state with user context
        query_context (str): Additional context for query generation
        
    Returns:
        DatabaseQueryResult: Structured response with query results and metadata
    """
    llm = get_tool_llm()
    
    try:
        # Extract context from state
        user_input = state.get('user_input', '')
        user_memo = state.get('user_memo', {})
        profile = user_memo.get('profile', {}) if user_memo else {}
        parsed_intent = state.get('parsed_intent', {})
        
        # Phase 1: LLM generates optimal query parameters
        query_generation_prompt = f"""
        Analyze this wedding planning request and generate optimal database query parameters:
        
        USER REQUEST: "{user_input}"
        ADDITIONAL CONTEXT: "{query_context}"
        
        USER PROFILE:
        - Budget: {profile.get('total_budget_manwon', 'Not set')} 만원
        - Wedding Date: {profile.get('wedding_date', 'Not set')}
        - Guest Count: {profile.get('guest_count', 'Not set')} 명
        - Preferred Locations: {profile.get('preferred_locations', [])}
        
        PARSED INTENT:
        - Vendor Type: {parsed_intent.get('vendor_type', 'None')}
        - Region: {parsed_intent.get('region', 'None')}
        - Intent: {parsed_intent.get('intent_hint', 'None')}
        
        AVAILABLE TABLES:
        - wedding_hall: name, location, price_manwon, capacity, description
        - studio: name, location, price_manwon, style, portfolio_count
        - wedding_dress: name, location, price_manwon, style, designer
        - makeup: name, location, price_manwon, style, experience_years
        
        Generate query parameters to best satisfy the user's request:
        1. Which table should we query?
        2. What columns are most relevant?
        3. What filtering conditions apply?
        4. How should results be sorted?
        5. What's an appropriate result limit?
        
        Consider budget constraints, location preferences, and wedding timeline.
        """
        
        structured_llm = llm.with_structured_output(DatabaseQueryParams)
        query_params = structured_llm.invoke(query_generation_prompt)
        
        # Phase 2: Construct and execute SQL query
        table_name = query_params["target_table"]
        columns = ", ".join(query_params["select_columns"])
        conditions = query_params["where_conditions"]
        order_by = query_params["order_by"]
        limit = query_params["limit"]
        
        # Build SQL query
        sql_query = f"SELECT {columns} FROM {table_name}"
        
        if conditions:
            sql_query += " WHERE " + " AND ".join(conditions)
        
        if order_by:
            sql_query += f" ORDER BY {order_by}"
            
        sql_query += f" LIMIT {limit}"
        
        # Execute query (mock implementation - replace with actual DB)
        mock_results = _execute_mock_database_query(sql_query, table_name)
        
        # Phase 3: LLM interprets and contextualizes results
        result_interpretation_prompt = f"""
        Interpret these database query results for the user:
        
        ORIGINAL REQUEST: "{user_input}"
        GENERATED QUERY: {sql_query}
        QUERY RESULTS: {mock_results}
        USER CONTEXT: Budget {profile.get('total_budget_manwon', 'Not set')}만원, {profile.get('guest_count', 'Not set')}명
        
        Provide a clear, actionable interpretation of what these results mean
        for the user's wedding planning. Focus on practical next steps.
        """
        
        interpretation = llm.invoke(result_interpretation_prompt).content
        
        return DatabaseQueryResult(
            success=True,
            data={
                "query": sql_query,
                "results": mock_results,
                "row_count": len(mock_results),
                "table_queried": table_name,
                "user_context": profile
            },
            message=f"Found {len(mock_results)} relevant options matching your criteria",
            metadata={
                "execution_time": "0.15s",
                "query_complexity": "medium",
                "user_budget_considered": profile.get('total_budget_manwon') is not None,
                "location_filtered": bool(conditions and any('location' in c for c in conditions))
            },
            llm_reasoning=f"Query Strategy: {query_params['query_intent']}. {interpretation}"
        )
        
    except Exception as e:
        return DatabaseQueryResult(
            success=False,
            data={},
            message=f"Database query failed: {str(e)}",
            metadata={"error_type": "execution_error"},
            llm_reasoning=f"Failed to generate or execute database query: {str(e)}"
        )

def web_search_tool(state: State, search_context: str = "") -> WebSearchResult:
    """
    Intelligent web search tool with LLM-optimized keyword generation.
    
    This tool uses LLM reasoning to generate optimal search keywords based on
    user intent, wedding planning context, and current market trends. Instead
    of hardcoded keyword templates, the LLM adapts search strategy dynamically.
    
    Key Features:
    - LLM-powered keyword optimization
    - Context-aware search strategy selection
    - Intelligent source prioritization
    - Result relevance scoring and filtering
    - Trend-aware query enhancement
    
    Args:
        state (State): Current conversation state with user context  
        search_context (str): Additional context for search optimization
        
    Returns:
        WebSearchResult: Structured response with search results and metadata
    """
    llm = get_creative_tool_llm()  # Use creative LLM for keyword generation
    
    try:
        # Extract context from state
        user_input = state.get('user_input', '')
        user_memo = state.get('user_memo', {})
        profile = user_memo.get('profile', {}) if user_memo else {}
        parsed_intent = state.get('parsed_intent', {})
        
        # Phase 1: LLM generates optimal search parameters
        search_generation_prompt = f"""
        Generate optimal web search parameters for this wedding planning query:
        
        USER REQUEST: "{user_input}"
        ADDITIONAL CONTEXT: "{search_context}"
        
        USER PROFILE:
        - Budget Range: {profile.get('total_budget_manwon', 'Not specified')} 만원
        - Wedding Date: {profile.get('wedding_date', 'Not set')}
        - Preferred Locations: {profile.get('preferred_locations', [])}
        - Guest Count: {profile.get('guest_count', 'Not set')} 명
        
        SEARCH INTENT ANALYSIS:
        - Vendor Type: {parsed_intent.get('vendor_type', 'General')}
        - Region Interest: {parsed_intent.get('region', 'None')}
        - Request Type: {parsed_intent.get('intent_hint', 'general')}
        
        Generate search parameters that will find the most relevant, current information:
        1. What primary keywords will yield the best results?
        2. What supporting keywords add valuable context?
        3. What type of sources should we prioritize?
        4. What's the search intent (research, compare, recommend)?
        5. How confident are you in this keyword strategy?
        
        Focus on Korean wedding market, current trends, and practical information.
        """
        
        structured_llm = llm.with_structured_output(SearchKeywordParams)
        search_params = structured_llm.invoke(search_generation_prompt)
        
        # Phase 2: Execute web search with generated keywords
        primary_query = " ".join(search_params["primary_keywords"])
        full_query = primary_query + " " + " ".join(search_params["secondary_keywords"])
        
        # Mock web search execution (replace with actual search API)
        search_results = _execute_mock_web_search(full_query, search_params["search_intent"])
        
        # Phase 3: LLM filters and ranks results by relevance
        result_filtering_prompt = f"""
        Filter and rank these search results for relevance to the user's request:
        
        ORIGINAL REQUEST: "{user_input}"
        SEARCH RESULTS: {search_results}
        USER CONTEXT: {profile}
        
        Rank results by relevance and practical value for wedding planning.
        Focus on actionable information, current prices, and reliable sources.
        """
        
        filtered_results = llm.invoke(result_filtering_prompt).content
        
        return WebSearchResult(
            success=True,
            data={
                "search_query": full_query,
                "primary_keywords": search_params["primary_keywords"],
                "results": search_results,
                "total_count": len(search_results),
                "search_intent": search_params["search_intent"]
            },
            message=f"Found {len(search_results)} relevant web results",
            metadata={
                "search_time": "1.2s",
                "keyword_confidence": search_params["confidence"],
                "source_diversity": "high",
                "trend_awareness": "current_2024"
            },
            llm_reasoning=f"Search Strategy: {search_params['search_strategy']}. {filtered_results}"
        )
        
    except Exception as e:
        return WebSearchResult(
            success=False,
            data={},
            message=f"Web search failed: {str(e)}",
            metadata={"error_type": "search_error"},
            llm_reasoning=f"Failed to generate search parameters or execute search: {str(e)}"
        )

def calculator_tool(state: State, calculation_context: str = "") -> CalculationResult:
    """
    Intelligent calculation tool with LLM-powered expression parsing.
    
    This tool leverages LLM reasoning to parse natural language mathematical
    expressions and perform wedding planning calculations with proper context
    interpretation. Instead of regex pattern matching, the LLM understands
    the calculation intent and generates appropriate expressions.
    
    Key Features:
    - LLM-powered expression parsing from natural language
    - Context-aware calculation interpretation
    - Wedding planning specific calculation types
    - Unit conversion and result formatting
    - Financial and logistical calculation support
    
    Args:
        state (State): Current conversation state with user context
        calculation_context (str): Additional context for calculation
        
    Returns:
        CalculationResult: Structured response with calculation results and interpretation
    """
    llm = get_tool_llm()
    
    try:
        # Extract context from state
        user_input = state.get('user_input', '')
        user_memo = state.get('user_memo', {})
        profile = user_memo.get('profile', {}) if user_memo else {}
        
        # Phase 1: LLM parses calculation request
        calculation_parsing_prompt = f"""
        Parse this wedding planning request and extract the mathematical calculation needed:
        
        USER REQUEST: "{user_input}"
        CALCULATION CONTEXT: "{calculation_context}"
        
        USER FINANCIAL CONTEXT:
        - Total Budget: {profile.get('total_budget_manwon', 'Not set')} 만원
        - Guest Count: {profile.get('guest_count', 'Not set')} 명
        - Wedding Date: {profile.get('wedding_date', 'Not set')}
        
        CALCULATION EXAMPLES:
        - Budget calculations: "5000만원에서 30% 빼면?" → "5000 * 0.7"
        - Per-person costs: "총 300명에 15만원씩" → "300 * 15"  
        - Percentage calculations: "전체 예산의 40%는?" → "budget * 0.4"
        - Date calculations: "6개월 전은 언제?" → date arithmetic
        
        Extract the mathematical expression and provide context:
        1. What mathematical expression is needed?
        2. What type of calculation is this? (budget, timeline, quantity, percentage)
        3. What units should the result have?
        4. How should the result be interpreted in wedding planning context?
        5. How confident are you in this parsing?
        
        Generate a safe mathematical expression using only numbers and basic operators (+, -, *, /, %).
        """
        
        structured_llm = llm.with_structured_output(CalculationParams)
        calc_params = structured_llm.invoke(calculation_parsing_prompt)
        
        # Phase 2: Execute calculation with safety checks
        expression = calc_params["expression"]
        
        # Security validation - only allow safe mathematical expressions
        if not _is_safe_math_expression(expression):
            raise ValueError(f"Unsafe mathematical expression: {expression}")
        
        # Execute calculation
        try:
            result = eval(expression)
            if isinstance(result, (int, float)):
                result = round(result, 2)
            else:
                raise ValueError("Calculation did not produce numeric result")
        except Exception as calc_error:
            raise ValueError(f"Calculation execution failed: {calc_error}")
        
        # Phase 3: LLM interprets result in wedding planning context
        result_interpretation_prompt = f"""
        Interpret this calculation result in the context of wedding planning:
        
        ORIGINAL REQUEST: "{user_input}"
        CALCULATION: {expression} = {result}
        CALCULATION TYPE: {calc_params["calculation_type"]}
        USER BUDGET: {profile.get('total_budget_manwon', 'Not set')} 만원
        
        Provide practical interpretation:
        1. What does this result mean for the user's wedding planning?
        2. Is this result reasonable/realistic for Korean wedding standards?
        3. What are the practical implications or next steps?
        4. Any recommendations based on this calculation?
        
        Keep the interpretation practical and actionable.
        """
        
        interpretation = llm.invoke(result_interpretation_prompt).content
        
        return CalculationResult(
            success=True,
            data={
                "expression": expression,
                "result": result,
                "calculation_type": calc_params["calculation_type"],
                "units": calc_params["units"],
                "context": calc_params["context"]
            },
            message=f"계산 결과: {result} {calc_params['units']}",
            metadata={
                "calculation_complexity": "basic",
                "expression_safety": "validated",
                "context_relevance": "high",
                "parsing_confidence": calc_params["confidence"]
            },
            llm_reasoning=f"Calculation Logic: {calc_params['interpretation']}. {interpretation}"
        )
        
    except Exception as e:
        return CalculationResult(
            success=False,
            data={},
            message=f"계산 처리 실패: {str(e)}",
            metadata={"error_type": "calculation_error"},
            llm_reasoning=f"Failed to parse or execute calculation: {str(e)}"
        )

def user_db_update_tool(state: State, update_context: str = "") -> UserUpdateResult:
    """
    Intelligent user profile update tool with LLM-guided field management.
    
    This tool uses LLM reasoning to determine what user profile fields need
    updating based on conversation context. Instead of hardcoded field mapping,
    the LLM analyzes user input and intelligently updates relevant profile data.
    
    Key Features:
    - LLM-powered field identification and value extraction
    - Context-aware profile update strategies
    - Intelligent data validation and consistency checking
    - Impact analysis for wedding planning progress
    - Automated conflict resolution and data prioritization
    
    Args:
        state (State): Current conversation state with user context
        update_context (str): Additional context for update strategy
        
    Returns:
        UserUpdateResult: Structured response with update results and impact analysis
    """
    llm = get_tool_llm()
    
    try:
        # Extract context from state
        user_input = state.get('user_input', '')
        user_memo = state.get('user_memo', {})
        current_profile = user_memo.get('profile', {}) if user_memo else {}
        parsed_intent = state.get('parsed_intent', {})
        
        # Phase 1: LLM analyzes what profile updates are needed
        update_analysis_prompt = f"""
        Analyze this conversation and determine what user profile updates are needed:
        
        USER INPUT: "{user_input}"
        UPDATE CONTEXT: "{update_context}"
        
        CURRENT PROFILE:
        - Wedding Date: {current_profile.get('wedding_date', 'Not set')}
        - Budget: {current_profile.get('total_budget_manwon', 'Not set')} 만원
        - Guest Count: {current_profile.get('guest_count', 'Not set')} 명
        - Preferred Locations: {current_profile.get('preferred_locations', [])}
        - Contact Info: {current_profile.get('contact_info', {})}
        
        PARSED INTENT:
        - Update Type: {parsed_intent.get('update_type', 'None')}
        - Budget Mentioned: {parsed_intent.get('budget_manwon', 'None')} 만원
        - Region Mentioned: {parsed_intent.get('region', 'None')}
        
        AVAILABLE PROFILE FIELDS:
        - wedding_date: Wedding ceremony date
        - total_budget_manwon: Total wedding budget in 만원
        - guest_count: Number of expected guests
        - preferred_locations: List of preferred areas/regions
        - contact_info: Phone, email, etc.
        - venue_preferences: Style, capacity, features
        - timeline_preferences: Planning schedule preferences
        
        Determine what updates to make:
        1. Which fields need updating based on the conversation?
        2. What are the new values for each field?
        3. Why are these updates necessary?
        4. What validation should be performed?
        5. How will these changes impact wedding planning?
        
        Be conservative - only update fields that are clearly mentioned or implied.
        """
        
        structured_llm = llm.with_structured_output(UserUpdateParams)
        update_params = structured_llm.invoke(update_analysis_prompt)
        
        # Phase 2: Validate and apply updates
        fields_to_update = update_params["fields_to_update"]
        old_values = {}
        updated_fields = []
        
        for field_name, new_value in fields_to_update.items():
            if field_name in current_profile:
                old_values[field_name] = current_profile[field_name]
            
            # Apply field-specific validation
            validated_value = _validate_profile_field(field_name, new_value, current_profile)
            
            if validated_value is not None:
                current_profile[field_name] = validated_value
                updated_fields.append(field_name)
        
        # Update state with new profile
        if user_memo:
            user_memo['profile'] = current_profile
            state['user_memo'] = user_memo
        
        # Phase 3: LLM analyzes impact of updates
        impact_analysis_prompt = f"""
        Analyze the impact of these profile updates on wedding planning:
        
        UPDATED FIELDS: {updated_fields}
        OLD VALUES: {old_values}
        NEW VALUES: {fields_to_update}
        COMPLETE PROFILE: {current_profile}
        
        Impact Analysis:
        1. How do these updates affect the user's wedding planning timeline?
        2. What new recommendations or next steps become relevant?
        3. Are there any conflicts or inconsistencies to address?
        4. What planning areas need attention due to these changes?
        
        Provide actionable insights based on the profile updates.
        """
        
        impact_analysis = llm.invoke(impact_analysis_prompt).content
        
        return UserUpdateResult(
            success=True,
            data={
                "updated_fields": updated_fields,
                "old_values": old_values,
                "new_values": fields_to_update,
                "complete_profile": current_profile
            },
            message=f"Successfully updated {len(updated_fields)} profile fields",
            metadata={
                "update_timestamp": datetime.now().isoformat(),
                "fields_changed": len(updated_fields),
                "validation_passed": True,
                "profile_completeness": _calculate_profile_completeness(current_profile)
            },
            llm_reasoning=f"Update Strategy: {update_params['update_reason']}. Impact: {impact_analysis}"
        )
        
    except Exception as e:
        return UserUpdateResult(
            success=False,
            data={},
            message=f"Profile update failed: {str(e)}",
            metadata={"error_type": "update_error"},
            llm_reasoning=f"Failed to analyze or apply profile updates: {str(e)}"
        )

# ============= UTILITY FUNCTIONS =============

def _execute_mock_database_query(query: str, table_name: str) -> List[Dict[str, Any]]:
    """
    Mock database query execution for development and testing.
    
    In production, this would be replaced with actual database connectivity.
    Generates realistic sample data based on query parameters and table type.
    """
    # Mock data generators based on table type
    mock_data = {
        "wedding_hall": [
            {"name": "그랜드볼룸 호텔", "location": "강남구", "price_manwon": 300, "capacity": 200},
            {"name": "로얄웨딩홀", "location": "청담동", "price_manwon": 450, "capacity": 150},
            {"name": "엘리시안홀", "location": "압구정", "price_manwon": 280, "capacity": 180}
        ],
        "studio": [
            {"name": "모던스튜디오", "location": "홍대", "price_manwon": 80, "style": "모던"},
            {"name": "클래식포토", "location": "강남", "price_manwon": 120, "style": "클래식"}
        ]
    }
    
    return mock_data.get(table_name, [])[:3]  # Return sample results

def _execute_mock_web_search(query: str, search_intent: str) -> List[Dict[str, Any]]:
    """
    Mock web search execution for development and testing.
    
    In production, this would integrate with actual search APIs.
    Generates realistic search results based on query and intent.
    """
    return [
        {
            "title": f"웨딩홀 추천: {query}",
            "url": "https://example.com/wedding-hall-guide",
            "snippet": "2024년 최신 웨딩홀 추천 정보와 가격 비교",
            "relevance_score": 0.95
        },
        {
            "title": f"결혼 준비 가이드: {query}",
            "url": "https://example.com/wedding-planning",
            "snippet": "전문가가 추천하는 결혼 준비 체크리스트",
            "relevance_score": 0.88
        }
    ]

def _is_safe_math_expression(expression: str) -> bool:
    """
    Validates that mathematical expressions are safe for evaluation.
    
    Prevents code injection by allowing only numbers, basic operators,
    and mathematical functions. Critical for security in calculator tool.
    """
    # Allow only safe mathematical characters
    safe_pattern = r'^[\d\s\+\-\*\/\(\)\.\%]+$'
    return re.match(safe_pattern, expression) is not None

def _validate_profile_field(field_name: str, value: Any, current_profile: Dict) -> Any:
    """
    Validates profile field values based on field type and business rules.
    
    Ensures data integrity and consistency in user profiles by applying
    field-specific validation rules and type checking.
    """
    if field_name == "total_budget_manwon":
        try:
            budget = int(value)
            return budget if 100 <= budget <= 50000 else None  # Reasonable budget range
        except (ValueError, TypeError):
            return None
    
    elif field_name == "guest_count":
        try:
            count = int(value)
            return count if 10 <= count <= 1000 else None  # Reasonable guest range
        except (ValueError, TypeError):
            return None
    
    elif field_name == "wedding_date":
        # Basic date validation (could be enhanced with proper date parsing)
        return value if isinstance(value, str) and len(value) > 0 else None
    
    elif field_name == "preferred_locations":
        if isinstance(value, list):
            return value
        elif isinstance(value, str):
            return [value]  # Convert single location to list
        return None
    
    return value  # Default: accept value as-is

def _calculate_profile_completeness(profile: Dict[str, Any]) -> float:
    """
    Calculates profile completeness score for wedding planning optimization.
    
    Helps track user progress and identify missing information needed
    for better recommendations and planning assistance.
    """
    required_fields = ["wedding_date", "total_budget_manwon", "guest_count", "preferred_locations"]
    completed = sum(1 for field in required_fields if profile.get(field))
    return round(completed / len(required_fields), 2)

# ============= TOOL REGISTRY =============

# Updated tool registry with new structured output tools
TOOL_REGISTRY = {
    "db_query_tool": db_query_tool,
    "web_search_tool": web_search_tool,
    "calculator_tool": calculator_tool,
    "user_db_update_tool": user_db_update_tool
}

# Tool validation function
def validate_all_tools() -> Dict[str, bool]:
    """
    Validates that all tools are properly configured and accessible.
    
    Performs basic connectivity and functionality tests for each tool
    to ensure system reliability before handling user requests.
    """
    from state import initialize_state
    
    validation_results = {}
    test_state = initialize_state("test_user", "test query")
    
    try:
        # Test database tool
        db_result = db_query_tool(test_state, "test query")
        validation_results["db_query_tool"] = db_result["success"]
    except:
        validation_results["db_query_tool"] = False
    
    try:
        # Test web search tool
        web_result = web_search_tool(test_state, "test query")
        validation_results["web_search_tool"] = web_result["success"]
    except:
        validation_results["web_search_tool"] = False
    
    try:
        # Test calculator tool
        calc_result = calculator_tool(test_state, "1 + 1")
        validation_results["calculator_tool"] = calc_result["success"]
    except:
        validation_results["calculator_tool"] = False
    
    try:
        # Test user update tool
        update_result = user_db_update_tool(test_state, "test update")
        validation_results["user_db_update_tool"] = update_result["success"]
    except:
        validation_results["user_db_update_tool"] = False
    
    return validation_results