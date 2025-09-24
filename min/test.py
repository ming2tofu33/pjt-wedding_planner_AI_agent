#!/usr/bin/env python3
"""
AI 웨딩 플래너 챗봇 실행 스크립트 - 개선된 버전
"""

from graph import app  # 여기서 app은 컴파일된 그래프
from state import State
import json

def test_chatbot():
    """챗봇 테스트 함수"""
    
    # 테스트할 사용자 입력
    user_input = "안녕 마리야 나는 배야. 결혼 자금 5천만원으로 결혼 준비해보려고"
    
    # 초기 State 설정
    initial_state = {
        'user_input': user_input,
        'user_id': 'test_user_001',
        # 다른 필요한 초기값들
        'memo': {},
        'tools_to_execute': [],
        'tool_results': {},
        'response': '',
        'status': '',
        'reason': '',
        'processing_timestamp': None
    }
    
    print("🚀 챗봇 실행 시작...")
    print(f"📝 입력: {user_input}")
    print("-" * 50)
    
    try:
        # 그래프 실행
        result = app.invoke(initial_state)
        
        print("✅ 실행 완료!")
        print(f"📤 최종 응답: {result.get('response', 'No response')}")
        print(f"🎯 의도 분류: {result.get('intent_hint', 'Unknown')}")
        print(f"🔄 라우팅 결정: {result.get('routing_decision', 'Unknown')}")
        print(f"📊 상태: {result.get('status', 'Unknown')}")
        
        # 세부 정보 출력
        if result.get('vendor_type'):
            print(f"🏪 업체 유형: {result.get('vendor_type')}")
        if result.get('region_keyword'):
            print(f"📍 지역: {result.get('region_keyword')}")
        if result.get('total_budget_manwon'):
            print(f"💰 예산: {result.get('total_budget_manwon')}만원")
            
        print("-" * 50)
        print("🔍 전체 결과:")
        # JSON 직렬화 가능한 항목만 출력
        safe_result = {}
        for key, value in result.items():
            try:
                json.dumps(value)  # 테스트
                safe_result[key] = value
            except (TypeError, ValueError):
                safe_result[key] = f"<{type(value).__name__} object>"
        
        print(json.dumps(safe_result, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"❌ 실행 중 오류 발생: {e}")
        import traceback
        print(traceback.format_exc())

def interactive_mode():
    """개선된 대화형 모드"""
    print("🎉 AI 웨딩 플래너 '마리'와 대화해보세요!")
    print("종료하려면 'quit' 또는 'exit'를 입력하세요.")
    print("-" * 50)
    
    # 대화 히스토리 저장
    conversation_history = []
    
    while True:
        user_input = input("👤 You: ").strip()
        
        if user_input.lower() in ['quit', 'exit', '종료', '나가기']:
            print("👋 안녕히 가세요!")
            break
            
        if not user_input:
            print("❌ 메시지를 입력해주세요.")
            continue
        
        # 대화 히스토리에 추가
        conversation_history.append({"role": "user", "content": user_input})
        
        # State 설정 - 더 완전한 초기화
        state = {
            'user_input': user_input,
            'user_id': 'interactive_user',
            'memo': {},
            'tools_to_execute': [],
            'tool_results': {},
            'response': '',
            'status': '',
            'reason': '',
            'processing_timestamp': None,
            'messages': conversation_history.copy(),  # 대화 히스토리 추가
            'rows': [],
            'suggestions': [],
            'quick_replies': [],
            'intent_hint': '',
            'routing_decision': '',
            'vendor_type': None,
            'region_keyword': None,
            'total_budget_manwon': None
        }
        
        print(f"\n🔄 처리 중...")
        
        try:
            # 그래프 실행
            result = app.invoke(state)
            
            # 응답 추출 및 출력 (여러 가능한 키 확인)
            response = (result.get('response', '') or 
                       result.get('response_content', '') or 
                       '').strip()
            
            status = result.get('status', 'unknown')
            intent = result.get('intent_hint', 'unknown')
            routing = result.get('routing_decision', 'unknown')
            
            # 디버깅 정보 출력
            print(f"🔍 상태: {status} | 의도: {intent} | 라우팅: {routing}")
            print(f"🔍 응답 키 확인: response='{result.get('response', 'None')}', response_content='{result.get('response_content', 'None')}'")
            
            # 응답 처리
            if response:
                print(f"🤖 마리: {response}")
                conversation_history.append({"role": "assistant", "content": response})
            else:
                # 응답이 없는 경우 기본 응답 제공
                if intent == 'general':
                    default_responses = {
                        '안녕': '안녕하세요! 저는 AI 웨딩 플래너 마리예요. 결혼 준비에 대해 궁금한 것이 있으시면 언제든 물어보세요! 💍',
                        '이름': '저는 마리예요! AI 웨딩 플래너로 여러분의 행복한 결혼식 준비를 도와드리고 있어요. ✨',
                        '고마워': '천만에요! 더 궁금한 것이 있으시면 언제든 말씀해주세요. 😊',
                        '감사': '도움이 되었다니 기뻐요! 결혼 준비에 관한 것이라면 무엇이든 물어보세요! 💕'
                    }
                    
                    # 키워드 매칭으로 기본 응답 찾기
                    fallback_response = "안녕하세요! 저는 AI 웨딩 플래너 마리예요. 결혼 준비에 대해 도움이 필요하시면 말씀해주세요! 💍"
                    
                    for keyword, response_text in default_responses.items():
                        if keyword in user_input:
                            fallback_response = response_text
                            break
                    
                    print(f"🤖 마리: {fallback_response}")
                    conversation_history.append({"role": "assistant", "content": fallback_response})
                
                elif intent == 'wedding':
                    fallback_response = "결혼 준비에 대해 문의해주셨네요! 구체적으로 어떤 도움이 필요하신지 알려주시면 더 자세한 답변을 드릴 수 있어요. 💒"
                    print(f"🤖 마리: {fallback_response}")
                    conversation_history.append({"role": "assistant", "content": fallback_response})
                
                else:
                    print(f"🤖 마리: 죄송해요, 응답을 생성할 수 없었어요. 다시 한 번 말씀해주시겠어요?")
            
            # 에러 상태 처리
            if status == 'error':
                error_reason = result.get('reason', 'Unknown error')
                print(f"⚠️  처리 중 오류: {error_reason}")
            
            # 추가 정보 출력 (웨딩 관련인 경우)
            if intent == 'wedding':
                if result.get('vendor_type'):
                    print(f"🏪 감지된 업체 유형: {result.get('vendor_type')}")
                if result.get('region_keyword'):
                    print(f"📍 감지된 지역: {result.get('region_keyword')}")
                if result.get('total_budget_manwon'):
                    print(f"💰 감지된 예산: {result.get('total_budget_manwon')}만원")
                
        except Exception as e:
            print(f"❌ 처리 중 오류가 발생했어요: {e}")
            print(f"🔧 다시 시도해보시거나, 다른 방식으로 질문해주세요.")
            
            # 디버깅 정보 (개발용)
            import traceback
            print(f"🐛 디버깅 정보:\n{traceback.format_exc()}")
        
        print("-" * 30)

def simple_test():
    """간단한 테스트"""
    test_inputs = [
        "안녕하세요",
        "이름이 뭐예요?", 
        "강남 웨딩홀 추천해주세요",
        "결혼 준비 도와주세요"
    ]
    
    print("🧪 간단한 테스트 실행...")
    
    for i, user_input in enumerate(test_inputs, 1):
        print(f"\n{'='*50}")
        print(f"테스트 {i}: {user_input}")
        print('='*50)
        
        state = {
            'user_input': user_input,
            'user_id': f'test_user_{i}',
            'memo': {},
            'tools_to_execute': [],
            'tool_results': {},
            'response': '',
            'status': '',
            'reason': '',
            'processing_timestamp': None,
            'messages': [],
            'rows': [],
            'suggestions': [],
            'quick_replies': []
        }
        
        try:
            result = app.invoke(state)
            
            # 응답 키 확인 (여러 가능성)
            response = (result.get('response', '') or 
                       result.get('response_content', '') or 
                       '').strip()
            
            print(f"✅ 결과:")
            print(f"   응답: {response or 'No response'}")
            print(f"   의도: {result.get('intent_hint', 'Unknown')}")
            print(f"   라우팅: {result.get('routing_decision', 'Unknown')}")
            print(f"   상태: {result.get('status', 'Unknown')}")
            
            # 디버깅: 실제로 어떤 키들이 있는지 확인
            response_keys = [k for k in result.keys() if 'response' in k.lower()]
            if response_keys:
                print(f"   🔍 응답 관련 키들: {response_keys}")
                for key in response_keys:
                    print(f"     {key}: '{str(result[key])[:50]}...'")
            
        except Exception as e:
            print(f"❌ 오류: {e}")

if __name__ == "__main__":
    print("🎭 AI 웨딩 플래너 실행 모드를 선택하세요:")
    print("1. 테스트 모드 (고정된 메시지 테스트)")
    print("2. 대화형 모드 (실시간 대화)")
    print("3. 간단한 테스트 (여러 입력 자동 테스트)")
    
    choice = input("선택 (1, 2, 또는 3): ").strip()
    
    if choice == "1":
        test_chatbot()
    elif choice == "2":
        interactive_mode()
    elif choice == "3":
        simple_test()
    else:
        print("❌ 잘못된 선택입니다. 1, 2, 또는 3을 입력해주세요.")