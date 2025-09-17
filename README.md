# 💍 MarryRoute - AI 웨딩 플래너 에이전트

> **🚧 현재 개발 진행 중입니다 (Work in Progress)**

AI 기반 웨딩 플래너 에이전트로, 예비 부부들이 복잡한 결혼 준비 과정을 쉽고 효율적으로 계획할 수 있도록 돕는 지능적인 솔루션입니다.

## 🎯 프로젝트 비전

**"결혼까지 가장 짧은 루트"**

- 🤖 **AI 웨딩 상담**: 자연어 대화를 통한 맞춤형 웨딩 플래닝
- 💰 **통합 예산 관리**: 실시간 지출 추적 및 예산 최적화  
- 📋 **스마트 체크리스트**: D-Day 맞춤형 자동 일정 관리
- 🏢 **업체 추천 시스템**: 예산과 취향에 맞는 신뢰할 수 있는 업체 매칭
- 📊 **데이터 기반 의사결정**: 투명한 정보 제공으로 합리적 선택 지원

---

## 🏗️ 현재 개발 현황

### ✅ 완료된 기능
- **데이터베이스 설계**: 사용자, 예산, 이벤트, 업체 정보 스키마 구축
- **자연어 파싱**: 한국어 입력에서 날짜, 지역, 예산 정보 자동 추출
- **업체 데이터베이스**: 웨딩홀, 스튜디오, 드레스, 메이크업 업체 데이터 수집
- **대화 요약 시스템**: AI와의 대화 내용 저장 및 히스토리 관리
- **콘솔 챗봇**: 기본적인 웨딩 상담 기능 구현
- **예산 관리 시스템**: 카테고리별 예산 설정 및 추적
- **타임라인 관리**: 결혼 준비 일정 자동 생성 및 관리

### 🔄 현재 작업 중
- **React 프론트엔드**: 사용자 인터페이스 개발
- **추천 알고리즘**: 사용자 선호도 기반 업체 추천 로직
- **챗봇 UX 개선**: 더 자연스러운 대화 흐름 구현

### 📋 계획된 기능
- **모바일 앱**: React Native 기반 모바일 애플리케이션
- **실시간 알림**: 중요 일정 및 할인 정보 푸시
- **소셜 기능**: 후기 공유 및 커뮤니티 기능
- **영감 보드**: 웨딩 스타일 큐레이션 및 무드보드

---

## 🛠️ 기술 스택

### Backend
- **Python 3.8+**: 메인 개발 언어
- **SQLite**: 데이터베이스 (개발용, 추후 PostgreSQL 예정)
- **Natural Language Processing**: 한국어 입력 파싱
- **Pandas**: 데이터 처리 및 분석

### Frontend  
- **React 18**: 사용자 인터페이스
- **Tailwind CSS**: 스타일링
- **Lucide React**: 아이콘 시스템

### AI & Data
- **LLM Integration**: Claude/GPT 등 대화형 AI 연동 (계획)
- **Vector Database**: 업체 정보 시맨틱 검색 (계획)

---

## 📂 프로젝트 구조

```
MarryRoute/
├── README.md
├── src/
│   └── MarryRouteReactApp.tsx  # React 메인 앱
├── min/                        # 백엔드 모듈들
│   ├── summary.py              # 대화 요약 관리
│   ├── parser.py               # 자연어 파싱
│   ├── memory.py               # 사용자 프로필/예산 관리
│   ├── events.py               # 이벤트 CRUD
│   ├── timeline.py             # 타임라인 관리
│   ├── chat.py                 # 콘솔 챗봇
│   ├── catalog_bridge.py       # 업체 추천 시스템
│   └── csv_import.py           # 데이터 임포트
├── data/                       # 업체 데이터
│   ├── MarryRouteDB_wedding_hall.csv
│   ├── MarryRouteDB_studio.csv
│   ├── MarryRouteDB_wedding_dress.csv
│   └── MarryRouteDB_makeup.csv
├── schema/
│   ├── schema.sql              # 기본 데이터베이스 스키마
│   └── add_schema.sql          # 확장 스키마
└── docs/                       # 프로젝트 문서들
```

---

## 🚀 빠른 시작

### 1. 저장소 클론
```bash
git clone https://github.com/your-username/MarryRoute.git
cd MarryRoute
```

### 2. Python 환경 설정
```bash
python -m venv venv
source venv/bin/activate  # Windows: .\venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 데이터베이스 초기화
```bash
python min/apply_add_schema.py  # 스키마 생성
python min/csv_import.py data/*.csv  # 업체 데이터 임포트
```

### 4. 콘솔 챗봇 실행
```bash
python min/chat.py
```

### 5. React 앱 실행 (개발 중)
```bash
# React 앱 설정 및 실행 (진행 중)
npm install
npm start
```

---

## 💡 주요 특징

### 🤖 AI 기반 대화형 플래닝
```python
# 자연어로 예산과 일정 입력
"본식은 10월 26일이고, 예산은 드레스 300-400만원, 스튜디오는 홍대입구역 근처로 했으면 좋겠어"
```

### 📊 데이터 기반 추천
- 지역 우선 정렬 → 가격 오름차순
- 예산 범위 내 맞춤 필터링
- 실제 후기 기반 신뢰도 평가

### 💰 투명한 예산 관리
- 카테고리별 예산 설정 및 추적
- 실시간 지출 현황 모니터링
- 절약 팁 및 대안 제안

---

## 📋 필요한 패키지

```
pandas>=1.3.0
sqlite3
argparse
datetime
typing
pathlib
json
re
```

---

## 🎨 브랜딩 & 디자인

### 서비스명
- **한국어**: 메리루트 (MarryRoute)
- **챗봇**: 마리 (친근한 AI 어시스턴트)
- **태그라인**: "결혼까지 가장 짧은 루트"

### 컬러 팔레트
```css
/* 메인 컬러 */
--primary: #C8A96A;        /* 골드 액센트 */
--background: #F5F1E8;     /* 웜 아이보리 */
--text: #0B1220;          /* 다크 네이비 */
--accent: #23C19C;        /* 세이빙스 그린 */
```

---

## 🔮 로드맵

### Phase 1: MVP (현재 진행)
- [x] 기본 데이터베이스 구축
- [x] 자연어 파싱 시스템
- [x] 콘솔 기반 챗봇
- [🔄] React 웹 앱 개발

### Phase 2: 베타 출시
- [ ] 웹 앱 배포
- [ ] 사용자 피드백 수집
- [ ] AI 대화 품질 개선

### Phase 3: 확장
- [ ] 모바일 앱 개발
- [ ] 업체 파트너십 확대
- [ ] 고급 추천 알고리즘

---

## 🤝 기여하기

현재 활발히 개발 중인 프로젝트입니다. 기여를 원하시면:

1. 참여 전: 먼저 Issues 탭을 확인하여 현재 진행 중인 작업이나 논의가 필요한 내용이 있는지 살펴보세요.
2. 기능 제안/버그 리포트: 새로운 아이디어가 있으시거나 버그를 발견하셨다면, Issues 탭에 자세히 남겨주세요.
3. 코드 기여: 직접 코드로 기여하고 싶으시다면, Pull Request를 생성하여 보내주세요.

---

## 📞 연락처

- **이메일**: contact@marryroute.gmail.com (예정)
- **개발자**: 배&민 공동 개발 🛵
    - [[GitHub Profile: baesisi3648](https://github.com/baesisi3648)]
    - [[GitHub Profile: ming2tofu33](https://github.com/ming2tofu33)]

---

## 📄 라이선스

이 프로젝트는 현재 개발 중이며, 라이선스는 추후 결정될 예정입니다.

---

*"결혼 준비의 모든 스트레스를 덜어내고, 두 사람만의 특별한 순간에 집중할 수 있도록 돕겠습니다."* - 마리 🤖💕