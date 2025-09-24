import streamlit as st
import time
import random
from datetime import datetime
import psycopg2 
from graph import app as langgraph_app
from state import State
from langchain_core.messages import HumanMessage, AIMessage
import json
import os


# --- 초기 설정 및 데이터 ---

# Streamlit 페이지 설정
st.set_page_config(
    page_title="MarryRoute by Marry",
    page_icon="💍",
    layout="centered",
    initial_sidebar_state="expanded"
)

# CSS 스타일 (이전과 동일)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900&display=swap');
    html, body, [class*="st-"] {
        font-family: 'Noto Sans KR', sans-serif;
    }
    :root {
        --bg-gradient: linear-gradient(to bottom right, #FFFBF0, #FFFFFF, #FFF7E6);
        --text-color: #5C3A00;
        --subtext-color: #8C5A00;
        --accent-color: #C8A96A;
        --accent-light-color: #F5F1E8;
        --primary-bg-color: #B38B4A;
        --primary-hover-bg-color: #99753D;
    }
    .stApp {
        background: var(--bg-gradient);
    }
    [data-testid="stSidebar"] {
        display: none;
    }
    .card {
        background-color: rgba(255, 255, 255, 0.9);
        border: 1px solid rgba(200, 169, 106, 0.3);
        border-radius: 24px;
        padding: 2rem;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        transition: all 0.3s ease-in-out;
        margin-bottom: 1rem;
        text-align: left;
    }
    .card:hover {
        transform: scale(1.02);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
    }
    .stButton > button {
        width: 100%;
        border-radius: 12px !important;
        font-weight: 600;
        padding: 12px 0;
    }
    .donut-chart-text {
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        text-align: center;
        font-weight: bold;
    }
    .donut-chart-percentage {
        font-size: 2em;
        color: var(--text-color);
    }
    .donut-chart-label {
        font-size: 0.9em;
        color: var(--subtext-color);
        opacity: 0.8;
    }
    [data-testid="stChatInput"] {
        background-color: rgba(255, 255, 255, 0.7);
    }
</style>
""", unsafe_allow_html=True)

# 데이터베이스 연결 초기화 함수
def init_connection():
    try:
        return psycopg2.connect(
            host=st.secrets["postgres"]["host"],
            port=st.secrets["postgres"]["port"], 
            database=st.secrets["postgres"]["database"],
            user=st.secrets["postgres"]["user"],
            password=st.secrets["postgres"]["password"]
        )
    except Exception as e:
        st.error(f"데이터베이스 연결 실패: {e}")
        return None

# 데이터베이스에서 업체 정보를 가져오는 함수
@st.cache_data(ttl=600) # 10분마다 데이터 새로고침
def fetch_vendors_from_db():
    # 각 테이블 이름과 앱에서 사용할 'type' 이름을 짝지어줍니다.
    table_map = {
        'wedding_hall': '웨딩홀',
        'studio': '스튜디오',
        'wedding_dress': '드레스',
        'makeup': '메이크업'
    }
    
    all_vendors = []
    conn = init_connection()
    
    if conn is None:
        # 데이터베이스 연결 실패시 더미 데이터 반환
        return [
            {
                'id': 1,
                'name': '샘플 웨딩홀',
                'type': '웨딩홀', 
                'description': '데이터베이스 연결 중 문제가 발생했습니다.',
                'rating': 4.5,
                'reviews': 100,
                'price': '문의',
                'image': '🏢'
            }
        ]

    try:
        with conn.cursor() as cur:
            # table_map의 모든 테이블을 순회하며 데이터를 가져옵니다.
            for table_name, type_name in table_map.items():
                try:
                    cur.execute(f"SELECT * FROM {table_name};")
                    
                    rows = cur.fetchall()
                    columns = [desc[0] for desc in cur.description]
                    
                    for row in rows:
                        vendor_dict = dict(zip(columns, row))
                        vendor_dict['type'] = type_name 
                        
                        # 딕셔너리 키를 일관되게 매핑합니다.
                        if 'conm' in vendor_dict:
                            vendor_dict['name'] = vendor_dict.pop('conm')
                        
                        if 'min_fee' in vendor_dict:
                            vendor_dict['price'] = vendor_dict.pop('min_fee')
                        
                        # 임시 데이터 추가
                        vendor_dict['description'] = "간단한 업체 설명입니다."
                        vendor_dict['rating'] = random.uniform(4.0, 5.0)
                        vendor_dict['reviews'] = random.randint(50, 500)
                        vendor_dict['image'] = '🏢'
                        
                        all_vendors.append(vendor_dict)
                        
                except Exception as table_error:
                    st.warning(f"{table_name} 테이블 조회 실패: {table_error}")
                    continue
                    
    except Exception as e:
        st.error(f"데이터베이스 조회 중 오류: {e}")
        return []
    finally:
        conn.close()
        
    return all_vendors

# --- 기존 데이터 (vendors 제외) ---
timeline_items = [
    { "id": 1, "title": "예식장 예약", "date": "2025-03-15", "status": "completed", "category": "venue" },
    { "id": 2, "title": "드레스 피팅", "date": "2025-04-20", "status": "upcoming", "category": "dress" },
    { "id": 3, "title": "스튜디오 촬영", "date": "2025-05-10", "status": "pending", "category": "photo" },
]

budget_categories = [
    { "name": "웨딩홀", "budget": 5000, "spent": 3950, "color": "#C8A96A" },
    { "name": "스튜디오", "budget": 200, "spent": 150, "color": "#23C19C" },
    { "name": "드레스", "budget": 200, "spent": 150, "color": "#FF6B6B" },
]

# --- 유틸리티 함수 (이전과 동일) ---

def calculate_dday(wedding_date_str):
    today = datetime.now().date()
    wedding_date = datetime.strptime(wedding_date_str, "%Y-%m-%d").date()
    delta = wedding_date - today
    return delta.days if delta.days > 0 else 0

def get_next_event():
    upcoming = [item for item in timeline_items if item['status'] == 'upcoming' or item['status'] == 'pending']
    upcoming.sort(key=lambda x: datetime.strptime(x['date'], "%Y-%m-%d"))
    return upcoming[0] if upcoming else None

def donut_chart_svg(percentage, color, radius=50, stroke_width=10):
    circumference = 2 * 3.14159 * radius
    offset = circumference - (percentage / 100) * circumference
    return f"""
    <div style="position: relative; width: {radius*2+stroke_width}px; height: {radius*2+stroke_width}px;">
        <svg width="{radius*2+stroke_width}" height="{radius*2+stroke_width}" style="transform: rotate(-90deg);">
            <circle cx="{radius+stroke_width/2}" cy="{radius+stroke_width/2}" r="{radius}" fill="none" stroke="#E5E7EB" stroke-width="{stroke_width}"></circle>
            <circle cx="{radius+stroke_width/2}" cy="{radius+stroke_width/2}" r="{radius}" fill="none" stroke="{color}" stroke-width="{stroke_width}" stroke-dasharray="{circumference}" stroke-dashoffset="{offset}" stroke-linecap="round"></circle>
        </svg>
        <div class="donut-chart-text">
            <span class="donut-chart-percentage">{round(percentage)}%</span>
            <div class="donut-chart-label">사용</div>
        </div>
    </div>
    """

# 기존 세션 상태 초기화 부분 수정
if 'page' not in st.session_state:
    st.session_state.page = 'home'

# LangGraph 메시지 형식으로 변경
if 'messages' not in st.session_state:
    st.session_state.messages = [
        AIMessage(content="안녕하세요! AI 웨딩 플래너 마리예요 ✨ 어떤 도움이 필요하신가요?")
    ]

# 사용자 메모리 초기화
if 'user_memo' not in st.session_state:
    st.session_state.user_memo = {
        "budget": "",
        "preferred_location": "",
        "wedding_date": "",
        "style": "",
        "confirmed_vendors": {},
        "notes": []
    }

if 'checklist_items' not in st.session_state:
    st.session_state.checklist_items = {
        "청첩장 시안 확인": False,
        "하객 명단 정리 시작": True,
        "스튜디오 촬영 컨셉 확정": False,
    }


# --- 페이지 렌더링 함수 ---

def render_home():
    st.markdown("<h1 style='text-align: center; color: var(--text-color);'>MarryRoute 💍</h1>", unsafe_allow_html=True)
    d_day = calculate_dday('2025-07-15')
    next_event = get_next_event()
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### 👰‍♀️ 결혼식까지 남은 시간")
        st.markdown(f"<p style='font-size: 3.5em; font-weight: 900; color: var(--accent-color); margin-bottom: 0.2em;'>D-{d_day}</p>", unsafe_allow_html=True)
        if next_event:
            st.markdown(f"**다음 일정:** {next_event['title']} ({next_event['date']})")
        st.markdown('</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        total_budget = sum(c['budget'] for c in budget_categories)
        total_spent = sum(c['spent'] for c in budget_categories)
        budget_percentage = (total_spent / total_budget) * 100
        with st.container():
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown("#### 💰 예산 현황")
            st.markdown(donut_chart_svg(budget_percentage, "#C8A96A"), unsafe_allow_html=True)
            st.markdown(f"<div style='text-align: center; margin-top: 1rem; font-size: 0.9em;'>총 {total_budget:,}만원 중 {total_spent:,}만원 사용</div>", unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        with st.container():
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown("#### 📊 진행률")
            st.markdown(f"<p style='font-size: 3em; font-weight: 700; color: #23C19C;'>60%</p>", unsafe_allow_html=True)
            st.write("순조롭게 진행중이에요!")
            st.progress(60)
            st.markdown('</div>', unsafe_allow_html=True)
            
    all_vendors = fetch_vendors_from_db()

    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### ✨ AI 추천 업체")
        # 홈 화면에는 최대 3개까지만 보여줍니다.
        for vendor in all_vendors[:3]: 
            col1, col2 = st.columns([1, 4])
            with col1:
                st.markdown(f"<div style='font-size: 2.5em; text-align: center;'>{vendor['image']}</div>", unsafe_allow_html=True)
            with col2:
                st.markdown(f"**{vendor['name']}** ({vendor['type']})")
                st.markdown(f"<span style='color: var(--subtext-color);'>{vendor['description']}</span>", unsafe_allow_html=True)
                st.markdown(f"⭐ {vendor.get('rating', 'N/A')} ({vendor.get('reviews', 0)} 리뷰) | **{vendor.get('price', '가격 문의')}**")
            st.markdown("---")
        st.markdown('</div>', unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### ✅ 진행 중인 체크리스트")
        for item, checked in st.session_state.checklist_items.items():
            new_checked = st.checkbox(item, value=checked, key=f"check_{item}")
            st.session_state.checklist_items[item] = new_checked
        st.markdown('</div>', unsafe_allow_html=True)


def render_search():
    st.markdown("<h2 style='text-align: center; color: var(--text-color);'>🔍 AI 추천 업체 찾기</h2>", unsafe_allow_html=True)
    
    all_vendors = fetch_vendors_from_db()
    
    db_categories = sorted(list(set(v['type'] for v in all_vendors)))
    categories = ['전체'] + db_categories
    
    selected_category = st.selectbox("카테고리 선택", options=categories)
    search_query = st.text_input("업체명이나 지역으로 검색", placeholder="예: 호텔 루미에르, 강남구")
    
    st.markdown("---")

    filtered = all_vendors
    if selected_category != '전체':
        filtered = [v for v in filtered if v['type'] == selected_category]
    if search_query:
        # 검색 필터링을 'name'과 'description'에 대해 수행합니다.
        filtered = [v for v in filtered if search_query.lower() in v['name'].lower() or search_query.lower() in v['description'].lower()]
    
    if not filtered:
        st.info("조건에 맞는 업체 정보가 없습니다.")
    
    for vendor in filtered:
        with st.container():
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown(f"<h3>{vendor.get('image', '🏢')} {vendor['name']}</h3>", unsafe_allow_html=True)
            st.markdown(f"**{vendor['type']}** | <span style='color: var(--subtext-color);'>{vendor['description']}</span>", unsafe_allow_html=True)
            
            # 모든 컬럼을 동적으로 표시하는 로직
            st.markdown("---")
            st.markdown("#### 상세 정보")
            
            # id, type, name, description, image, rating, reviews는 이미 표시했으므로 제외
            excluded_keys = ['id', 'type', 'name', 'description', 'image', 'rating', 'reviews', 'price']
            
            # 표 생성을 위해 두 개의 열(columns) 생성
            cols = st.columns(2)
            item_count = 0

            for key, value in vendor.items():
                if key not in excluded_keys:
                    # 'conm'과 'min_fee'는 이미 'name', 'price'로 바뀌었으므로 제외
                    if key not in ['conm', 'min_fee']:
                        # 가독성을 위해 키 이름 포맷 변경 (예: hall_rental_fee -> Hall Rental Fee)
                        formatted_key = key.replace('_', ' ').capitalize()
                        
                        # 홀수 번째 항목은 첫 번째 열에, 짝수 번째 항목은 두 번째 열에 배치
                        with cols[item_count % 2]:
                            st.markdown(f"**{formatted_key}:** {value}")
                        item_count += 1


            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                st.button("상세보기", key=f"detail_{vendor['id']}")
            with col2:
                st.button("🤍 찜하기", key=f"like_{vendor['id']}")
            st.markdown('</div>', unsafe_allow_html=True)

# ... render_timeline, render_budget, render_chat 함수 및 하단 내비게이션은 이전과 동일 ...
def render_timeline():
    st.markdown("<h2 style='text-align: center; color: var(--text-color);'>🗓️ 결혼 준비 타임라인</h2>", unsafe_allow_html=True)
    for item in sorted(timeline_items, key=lambda x: x['date']):
        with st.container():
            st.markdown('<div class="card">', unsafe_allow_html=True)
            icon = "✅" if item['status'] == 'completed' else "⏳" if item['status'] == 'upcoming' else "📋"
            st.markdown(f"<h4>{icon} {item['title']}</h4>", unsafe_allow_html=True)
            st.markdown(f"**예정일:** {item['date']}")
            if item['status'] == 'completed':
                st.success("완료")
            elif item['status'] == 'upcoming':
                st.info("진행중")
            else:
                st.warning("예정")
            st.markdown('</div>', unsafe_allow_html=True)

def render_budget():
    st.markdown("<h2 style='text-align: center; color: var(--text-color);'>💰 예산 관리</h2>", unsafe_allow_html=True)
    total_budget = sum(c['budget'] for c in budget_categories)
    total_spent = sum(c['spent'] for c in budget_categories)
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### 전체 예산 현황")
        col1, col2 = st.columns(2)
        col1.metric("총 사용액", f"{total_spent:,} 만원", f"{total_spent-total_budget:,} 만원")
        col2.metric("총 예산", f"{total_budget:,} 만원", " ")
        st.progress(total_spent / total_budget)
        st.markdown('</div>', unsafe_allow_html=True)
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### 카테고리별 예산")
        for cat in budget_categories:
            st.markdown(f"**{cat['name']}**")
            st.markdown(f"<span style='color: var(--subtext-color);'>{cat['spent']:,}만원 / {cat['budget']:,}만원</span>", unsafe_allow_html=True)
            st.progress(cat['spent'] / cat['budget'])
        st.markdown('</div>', unsafe_allow_html=True)

def render_chat():
    st.markdown("<h2 style='text-align: center; color: var(--text-color);'>💬 AI 플래너 마리</h2>", unsafe_allow_html=True)
    
    # 채팅 메시지 표시 (LangGraph 메시지 형식)
    for msg in st.session_state.messages:
        role = "assistant" if isinstance(msg, AIMessage) else "user"
        with st.chat_message(role):
            st.write(msg.content)
    
    # 사용자 입력 처리
    if prompt := st.chat_input("마리에게 물어보세요..."):
        # 사용자 메시지 추가
        user_message = HumanMessage(content=prompt)
        st.session_state.messages.append(user_message)
        
        # 사용자 메시지 즉시 표시
        with st.chat_message("user"):
            st.write(prompt)
        
        # AI 응답 생성
        with st.chat_message("assistant"):
            with st.spinner("마리가 생각 중이에요..."):
                try:
                    # LangGraph 상태 생성
                    initial_state = State(
                        messages=st.session_state.messages,
                        memo=st.session_state.user_memo,
                        intent="",
                        tools_needed=[],
                        tool_results={}
                    )
                    
                    # LangGraph 실행
                    result = langgraph_app.invoke(initial_state)
                    
                    # 응답 메시지 추출 (마지막 메시지가 AI 응답)
                    if result["messages"]:
                        ai_response = result["messages"][-1]
                        st.write(ai_response.content)
                        
                        # 세션 상태 업데이트
                        st.session_state.messages = result["messages"]
                        st.session_state.user_memo.update(result["memo"])
                    else:
                        error_msg = "죄송해요, 응답을 생성하는데 문제가 발생했습니다."
                        st.write(error_msg)
                        st.session_state.messages.append(AIMessage(content=error_msg))
                        
                except Exception as e:
                    error_msg = f"오류가 발생했습니다: {str(e)}"
                    st.error(error_msg)
                    st.session_state.messages.append(AIMessage(content="죄송해요, 일시적인 문제가 발생했습니다. 다시 시도해주세요."))

# --- 하단 내비게이션 및 페이지 라우팅 ---
st.markdown("""<div style="position: fixed; bottom: 0; left: 0; width: 100%; background-color: rgba(255, 255, 255, 0.9); backdrop-filter: blur(10px); border-top: 1px solid #eee; padding: 10px 0; z-index: 99;"></div>""", unsafe_allow_html=True)
nav_cols = st.columns(5)
nav_items = {"홈": ("home", "🏠"), "찾기": ("search", "🔍"), "일정": ("timeline", "🗓️"), "예산": ("budget", "💰"), "마리": ("chat", "💬")}
for i, (label, (page_id, icon)) in enumerate(nav_items.items()):
    with nav_cols[i]:
        if st.button(f"{icon} {label}", key=f"nav_{page_id}"):
            st.session_state.page = page_id
            st.rerun()

# 현재 페이지 렌더링
if st.session_state.page == 'home':
    render_home()
elif st.session_state.page == 'search':
    render_search()
elif st.session_state.page == 'timeline':
    render_timeline()
elif st.session_state.page == 'budget':
    render_budget()
elif st.session_state.page == 'chat':
    render_chat()