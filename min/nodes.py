# nodes.py
# LangGraph의 개별 노드 역할을 하는 함수들을 정의합니다.

import os
import json
import re
import traceback
from datetime import datetime
from typing import List, Dict, Any, Optional

from openai import OpenAI
from dotenv import load_dotenv

# 프로젝트 모듈들 임포트
from state import create_empty_user_memo, get_memo_file_path, touch_processing_timestamp
from db import db
from tools import db_query_tool, user_db_update_tool, web_search_tool, calculator_tool

# LLM 클라이언트 초기화
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 노드에 사용될 도구 매핑
TOOLS = {
    "db_query_tool": db_query_tool,
    "user_db_update_tool": user_db_update_tool,
    "web_search_tool": web_search_tool,
    "calculator_tool": calculator_tool,
}

def parsing_node(state: dict) -> dict:
    """사용자 입력을 분석하여 의도(intent)를 파악하고 상태를 업데이트하는 노드"""
    state['processing_timestamp'] = datetime.now().isoformat(timespec="seconds")
    user_input = state.get('user_input', '')

    if not user_input or not user_input.strip():
        state['status'] = "error"
        state['reason'] = "Empty user input"
        return state

    try:
        system_prompt = """You are a wedding planning assistant. Analyze the user input and extract:

1. VENDOR_TYPE: wedding_hall, studio, wedding_dress, makeup, or null
2. REGION: Korean location keywords (강남, 청담, 압구정, etc.) or null  
3. INTENT_HINT: 
   - "recommend": 업체 추천 요청
   - "tool": DB 업데이트, 계산, 검색이 필요한 요청
   - "general": 일반 상담, 정보 제공
4. UPDATE_TYPE: 사용자 정보 업데이트인 경우 (wedding_date, budget, guest_count, preferred_location, null)
5. BUDGET_MENTIONED: any budget numbers in Korean won (만원 units)

Respond ONLY in this JSON format:
{
    "vendor_type": "wedding_hall|studio|wedding_dress|makeup|null",
    "region_keyword": "지역명|null", 
    "intent_hint": "recommend|tool|general",
    "update_type": "wedding_date|budget|guest_count|preferred_location|null",
    "budget_manwon": number_or_null,
    "confidence": 0.0-1.0
}

Examples:
- "강남 웨딩홀 추천해줘" → {"vendor_type": "wedding_hall", "region_keyword": "강남", "intent_hint": "recommend", "update_type": null, "budget_manwon": null, "confidence": 0.9}
- "결혼식 날짜 크리스마스로 바꿔줘" → {"vendor_type": null, "region_keyword": null, "intent_hint": "tool", "update_type": "wedding_date", "budget_manwon": null, "confidence": 0.95}
- "총 예산 5천만원으로 수정해주세요" → {"vendor_type": null, "region_keyword": null, "intent_hint": "tool", "update_type": "budget", "budget_manwon": 5000, "confidence": 0.95}"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ],
            temperature=0.1,
            max_tokens=300
        )
        
        parsed_response = json.loads(response.choices[0].message.content)
        
        state['vendor_type'] = parsed_response.get("vendor_type")
        if state['vendor_type'] == "null":
            state['vendor_type'] = None
            
        state['region_keyword'] = parsed_response.get("region_keyword") 
        if state['region_keyword'] == "null":
            state['region_keyword'] = None
            
        state['intent_hint'] = parsed_response.get("intent_hint", "general")
        state['update_type'] = parsed_response.get("update_type")
        
        budget = parsed_response.get("budget_manwon")
        if budget and isinstance(budget, (int, float)):
            state['total_budget_manwon'] = int(budget)
        
        state['status'] = "ok"
        state['error_info'] = {
            "parsing_confidence": parsed_response.get("confidence", 0.0),
            "raw_llm_response": parsed_response
        }
        
    except Exception as e:
        state['status'] = "error" 
        state['reason'] = f"Parsing node error: {str(e)}"
        state['intent_hint'] = "general"
    
    return state


def memo_check_node(state: dict) -> dict:
    """사용자의 장기 메모(JSON 파일)를 불러오거나 새로 생성하는 노드"""
    user_id = state.get('user_id')
    if not user_id:
        state['status'] = "error"
        state['reason'] = "No user_id provided for memory check"
        return state
    
    try:
        memo_file_path = get_memo_file_path(user_id)
        state['memo_file_path'] = memo_file_path
        
        if os.path.exists(memo_file_path):
            with open(memo_file_path, 'r', encoding='utf-8') as f:
                user_memo = json.load(f)
            
            if not isinstance(user_memo, dict):
                raise ValueError("Invalid memory format: not a dictionary")
            
            if 'profile' not in user_memo:
                raise ValueError("Invalid memory format: missing profile")
            
            if 'version' not in user_memo:
                user_memo['version'] = "1.0"
            
            memo_user_id = user_memo.get('profile', {}).get('user_id')
            if memo_user_id != user_id:
                raise ValueError(f"User ID mismatch: expected {user_id}, found {memo_user_id}")
            
            state['user_memo'] = user_memo
            state['memo_needs_update'] = False
        else:
            user_memo = create_empty_user_memo(user_id)
            state['user_memo'] = user_memo
            state['memo_needs_update'] = True
        
        profile = user_memo.get('profile', {})
        if profile.get('total_budget_manwon'):
            state['total_budget_manwon'] = profile['total_budget_manwon']
        if profile.get('wedding_date'):
            state['wedding_date'] = profile['wedding_date']
        if profile.get('guest_count'):
            state['guest_count'] = profile['guest_count']
        if profile.get('preferred_locations'):
            state['preferred_locations'] = profile['preferred_locations']
        
        conversation_summary = user_memo.get('conversation_summary')
        if conversation_summary:
            state['conversation_summary'] = conversation_summary
        
        state['status'] = "ok"
        state['memo_debug'] = {
            "memo_file_exists": os.path.exists(memo_file_path),
            "memo_version": user_memo.get('version', 'unknown'),
            "profile_completeness": len([k for k, v in profile.items() if v is not None])
        }
        
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        state['status'] = "error"
        state['reason'] = f"Memory check error: {str(e)}"
    except Exception as e:
        state['status'] = "error"
        state['reason'] = f"Memory check error: {str(e)}"
    
    return state

def conditional_router(state: dict) -> dict:
    """분석된 의도를 기반으로 다음 노드를 결정하는 라우터 노드"""
    intent_hint = state.get('intent_hint', 'general')
    vendor_type = state.get('vendor_type')
    region_keyword = state.get('region_keyword')
    update_type = state.get('update_type')
    user_memo = state.get('user_memo', {})
    user_input = state.get('user_input', '').lower()

    try:
        if update_type:
            state['routing_decision'] = "tool_execution"
            state['tools_to_execute'] = ["user_db_update_tool"]
            state['reason'] = f"User data update required: {update_type}"
        elif intent_hint == "recommend":
            if vendor_type:
                state['routing_decision'] = "tool_execution"
                state['tools_to_execute'] = ["db_query_tool"]
                if region_keyword:
                    state['tools_to_execute'].append("web_search_tool")
                state['reason'] = f"Specific vendor recommendation: {vendor_type}"
            else:
                state['routing_decision'] = "recommendation"
                state['reason'] = "General recommendation request"
        elif intent_hint == "tool":
            state['routing_decision'] = "tool_execution"
            tools_needed = []
            if any(keyword in user_input for keyword in ['계산', '예산', '총액', '비용']):
                tools_needed.append("calculator_tool")
                tools_needed.append("db_query_tool")
            if vendor_type or region_keyword:
                if "db_query_tool" not in tools_needed:
                    tools_needed.append("db_query_tool")
            if any(keyword in user_input for keyword in ['최신', '요즘', '트렌드', '후기']):
                tools_needed.append("web_search_tool")
            if not tools_needed:
                tools_needed.append("db_query_tool")
            state['tools_to_execute'] = tools_needed
            state['reason'] = f"Tool execution needed: {', '.join(tools_needed)}"
        else: # intent_hint == "general"
            state['routing_decision'] = "general_response"
            state['tools_to_execute'] = []
            state['reason'] = "General conversation or FAQ"
            
        profile = user_memo.get('profile', {})
        missing_info = []
        if not profile.get('wedding_date'):
            missing_info.append("wedding_date")
        if not profile.get('total_budget_manwon'):
            missing_info.append("budget")
        if not profile.get('guest_count'):
            missing_info.append("guest_count")
        
        if (len(missing_info) >= 3 and 
            state.get('routing_decision') == "recommendation" and 
            not vendor_type):
            state['routing_decision'] = "general_response"
            state['tools_to_execute'] = []
            state['reason'] = "Insufficient profile info for recommendation, shifting to general advice"
    
    except Exception as e:
        state['status'] = "error"
        state['reason'] = f"Router error: {str(e)}"
        state['routing_decision'] = "error_handler"
    
    return state


def tool_execution_node(state: dict) -> dict:
    """조건부 라우터에서 결정된 도구를 실행하는 노드"""
    touch_processing_timestamp(state)
    tools_to_execute = state.get('tools_to_execute', [])
    tool_results = []
    
    state['tool_execution_log'] = {}
    
    for tool_name in tools_to_execute:
        tool_func = TOOLS.get(tool_name)
        if tool_func:
            try:
                result = tool_func(state)
                tool_results.append({
                    "tool_name": tool_name,
                    "success": True,
                    "output": result
                })
                state['tool_execution_log'][tool_name] = {"status": "ok", "output": result}
            except Exception as e:
                tool_results.append({
                    "tool_name": tool_name,
                    "success": False,
                    "error": str(e)
                })
                state['tool_execution_log'][tool_name] = {"status": "error", "reason": str(e)}
                
    state['tool_results'] = tool_results
    state['status'] = "ok"
    
    return state


def memo_update_node(state: dict) -> dict:
    """도구 실행 결과로 장기 메모(user_memo)를 업데이트하는 노드"""
    touch_processing_timestamp(state)
    user_memo = state.get('user_memo')
    tool_results = state.get('tool_results', [])
    
    if not user_memo:
        state['status'] = "error"
        state['reason'] = "User memo is missing for update"
        return state
        
    try:
        updates_made = _process_memo_updates(tool_results, user_memo)
        
        if updates_made:
            _save_memo(user_memo, state['memo_file_path'])
            state['memo_needs_update'] = False
            state['memo_updates_made'] = updates_made
        
        state['status'] = "ok"
    except Exception as e:
        state['status'] = "error"
        state['reason'] = f"Memo update node error: {str(e)}"
        
    return state

def _process_memo_updates(tool_results: List[Dict], user_memo: Dict) -> List[Dict]:
    """도구 결과에 따라 user_memo에 반영할 업데이트 내역을 생성합니다."""
    updates = []
    
    for result in tool_results:
        if result['tool_name'] == 'db_query_tool' and result['success']:
            updates.extend(_process_db_query_result(result['output'], user_memo))
        elif result['tool_name'] == 'user_db_update_tool' and result['success']:
            updates.extend(_process_user_db_update_result(result['output'], user_memo))
        elif result['tool_name'] == 'web_search_tool' and result['success']:
            updates.extend(_process_web_search_result(result['output'], user_memo))
        elif result['tool_name'] == 'calculator_tool' and result['success']:
            updates.extend(_process_calculator_result(result['output'], user_memo))
    
    return updates

def _process_db_query_result(tool_data: dict, user_memo: dict) -> List[dict]:
    updates = []
    if 'search_query' in tool_data and 'results' in tool_data:
        search_history = user_memo.setdefault('search_history', [])
        history_entry = {
            'query': tool_data['search_query'],
            'results_count': len(tool_data['results']),
            'timestamp': datetime.now().isoformat()
        }
        search_history.append(history_entry)
        updates.append({'category': 'history', 'action': 'add_search_history', 'data': history_entry})
    return updates

def _process_user_db_update_result(tool_data: dict, user_memo: dict) -> List[dict]:
    updates = []
    if tool_data.get('success'):
        updated_profile = tool_data.get('data', {}).get('updated_profile', {})
        profile = user_memo.setdefault('profile', {})
        for key, value in updated_profile.items():
            profile[key] = value
        update_metadata = tool_data.get('data', {}).get('update_metadata', {})
        updates.append({'category': 'profile', 'action': 'update_profile', 'data': update_metadata})
    return updates

def _process_web_search_result(tool_data: dict, user_memo: dict) -> List[dict]:
    updates = []
    if 'insights' in tool_data and tool_data['insights']:
        preferences = user_memo.setdefault('preferences', {})
        insights = preferences.setdefault('external_insights', [])
        for insight in tool_data['insights']:
            insights.append(insight)
            updates.append({'category': 'preferences', 'action': 'add_external_insight', 'data': insight})
    return updates

def _process_calculator_result(tool_data: dict, user_memo: dict) -> List[dict]:
    updates = []
    if 'calculation_type' in tool_data and 'result' in tool_data:
        profile = user_memo.setdefault('profile', {})
        calculations = profile.setdefault('budget_calculations', [])
        calc_entry = {
            'type': tool_data['calculation_type'],
            'result': tool_data['result'],
            'inputs': tool_data.get('inputs', {}),
            'timestamp': datetime.now().isoformat()
        }
        calculations.append(calc_entry)
        if len(calculations) > 20:
            calculations[:] = calculations[-20:]
        updates.append({'category': 'profile', 'action': 'append_calculation', 'data': calc_entry})
    return updates

def _save_memo(user_memo: dict, memo_file_path: str):
    """메모리 파일을 저장합니다."""
    os.makedirs(os.path.dirname(memo_file_path), exist_ok=True)
    with open(memo_file_path, 'w', encoding='utf-8') as f:
        json.dump(user_memo, f, ensure_ascii=False, indent=2)


def response_generation_node(state: dict) -> dict:
    """최종 사용자 응답을 생성하는 노드"""
    touch_processing_timestamp(state)
    try:
        user_input = state.get('user_input', '')
        tool_results = state.get('tool_results', [])
        memo_updates = state.get('memo_updates_made', [])
        user_memo = state.get('user_memo', {})

        context_string = _build_context_string(user_memo, tool_results, memo_updates)

        messages = [
            {"role": "system", "content": _create_response_prompt(context_string)},
            {"role": "user", "content": user_input}
        ]

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )
        final_response = response.choices[0].message.content

        state['final_response'] = _apply_final_quality_checks(final_response, user_memo)
        state['status'] = "ok"

    except Exception as e:
        state['status'] = "error"
        state['reason'] = f"Response generation error: {str(e)}"

    return state

def _build_context_string(user_memo: dict, tool_results: list, memo_updates: list) -> str:
    """컨텍스트 문자열을 빌드합니다."""
    context_parts = []
    profile = user_memo.get('profile', {})
    if profile:
        context_parts.append(f"사용자 프로필: {json.dumps(profile, ensure_ascii=False)}")
    
    if tool_results:
        tool_info = []
        for res in tool_results:
            if res['success']:
                tool_info.append(f"{res['tool_name']} 실행 성공. 결과: {json.dumps(res['output'], ensure_ascii=False)}")
            else:
                tool_info.append(f"{res['tool_name']} 실행 실패. 이유: {res['error']}")
        context_parts.append(f"도구 실행 결과: {'; '.join(tool_info)}")
    
    if memo_updates:
        update_info = [f"{upd['action']} 성공: {json.dumps(upd['data'], ensure_ascii=False)}" for upd in memo_updates]
        context_parts.append(f"메모리 업데이트: {'; '.join(update_info)}")

    return "\\n\\n".join(context_parts)

def _create_response_prompt(context_string: str) -> str:
    """응답 생성 프롬프트를 만듭니다."""
    base_prompt = """You are an AI wedding planner assistant named 'marry-route'. Your goal is to help users plan their wedding by providing helpful, friendly, and accurate information.

- Use the provided context to generate your response. If a user's profile has been updated, confirm the update clearly.
- If a tool was executed, use the tool results to answer the user's question.
- Do not make up information that is not supported by the context or tool results.
- Your tone should be positive, encouraging, and helpful.
- If no specific information is requested (e.g., a greeting), respond appropriately and guide the user toward a wedding planning topic.
- If you cannot fulfill the request due to missing information, politely ask for the necessary details.
- Always provide a conversational, human-like response.

Provided Context:
{context_string}
"""
    return base_prompt.format(context_string=context_string)

def _apply_final_quality_checks(response: str, user_memo: dict) -> str:
    """최종 응답에 개인화 및 품질 개선을 적용합니다."""
    profile = user_memo.get('profile', {})
    user_name = profile.get('name', '고객님')
    
    response = response.replace("사용자", user_name)
    response = re.sub(r'(^|\s)(만원)(\s|$)', r'\1만원\2', response)
    
    return response

def recommendation_node(state: dict) -> dict:
    """추천 엔진 노드 (현재는 tool_execution으로 라우팅하는 패스스루 버전)"""
    state['routing_decision'] = "tool_execution"
    state['tools_to_execute'] = state.get('tools_to_execute', ['db_query_tool'])
    state['recommendation_status'] = "passed_to_tool_execution"
    state['status'] = "ok"
    return state

def error_handler_node(state: dict) -> dict:
    """오류를 처리하고 복구하는 노드"""
    touch_processing_timestamp(state)
    error_reason = state.get('reason', '알 수 없는 오류')
    
    # 예시: 특정 오류에 대한 맞춤형 응답
    if "Memory check error" in error_reason:
        state['final_response'] = "장기 메모리 정보를 불러오는 데 문제가 발생했습니다. 잠시 후 다시 시도해 주세요."
    elif "Parsing node error" in error_reason:
        state['final_response'] = "요청 내용을 분석하는 데 문제가 발생했습니다. 좀 더 명확하게 말씀해주시면 좋을 것 같아요."
    elif "Tool execution node error" in error_reason:
        state['final_response'] = "요청을 처리하는 데 필요한 도구 실행 중 문제가 발생했습니다. 불편을 드려 죄송합니다. 잠시 후 다시 시도해 주세요."
    else:
        state['final_response'] = "시스템에 예상치 못한 문제가 발생했습니다. 잠시 후 다시 시도해 주시거나, 브라우저를 새로고침한 후 다시 접속해 주세요."
    
    state['status'] = "handled_error"
    return state