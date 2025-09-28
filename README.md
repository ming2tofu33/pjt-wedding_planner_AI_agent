# 💍 MarryRoute - AI 웨딩 플래너 README

![MarryRoute Banner](https://lh3.googleusercontent.com/gg/AAHar4dhhQNNhLUd6mIu2Xxqf1snk6Unq9Uz2gviv2VNvc72u7mLKSfpRwAGSlYEqfJvYl_sn5zMOBSBz6LItRE6BMXbXJQWvTHvAql1GRkIDjOYyOvNpwSYOJW_nROvjuHdN85GWGUcjB7XGc3tfP-dDAfV5E-tYWDEZcQm1JTgg5cC3lI0LZcLZleeUY6VLmNprhTTmjUVwX4CiIV4K_SvXyTvmGyy_wNo-Atobp3IkM-pfB_WUScZ0YTrXbhpumVkjbrpAz5G-8jgyKE0H-94tNYhAQgCbgTDBnPhkXnVPcy7VFOAXaUHNR4gWBtJiMy6qEne4bdW5s-1EnXSOY9Hf0rl=s1024)

- 배포 URL : (배포 후 추가 예정)
- Demo URL : `streamlit run app.py`

<br>

## 🚀 프로젝트 소개

- **MarryRoute**는 AI 기술을 활용한 개인 맞춤형 웨딩 플래너 서비스입니다.
- 웨딩 준비의 모든 과정을 AI 어시스턴트 '마리'와 함께 체계적으로 관리할 수 있습니다.
- 개인 정보와 선호도를 학습하여 최적화된 웨딩 업체 추천과 일정 관리를 제공합니다.
- 실시간 웹 검색과 데이터베이스 연동으로 최신 정보와 맞춤형 추천을 제공합니다.

### 📚 프로젝트 상세 문서
<div align="center">
MarryRoute의 AI Agent 설계 과정과 LangGraph 아키텍처가 궁금하시다면?

**[📖 Notion 프로젝트 문서 바로가기](https://maroon-anaconda-f0c.notion.site/AI-Agent-Project-26bee8fffe158048970cee71fe6b9244)**

*프로젝트의 기술적 세부사항, 개발 과정, 아키텍처 설계 등 상세한 내용을 확인하실 수 있습니다.*

</div>

<br>

## 👥 팀원 구성

<div align="center">

| **배성우** | **김도민** |
| :------: |  :------: |
| [<img src="https://i.pinimg.com/736x/f1/ec/c8/f1ecc86b47a6e5789119afbbac06a4d4.jpg" height=150 width=150> <br/> @baesisi3648](https://github.com/baesisi3648) | [<img src="https://i.pinimg.com/736x/89/3b/7d/893b7da680e917dc234dcbf13682c9d9.jpg" height=150 width=150> <br/> @ming2tofu33](https://github.com/ming2tofu33) |

</div>

<br>

## 📅개발 기간 및 작업 관리

### 개발 기간

- 전체 개발 기간 : 2025/09/15 - 2025/09/29

<br>

## ✅ 주요 기능

### 🤖 AI 웨딩 플래너 '마리'
- **대화형 인터페이스**: 자연어로 웨딩 준비 상담 가능
- **개인화 서비스**: 예산, 취향, 지역 등 개인 정보 기반 맞춤 추천
- **실시간 학습**: 대화를 통해 사용자 선호도를 지속적으로 학습

### 🏢 스마트 업체 추천
- **데이터베이스 연동**: 웨딩홀, 스튜디오, 드레스, 메이크업 업체 정보
- **지역별 검색**: 지하철역, 지역명 기반 업체 검색
- **예산 맞춤**: 설정한 예산 범위 내 업체 필터링
- **실시간 정보**: 웹 검색을 통한 최신 업체 정보 및 후기

### 📅 일정 관리 시스템
- **통합 스케줄링**: 웨딩 준비 일정을 체계적으로 관리
- **카테고리별 분류**: 웨딩홀, 드레스, 사진촬영 등 카테고리별 일정 구분
- **진행 상황 추적**: 예정, 진행중, 완료, 취소 등 상태별 관리
- **데이터베이스 동기화**: PostgreSQL과 연동하여 안전한 데이터 저장

### 💰 예산 관리
- **카테고리별 예산**: 웨딩홀, 드레스, 스튜디오 등 항목별 예산 설정
- **실시간 계산**: AI 계산기를 통한 예산 분배 및 비용 계산
- **시각화**: 도넛 차트를 통한 예산 사용 현황 시각화

### 🔍 통합 검색
- **다중 검색**: 내부 데이터베이스 + 웹 검색 동시 지원
- **맥락 인식**: 이전 대화 내용을 고려한 검색 결과 제공
- **업체 상세 정보**: 가격, 위치, 연락처, 특징 등 종합 정보

<br>

## 🔧 기술 스택

### Backend
- **Python 3.8+**: 메인 개발 언어
- **LangGraph**: 대화 플로우 및 AI 워크플로우 관리
- **OpenAI GPT-4**: 자연어 처리 및 대화 생성
- **PostgreSQL**: 업체 정보 및 사용자 일정 데이터 저장
- **psycopg2**: ORM 및 데이터베이스 연동
- **Tavily API**: 실시간 웹 검색

### Frontend
- **Streamlit**: 웹 인터페이스 및 사용자 경험
- **CSS Styling**: 커스텀 디자인 시스템
- **Interactive Components**: 차트, 폼, 버튼 등 인터랙티브 요소

### AI & ML
- **LangChain**: LLM 체인 및 도구 통합
- **Conversational AI**: 컨텍스트 인식 대화 시스템
- **Memory Management**: 사용자별 개인화 정보 저장

### DevOps & Tools
- **Environment Management**: .env 파일을 통한 환경 변수 관리
- **Git**: 버전 관리
- **Requirements Management**: pip를 통한 의존성 관리

<br>

## 📁 프로젝트 구조

```
├── README.md
├── .gitignore
├── .env
├── requirements.txt
├── bae                     # 개인 작업 폴더
├── min                     # 개인 작업 폴더
│
├── docs/
│   └── images/             # demo images
│
└── src/
    ├── README.md
    ├── requirements.txt
    ├── .env                 # 환경 변수 (API 키, DB 연결 정보)
    ├── .gitignore
    ├── langgraph.json       # LangGraph 설정
    │
    ├── app.py               # Streamlit 메인 애플리케이션
    ├── graph.py             # LangGraph 워크플로우 정의
    ├── state.py             # 대화 상태 관리
    ├── nodes.py             # 대화 플로우 노드 구현
    ├── routers.py           # 라우팅 로직
    ├── tools.py             # AI 도구 (DB 쿼리, 웹 검색, 계산기 등)
    ├── db.py                # 데이터베이스 연결 및 관리
    │
    ├── memories/            # 사용자별 메모리 저장
    │   └── user_id.json
    ├── streamlit/           # Streamlit 관련 파일
    ├── __pycache__/         # Python 캐시
    └── venv/                # 가상환경

```

<br>

## 📦 설치 및 설정

### 1. 환경 설정

```bash
# 레포지토리 클론
git clone [repository-url]
cd MarryRoute

# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

### 2. 환경 변수 설정

`.env` 파일을 생성하고 다음 변수들을 설정하세요:

```env
# OpenAI API
OPENAI_API_KEY=your_openai_api_key

# Tavily (웹 검색) API
TAVILY_API_KEY=your_tavily_api_key

# PostgreSQL 데이터베이스
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=wedding_db
POSTGRES_USER=your_username
POSTGRES_PASSWORD=your_password

# 기본 사용자 ID
DEFAULT_USER_ID=mvp-test-user
```

### 3. 데이터베이스 설정

PostgreSQL 데이터베이스에 다음 테이블들이 필요합니다:

- `wedding_hall`: 웨딩홀 정보
- `studio`: 스튜디오 정보  
- `wedding_dress`: 드레스 업체 정보
- `makeup`: 메이크업 업체 정보
- `user_schedule`: 사용자 일정 관리

### 4. 애플리케이션 실행

```bash
streamlit run app.py
```

브라우저에서 `http://localhost:8501`로 접속하여 서비스를 이용할 수 있습니다.

<br>

## ⚙️ 주요 컴포넌트

### AI 대화 플로우 (LangGraph)
1. **parsing_node**: 사용자 의도 파싱 및 필요 도구 판단
2. **memo_check_node**: 사용자 메모리 로드 및 관리
3. **tool_execution_node**: 필요한 도구들 실행
4. **memo_update_node**: 사용자 정보 업데이트
5. **response_generation_node**: 최종 응답 생성
6. **general_response_node**: 일반 대화 응답

### 도구 시스템 (Tools)
- **db_query_tool**: 웨딩 업체 데이터베이스 검색
- **web_search_tool**: Tavily API를 통한 실시간 웹 검색
- **calculator_tool**: 웨딩 예산 및 비용 계산
- **memo_update_tool**: 사용자 정보 저장
- **user_db_update_tool**: 일정 관리 (CRUD)

### 사용자 인터페이스
- **AI 채팅**: 마리와의 대화형 상담
- **홈 대시보드**: D-day, 예산 현황, 진행률, 추천 업체
- **업체 검색**: 카테고리별 필터링 및 상세 정보
- **일정 관리**: 타임라인 뷰 및 일정 추가/수정
- **예산 관리**: 카테고리별 예산 배분 및 사용 현황

<br>

## 사용 예시

### 1. 기본 정보 입력
```
👤 사용자: "내 이름은 김민아이고, 예산은 5000만원 정도예요"
🤖 마리:  "안녕하세요 민아님! 5000만원 예산으로 멋진 웨딩을 준비해보세요..."
```

### 2. 업체 추천 요청
```
👤사용자: "강남 지역 웨딩홀 3곳 추천해주세요"
🤖마리: "강남 지역의 예산에 맞는 웨딩홀을 찾아드릴게요..."
[DB 검색 + 웹 검색 결과 제공]
```

### 3. 일정 관리
```
👤사용자: "내일 오후 2시에 드레스샵 상담 일정 잡아주세요"
🤖마리: "드레스샵 상담 일정이 추가되었습니다..."
```

### 4. Streamlit DEMO

<details>
<summary>🔍 더 많은 사용 예시 보기</summary>

**추가 예시 1: 개인정보 입력**
| 추가 예시 1 |
|----------|
|![개인정보 입력](https://github.com/ming2tofu33/pjt-wedding_planner_AI_agent/blob/main/docs/images/%EA%B0%9C%EC%9D%B8%EC%A0%95%EB%B3%B4%20%EC%9E%85%EB%A0%A5.gif?raw=true)|


**추가 예시 2: 스튜디오 추천**  
| 추가 예시 2 |
|----------|
|![스튜디오 추천](https://github.com/ming2tofu33/pjt-wedding_planner_AI_agent/blob/main/docs/images/%EA%B0%9C%EC%9D%B8%EC%A0%95%EB%B3%B4%20%EC%9E%85%EB%A0%A5.gif?raw=true)|

**추가 예시 3: 스튜디오 웹서치**
| 추가 예시 3 |
|----------|
|![스튜디오 웹서치](https://github.com/ming2tofu33/pjt-wedding_planner_AI_agent/blob/main/docs/images/%EA%B0%9C%EC%9D%B8%EC%A0%95%EB%B3%B4%20%EC%9E%85%EB%A0%A5.gif?raw=true)|

**추가 예시 4: 드레스 추천**
| 추가 예시 4 |
|----------|
|![드레스 추천](https://github.com/ming2tofu33/pjt-wedding_planner_AI_agent/blob/main/docs/images/%EA%B0%9C%EC%9D%B8%EC%A0%95%EB%B3%B4%20%EC%9E%85%EB%A0%A5.gif?raw=true)|

**추가 예시 5: 인스타그램 검색**
| 추가 예시 5 |
|----------|
|![인스타그램 검색](https://github.com/ming2tofu33/pjt-wedding_planner_AI_agent/blob/main/docs/mages/%EA%B0%9C%EC%9D%B8%EC%A0%95%EB%B3%B4%20%EC%9E%85%EB%A0%A5.gif?raw=true)|

**추가 예시 6: 웨딩홀 추천**
| 추가 예시 6 |
|----------|
|![웨딩홀 추천](https://github.com/ming2tofu33/pjt-wedding_planner_AI_agent/blob/main/docs/images/%EA%B0%9C%EC%9D%B8%EC%A0%95%EB%B3%B4%20%EC%9E%85%EB%A0%A5.gif?raw=true)|

**추가 예시 7: 업체 리뷰**
| 추가 예시 7 |
|----------|
|![업체 리뷰](https://github.com/ming2tofu33/pjt-wedding_planner_AI_agent/blob/main/docs/images/%EA%B0%9C%EC%9D%B8%EC%A0%95%EB%B3%B4%20%EC%9E%85%EB%A0%A5.gif?raw=true)|

</details>

<br>

## 💡 개발 포인트

### 🎯 핵심 기능
- **컨텍스트 인식**: 이전 대화 내용을 기억하여 맞춤형 응답 제공
- **멀티모달 검색**: 내부 DB와 외부 웹 검색 결과를 통합하여 제공
- **실시간 학습**: 사용자와의 대화를 통해 선호도를 지속적으로 학습
- **상태 관리**: LangGraph를 활용한 복잡한 대화 플로우 관리

### 🔧 기술적 도전
- **비동기 처리**: 다중 도구 실행 시 성능 최적화
- **메모리 관리**: 사용자별 개인화 정보의 효율적 저장 및 조회
- **오류 처리**: 외부 API 연동 시 안정성 확보
- **사용자 경험**: Streamlit을 활용한 직관적인 UI/UX 구현

<br>

## 🌱 향후 개선 계획

### 📈 기능 확장
- [ ] 실제 업체와의 예약 연동 시스템
- [ ] 웨딩 체크리스트 자동 생성
- [ ] 예산 알림 및 추천 시스템
- [ ] 모바일 반응형 디자인
- [ ] 다중 사용자 지원 (커플 공동 계정)

### 🚀 성능 최적화
- [ ] 데이터베이스 쿼리 최적화
- [ ] 캐싱 시스템 도입
- [ ] API 응답 속도 개선
- [ ] 메모리 사용량 최적화

### 🔐 보안 강화
- [ ] 사용자 인증 시스템
- [ ] 개인정보 암호화
- [ ] API 키 보안 강화
- [ ] 데이터 백업 시스템

<br>

## 📄 라이선스

이 프로젝트는 [MIT License](LICENSE)를 따릅니다.

<br>

## 🤝 기여하기

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

<br>

## 연락처

프로젝트 관련 문의: [contact@marryroute.com]

프로젝트 링크: [https://github.com/ming2tofu33/pjt-wedding_planner_AI_agent]

---

💍 **"결혼 준비의 모든 스트레스를 덜어내고, 두 사람만의 특별한 순간에 집중할 수 있도록 돕겠습니다."**  - 마리 🤖💕 💍