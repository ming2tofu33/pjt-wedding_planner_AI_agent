# 🤖 LangGraph 웨딩 플래너 - ChatOpenAI 버전

**ChatOpenAI를 최대한 활용**하는 지능적인 결혼 준비 AI 도우미입니다.  
LangGraph + LangChain 상태 머신을 바탕으로, 예산·일정·체크리스트·업체 추천을 자동화합니다.

---

## 🚀 주요 특징

### LLM 최대 활용
```python
# 기본 LLM 설정
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

class ParsingResult(BaseModel):
    intent: str
    slots: dict

llm = ChatOpenAI(model='gpt-4o', temperature=0)

# 구조화된 출력 활용
structured_llm = llm.with_structured_output(ParsingResult)
result = structured_llm.invoke([
    {"role": "user", "content": "강남에서 예산 5천으로 예식장 추천"}
])
```

### 지능적 노드 시스템
- **parsing_node**: LLM으로 사용자 의도/슬롯 정확 분석
- **conditional_router**: 상태·컨텍스트 기반 라우팅 결정
- **tool_execution_node**: LLM이 도구 매개변수 생성 → 실행
- **response_generation_node**: 결과를 맥락적으로 요약/후속질문 생성

### 스마트 도구들
- **web_search_tool**: LLM 검색 쿼리 최적화 & 최신성 반영
- **calculator_tool**: 한국어 수식/퍼센트 해석
- **db_query_tool**: 자연어 → SQL 자동 생성 및 결과 해석
- **user_db_update_tool**: 대화 로그 기반 사용자 프로필/선호 업데이트 검증

---

## 📦 설치 및 설정

### 1) 의존성 설치
```bash
pip install -r requirements.txt
```

### 2) 환경 변수 설정
프로젝트 루트에 `.env` 파일을 생성하고 값 기입:
```env
# OpenAI API 설정
OPENAI_API_KEY=your_openai_api_key_here
LLM_MODEL=gpt-4o

# 데이터베이스 설정 (옵션)
DATABASE_URL=sqlite:///wedding_planner.db

# 로그 레벨 (옵션: DEBUG/INFO/WARN/ERROR)
LOG_LEVEL=INFO
```

### 3) 데이터베이스 초기화 (필요시)
```python
from db import initialize_db
initialize_db()
```

---

## 🎯 실행 방법

### 대화형 챗봇 모드
```bash
python main.py
# 프롬프트에서: 1 (interactive)
```

### 테스트 시나리오 실행
```bash
python main.py
# 프롬프트에서: 2 (test)
```

### 단일 쿼리 테스트
```bash
python main.py
# 프롬프트에서: 3 (single)
```

---

## 💬 사용 예시

### 웨딩홀 추천
```
👤 You: 강남에서 예산 5000만원으로 웨딩홀 추천해주세요

🤖 AI: 강남 지역에서 예산 5000만원에 맞는 웨딩홀을 찾아드렸어요! 

추천 웨딩홀:
1. 강남 그랜드 웨딩홀 - 4800만원, 200명 수용
2. 압구정 로얄홀 - 4500만원, 180명 수용
3. 청담 프리미엄홀 - 4900만원, 220명 수용

각 홀의 특징과 장단점도 자세히 설명드릴까요?
```

### 예산 계산
```
👤 You: 총 예산 8000만원에서 웨딩홀 60%, 스튜디오 15% 쓰면 각각 얼마죠?

🤖 AI: 예산 계산 결과입니다:

💰 총 예산: 8,000만원
- 웨딩홀 (60%): 4,800만원
- 스튜디오 (15%): 1,200만원
- 남은 예산 (25%): 2,000만원

남은 2,000만원으로 드레스, 메이크업, 혼수 등을 준비하시면 됩니다.
```

### 프로필 업데이트
```
👤 You: 하객수를 150명으로 변경해주세요

🤖 AI: ✅ 하객수가 150명으로 업데이트되었습니다!

이제 150명 기준으로 웨딩홀과 예산을 다시 계산해드릴까요?
예상 식비: 150명 × 5만원 = 750만원
```

---

## 🔧 기술 스택

### Core Framework
- **LangGraph**: 그래프 기반 상태 관리
- **LangChain**: LLM 체인/도구 통합
- **ChatOpenAI**: GPT-4o 직접 활용

### LLM 활용 방식
```python
# 기본 호출
response = llm.invoke([{"role": "user", "content": "예식장 예약 상태 보여줘"}])

# 구조화된 출력
from pydantic import BaseModel
class MyDataClass(BaseModel):
    field_a: str
    field_b: int

structured_llm = llm.with_structured_output(MyDataClass)
result = structured_llm.invoke([
    {"role": "system", "content": "역할: 웨딩 플래너"},
    {"role": "user", "content": "예산 배분 6:2:2로 계산"}
])

# 용도별 LLM
parsing_llm = ChatOpenAI(model='gpt-4o-mini', temperature=0)  # 정확성 우선
creative_llm = ChatOpenAI(model='gpt-4o', temperature=0.3)    # 창의성 허용
```

---

## 📁 파일 구조
> 최소 실행 예시 구조 (예시는 상황에 맞게 조정하세요)

```
wedding-planner/
├── main.py              # 메인 실행 (CLI 메뉴: interactive/test/single)
├── nodes.py             # LLM 기반 노드 함수들 (parsing/router/tool/response)
├── tools.py             # web/db/calculator 등 도구 정의
├── state.py             # 그래프 상태/메모리 관리
├── db.py                # DB 연결 및 ORM/쿼리
├── requirements.txt     # 의존성
├── .env                 # 환경 변수 (개인용)
└── README.md            # 이 파일
```
- (선택) `/src/MarryRouteReactApp.tsx` 웹 UI 프로토타입 포함 가능

---

## 🎨 주요 개선사항 (15-code_interpreter 방식 → ChatOpenAI 전환)

### Before (OpenAI Client 직접 사용)
```python
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": prompt}]
)
result = json.loads(response.choices[0].message.content)
```

### After (ChatOpenAI + 구조화된 출력)
```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model='gpt-4o', temperature=0)
structured_llm = llm.with_structured_output(ParsingResult)
result = structured_llm.invoke([
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": user_input}
])
```

- ✅ 응답 파싱 안정성 향상 (Pydantic 스키마로 바로 검증)
- ✅ 노드 간 I/O 규격화 → 유지보수/테스트 용이
- ✅ 프롬프트 관리 단순화 (역할/컨텍스트 명확화)

---

## 🔍 디버깅 & 모니터링

### 상태 확인 (샘플)
```
👤 You: 상태확인

🔍 현재 시스템 상태:
  - LLM 모델: gpt-4o
  - ChatOpenAI 사용: ✅
  - 메모리: 활성화
```
- 노드별 로깅: 각 노드 진입/출력/에러를 로그로 기록
- 트레이싱: LangSmith/LangChain 텔레메트리(옵션)로 호출 추적

### 트러블슈팅 팁
- .env 누락 → `OPENAI_API_KEY` 확인
- DB 초기화 누락 → `initialize_db()` 또는 마이그레이션 스크립트 실행
- 구조화 출력 오류 → Pydantic 스키마/필드명 재확인

---

## 🤝 기여 & 개선 로드맵
1) **더 많은 구조화된 출력** 적용으로 파싱 안정화  
2) **도구별 전문 LLM** 세분화(Parsing/Creative/Tool-Reasoner)  
3) **컨텍스트/메모리 관리** 고도화 (프로필·예산·일정 동기화)  
4) **멀티모달**: 이미지 무드보드/드레스 매칭(차차 추가)  

---

## 📞 지원
이메일: contact@marryroute.com (예정)
개발자: 배&민 공동 개발 🛵 

이슈/피드백은 PR 또는 Issue로 남겨주세요.  
서비스화에 맞춰 웹 UI(React)·알림(캘린더/메신저)·실시간 지출 알림을 순차 탑재 예정입니다.


## 📄 라이선스

이 프로젝트는 현재 개발 중이며, 라이선스는 추후 결정될 예정입니다.


**💡 핵심**: _ChatOpenAI를 직접 사용하여 LLM의 능력을 최대한 끌어내는 것_ — 이것이 본 프로젝트의 목표입니다!

*"결혼 준비의 모든 스트레스를 덜어내고, 두 사람만의 특별한 순간에 집중할 수 있도록 돕겠습니다."* - 마리 🤖💕
