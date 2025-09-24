import os
import asyncio
from langchain_core.messages import HumanMessage
from graph import app
from state import State
from dotenv import load_dotenv

load_dotenv()

async def run_chat():
    """웨딩 챗봇과 대화하기"""
    
    print("🎉 웨딩 챗봇에 오신 것을 환영합니다!")
    print("웨딩 관련 질문이나 일반적인 대화를 나눠보세요.")
    print("종료하려면 'quit' 또는 'exit'를 입력하세요.\n")
    
    # 초기 상태 설정
    current_state = State(
        messages=[],
        memo={
            "budget": "",
            "preferred_location": "",
            "wedding_date": "",
            "style": "",
            "confirmed_vendors": {},
            "notes": []
        },
        intent="",
        tools_needed=[],
        tool_results={}
    )
    
    while True:
        try:
            # 사용자 입력 받기
            user_input = input("\n👤 사용자: ").strip()
            
            if user_input.lower() in ['quit', 'exit', '종료', '끝']:
                print("👋 웨딩 챗봇을 이용해주셔서 감사합니다!")
                break
            
            if not user_input:
                continue
            
            # 사용자 메시지를 상태에 추가
            current_state.messages.append(HumanMessage(content=user_input))
            
            print("🤖 처리 중...")
            
            # 그래프 실행
            result = await app.ainvoke(current_state)
            
            # AI 응답 출력
            if result.messages and len(result.messages) > 0:
                last_message = result.messages[-1]
                if hasattr(last_message, 'content'):
                    print(f"🤖 챗봇: {last_message.content}")
                else:
                    print("🤖 챗봇: 응답을 생성하는 중 문제가 발생했습니다.")
            
            # 상태 업데이트 (메모리 유지)
            current_state = result
            
            # 디버깅 정보 (선택적)
            if os.getenv('DEBUG', 'false').lower() == 'true':
                print(f"\n[DEBUG] Intent: {result.intent}")
                print(f"[DEBUG] Tools needed: {result.tools_needed}")
                print(f"[DEBUG] Memo: {result.memo}")
                
        except KeyboardInterrupt:
            print("\n👋 웨딩 챗봇을 이용해주셔서 감사합니다!")
            break
        except Exception as e:
            print(f"❌ 오류가 발생했습니다: {e}")
            print("다시 시도해주세요.")

def run_single_query(query: str):
    """단일 질문 테스트용 함수"""
    
    initial_state = State(
        messages=[HumanMessage(content=query)],
        memo={
            "budget": "",
            "preferred_location": "",
            "wedding_date": "",
            "style": "",
            "confirmed_vendors": {},
            "notes": []
        },
        intent="",
        tools_needed=[],
        tool_results={}
    )
    
    try:
        result = app.invoke(initial_state)
        if result.messages and len(result.messages) > 0:
            last_message = result.messages[-1]
            print(f"질문: {query}")
            print(f"답변: {last_message.content}")
            print(f"의도: {result.intent}")
            print(f"사용된 툴: {result.tools_needed}")
        return result
    except Exception as e:
        print(f"오류: {e}")
        return None

async def test_scenarios():
    """다양한 시나리오 테스트"""
    
    test_cases = [
        "안녕하세요!",
        "웨딩홀 추천해주세요",
        "예산 200만원으로 드레스 찾아줘",
        "강남 근처 스튜디오 알아봐줘",
        "하객 100명 예산 계산해줘",
        "오늘 날씨 어때요?"
    ]
    
    print("🧪 테스트 시나리오 실행 중...\n")
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"[테스트 {i}] {test_case}")
        result = run_single_query(test_case)
        print("-" * 50)
        await asyncio.sleep(1)  # API 호출 간격

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "test":
            # 테스트 모드
            asyncio.run(test_scenarios())
        elif sys.argv[1] == "single":
            # 단일 쿼리 모드
            if len(sys.argv) > 2:
                query = " ".join(sys.argv[2:])
                run_single_query(query)
            else:
                print("사용법: python main.py single '질문 내용'")
        else:
            print("사용법: python main.py [test|single]")
    else:
        # 대화형 모드 (기본)
        asyncio.run(run_chat())