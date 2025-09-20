from typing import TypedDict, List, Dict, Optional, Union, Literal
from datetime import datetime
from enum import Enum

# ============= STRUCTURED TYPE DEFINITIONS =============
class IntentType(TypedDict):
    """Structured intent analysis result"""
    intent: str                    # Main intent: "venue_search", "budget_calculation", "general_question"
    entities: Dict[str, Union[str, int, float]]  # Extracted entities
    confidence: float             # Confidence score (0.0-1.0)
    intent_category: Literal["search_request", "calculation", "general_chat", "booking_action"]

class UserProfile(TypedDict):
    """User's basic profile information"""
    name: Optional[str]
    wedding_date: Optional[str]   # ISO format date
    total_budget: Optional[int]   # In KRW
    guest_count: Optional[int]
    partner_name: Optional[str]

class UserPreferences(TypedDict):
    """User's preferences and style choices"""
    style_preferences: List[str]   # ["모던한 스타일", "클래식"]
    location_preferences: List[str] # ["강남", "홍대"]  
    priority_factors: List[str]    # ["budget", "location", "style"]

class UserMemo(TypedDict):
    """Complete user memory structure"""
    profile: UserProfile
    preferences: UserPreferences
    confirmed_bookings: List[Dict[str, str]]  # Confirmed reservations
    search_history: List[Dict[str, str]]      # Past search queries
    conversation_summary: Optional[str]       # AI-generated summary of past conversations

class ConversationMessage(TypedDict):
    """Single conversation message structure"""
    timestamp: datetime
    role: Literal["user", "assistant"] 
    content: str
    message_type: Literal["query", "response", "action_confirmation"]

class ToolResult(TypedDict):
    """Individual tool execution result"""
    tool_name: str
    execution_time: datetime
    success: bool
    data: Dict[str, any]          # Tool-specific result data
    error_message: Optional[str]

class ErrorInfo(TypedDict):
    """Error handling information"""
    error_type: str               # "parsing_failed", "tool_execution_failed", "llm_error"
    error_message: str
    node_name: str               # Which node produced the error
    recovery_action: Optional[str] # Suggested recovery action
    timestamp: datetime

class NodeExecutionLog(TypedDict):
    """Node execution tracking"""
    node_name: str
    start_time: datetime
    end_time: Optional[datetime]
    success: bool
    processing_notes: Optional[str]

# ============= MAIN STATE STRUCTURE =============
class WeddingChatbotState(TypedDict):
    """
    Core state structure for Wedding Planner AI Chatbot using LangGraph
    
    Data Flow:
    1. Raw user input → parsing_node → parsed_intent
    2. Load user context → memo_check_node → user_memo
    3. Route decision → conditional_router → routing_decision  
    4. Execute tools → tool_execution_node → tool_results
    5. Update memory → memo_update_node → updated user_memo
    6. Generate response → response_generation_node → final_response
    """
    
    # ============= USER IDENTIFICATION =============
    user_id: Optional[str]         # Persistent user identifier for long-term memory
    session_id: Optional[str]      # Current conversation session identifier
    
    # ============= INPUT PROCESSING =============
    user_input: str               # Original raw user input text
    parsed_intent: Optional[IntentType]  # Structured intent analysis result
    
    # ============= MEMORY & CONTEXT =============
    user_memo: Optional[UserMemo]  # Persistent user memory across sessions
    conversation_history: List[ConversationMessage]  # Current session conversation
    
    # ============= ROUTING & EXECUTION =============
    routing_decision: Optional[Literal["tool_execution", "general_response", "recommendation"]]
    tools_to_execute: List[str]    # Tools scheduled for execution
    tool_results: Dict[str, ToolResult]  # Results from executed tools
    
    # ============= RECOMMENDATION SYSTEM =============  
    recommendations: Optional[List[Dict[str, any]]]  # AI recommendations (MVP: skip)
    
    # ============= RESPONSE GENERATION =============
    response_content: Optional[str]  # Core response content before formatting
    final_response: str            # Final formatted response to user
    response_metadata: Optional[Dict[str, str]]  # Generation metadata (tone, format, etc.)
    
    # ============= ERROR HANDLING =============
    error_info: Optional[ErrorInfo]  # Comprehensive error information
    
    # ============= SYSTEM TRACKING =============
    current_node: Optional[str]    # Currently processing node name
    processing_timestamp: datetime # Processing start time
    node_execution_log: List[NodeExecutionLog]  # Complete execution tracking