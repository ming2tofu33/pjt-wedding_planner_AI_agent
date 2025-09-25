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
import urllib.parse

# --- 초기 설정 및 데이터 ---

# Streamlit 페이지 설정
st.set_page_config(
    page_title="MarryRoute by Marry",
    page_icon="💍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS 스타일 수정
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
    /* 사이드바 스타일 추가 */
    [data-testid="stSidebar"] {
        background: linear-gradient(to bottom, #FFFBF0, #F5F1E8);
        border-right: 1px solid #e0e0e0;
        padding: 2rem;
    }
    .sidebar-logo {
        text-align: center;
        margin-bottom: 2rem;
    }
    .sidebar-logo h1 {
        color: var(--accent-color);
        font-weight: 900;
        font-size: 2.5em;
        margin: 0;
    }
    .sidebar-logo p {
        color: var(--subtext-color);
        font-size: 0.9em;
        margin-top: 0;
    }
    /* 사이드바 버튼 디자인 개선 */
    [data-testid="stSidebar"] .stButton > button {
        background-color: transparent !important;
        border: none !important;
        color: var(--text-color) !important;
        text-align: left;
        padding: 12px 10px;
        margin: 5px 0;
        transition: all 0.2s;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background-color: var(--accent-light-color) !important;
        color: var(--text-color) !important;
        border-left: 5px solid var(--accent-color) !important;
    }
    [data-testid="stSidebar"] .stButton > button:focus {
        box-shadow: none !important;
    }
    /* 체크리스트 아이템 정렬 */
    div.st-emotion-cache-121p653 > p {
        flex-grow: 1;
        margin: 0;
    }
</style>
""", unsafe_allow_html=True)

# 데이터베이스 연결 초기화 함수 (기존과 동일)
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

# 데이터베이스에서 업체 정보를 가져오는 함수 (기존과 동일)
@st.cache_data(ttl=600)
def fetch_vendors_from_db():
    table_map = {
        'wedding_hall': '웨딩홀',
        'studio': '스튜디오',
        'wedding_dress': '드레스',
        'makeup': '메이크업'
    }
    
    all_vendors = []
    conn = init_connection()
    
    if conn is None:
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
            for table_name, type_name in table_map.items():
                try:
                    cur.execute(f"SELECT * FROM {table_name};")
                    
                    rows = cur.fetchall()
                    columns = [desc[0] for desc in cur.description]
                    
                    for row in rows:
                        vendor_dict = dict(zip(columns, row))
                        vendor_dict['type'] = type_name 
                        
                        if 'conm' in vendor_dict:
                            vendor_dict['name'] = vendor_dict.pop('conm')
                            vendor_dict['id'] = vendor_dict['name']
                        
                        if 'min_fee' in vendor_dict:
                            vendor_dict['price'] = vendor_dict.pop('min_fee')
                        
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

# --- 기존 데이터 ---
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

# --- 유틸리티 함수 (기존과 동일) ---
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

# --- 세션 상태 초기화 ---
if 'page' not in st.session_state:
    st.session_state.page = 'chat'
if 'messages' not in st.session_state:
    new_intro_message = """
안녕하세요! 당신의 완벽한 결혼식을 위한 AI 웨딩플래너, **마리**입니다. ✨ 저와 함께 모든 결혼 준비 과정을 쉽고 즐겁게 만들어가요.

저희 메리루트 서비스는 별도의 개인정보 없이도 바로 이용할 수 있어요. 혹시 이름, 예식 희망일, 예산 범위 등 기본적인 정보를 알려주시면 더 자세하고 맞춤화된 플래닝을 도와드릴 수 있어요. 물론, 지금 당장 궁금한 점이 있다면 채팅으로 자유롭게 물어봐 주세요!

더욱 정확한 맞춤형 정보를 원하시면 아래 옵션 중 한 가지를 선택해 주세요.
"""
    st.session_state.messages = [
        AIMessage(content=new_intro_message)
    ]
if 'user_memo' not in st.session_state:
    st.session_state.user_memo = {
        "budget": "",
        "preferred_location": "",
        "wedding_date": "",
        "style": "",
        "confirmed_vendors": {},
        "notes": "" # 메모를 하나의 문자열로 저장하도록 변경
    }
if 'checklist_items' not in st.session_state:
    # 체크리스트를 딕셔너리에서 리스트로 변경
    st.session_state.checklist_items = [
        {"item": "청첩장 시안 확인", "checked": False},
        {"item": "하객 명단 정리 시작", "checked": True},
        {"item": "스튜디오 촬영 컨셉 확정", "checked": False},
    ]
if 'liked_vendors' not in st.session_state:
    st.session_state.liked_vendors = []

# --- 사이드바 내비게이션 함수 ---
def create_sidebar():
    with st.sidebar:
        st.markdown('<div class="sidebar-logo"><h1>💍 MarryRoute</h1><p>AI 웨딩 플래너</p></div>', unsafe_allow_html=True)
        st.markdown("---")
        
        # 페이지 이동 버튼 순서
        nav_buttons = {
            "💬 마리": 'chat', # 가장 위로 이동
            "🏠 홈": 'home',
            "🔍 찾기": 'search',
            "🗓️ 타임라인": 'timeline',
            "💰 예산": 'budget',
            "❤️ 찜": 'liked',
        }
        for label, page_id in nav_buttons.items():
            if st.button(label, key=f"nav_{page_id}_sidebar"):
                st.session_state.page = page_id
                st.rerun()

        st.markdown("---")
        
        # 사용자 메모 및 D-day 위젯
        d_day = calculate_dday('2025-07-15')
        st.info(f"결혼식까지 **D-{d_day}**일 남았어요!")
        st.markdown("### 📝 나의 메모")
        # 메모를 텍스트 에리어에 바로 저장
        st.session_state.user_memo["notes"] = st.text_area(
            "중요한 내용을 기록해두세요.", 
            value=st.session_state.user_memo["notes"], 
            height=150, 
            key="user_memo_area"
        )
        st.markdown("---")
        
        # 체크리스트 기능
        st.markdown("### ✅ 결혼 준비 체크리스트")
        for i, item in enumerate(st.session_state.checklist_items):
            cols = st.columns([0.8, 0.1, 0.1])
            with cols[0]:
                checked = st.checkbox(item["item"], value=item["checked"], key=f"check_{i}")
                st.session_state.checklist_items[i]["checked"] = checked
            with cols[1]:
                if st.button("✖️", key=f"delete_check_{i}"):
                    st.session_state.checklist_items.pop(i)
                    st.rerun()
        
        new_item = st.text_input("새 항목 추가", key="new_checklist_item")
        if new_item:
            if st.button("추가"):
                st.session_state.checklist_items.append({"item": new_item, "checked": False})
                st.session_state.new_checklist_item = ""  # 입력창 비우기
                st.rerun()


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


def render_search():
    st.markdown("<h2 style='text-align: center; color: var(--text-color);'>🔍 AI 추천 업체 찾기</h2>", unsafe_allow_html=True)
    
    all_vendors = fetch_vendors_from_db()
    
    categories_order = ['전체', '웨딩홀', '스튜디오', '드레스', '메이크업']
    db_categories = sorted(list(set(v['type'] for v in all_vendors)))
    ordered_categories = [c for c in categories_order if c in ['전체'] + db_categories]
    
    selected_category = st.selectbox("카테고리 선택", options=ordered_categories)
    search_query = st.text_input("업체명이나 지하철역으로 검색", placeholder="예: 더채플, 압구정로데오역")
    
    st.markdown("---")

    filtered = all_vendors
    if selected_category != '전체':
        filtered = [v for v in filtered if v['type'] == selected_category]
    if search_query:
        filtered = [v for v in filtered if (
            search_query.lower() in v['name'].lower() or 
            (v.get('subway') and search_query.lower() in v['subway'].lower())
        )]
    
    if not filtered:
        st.info("조건에 맞는 업체 정보가 없습니다.")
    
    # 찜하기 버튼 클릭 시 호출될 함수
    def handle_like_button(vendor_info):
        if vendor_info not in st.session_state.liked_vendors:
            st.session_state.liked_vendors.append(vendor_info)
            st.toast(f"❤️ {vendor_info['name']}이(가) 찜 목록에 추가되었습니다!")

    for i, vendor in enumerate(filtered):
        with st.container():
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown(f"<h3>{vendor.get('image', '🏢')} {vendor['name']}</h3>", unsafe_allow_html=True)
            st.markdown(f"**{vendor['type']}** | <span style='color: var(--subtext-color);'>{vendor['description']}</span>", unsafe_allow_html=True)
            
            st.markdown("---")
            st.markdown("#### 상세 정보")
            
            # 정보 딕셔너리 및 한글 변환 매핑
            info_to_display = {
                'rating': ('⭐ 평점', '리뷰'),
                'price': ('💰 가격', None),
                'subway': ('🚇 지하철', None),
                'bus': ('🚌 버스', None),
                'tel': ('📞 전화', None),
                'address': ('📍 주소', None),
                'meal_price_per_person': ('🍽️ 식대', '원'),
                'min_guarantee': ('👥 최소 보증 인원', '명'),
                'parking_space': ('🚗 주차 공간', '대'),
                'rental_fee': ('💵 대관료', '원'),
                'peak_season_fee': ('🌸 성수기 대관료', '원'),
                'off_peak_season_fee': ('🍂 비수기 대관료', '원'),
                'peak': ('최성수기', ' (피크)'),
                'off_peak': ('비성수기', ' (피크)'),
            }
            
            # 업체 상세 정보 테이블로 표시
            cols = st.columns(2)
            item_count = 0
            for key, (label, unit) in info_to_display.items():
                if key in vendor and vendor[key] is not None:
                    value = vendor[key]
                    if key in ['peak', 'off_peak']:
                        value = 'O' if value else 'X'
                        formatted_value = f"{label} {value}"
                    elif key in ['peak_season_fee', 'off_peak_season_fee', 'meal_price_per_person', 'min_guarantee', 'parking_space', 'rental_fee']:
                        formatted_value = f"{value:,d}{unit}" if isinstance(value, int) else f"{value}{unit}"
                    elif key == 'rating':
                        formatted_value = f"{value} ({vendor['reviews']}{unit[1]})"
                    elif key == 'price':
                         formatted_value = value
                    else:
                        formatted_value = value
                    
                    with cols[item_count % 2]:
                        st.markdown(f"**{label}:** {formatted_value}")
                    item_count += 1
            
            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                search_query_encoded = urllib.parse.quote(vendor['name'])
                naver_url = f"https://search.naver.com/search.naver?query={search_query_encoded}"
                st.markdown(f'<a href="{naver_url}" target="_blank"><button style="width: 100%; border-radius: 12px; font-weight: 600; padding: 12px 0;">상세보기</button></a>', unsafe_allow_html=True)
            with col2:
                # key에 인덱스(i)를 추가하여 고유하게 만듦
                st.button("🤍 찜하기", key=f"like_{i}_{vendor.get('id', vendor['name'])}", on_click=handle_like_button, args=(vendor,))
            st.markdown('</div>', unsafe_allow_html=True)


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
    
    # 첫 번째 메시지에 대한 버튼 옵션 정의
    button_options = {
        "📋 개인 정보 입력": "개인 정보(이름, 예식일, 예산 등)를 입력하고 싶어요.",
        "🏃‍♀️ 준비 시간이 부족하고 너무 바빠요": "시간을 절약할 수 있는 효율적인 준비 방법을 추천해 주세요.",
        "✨ 개성 있고 특별한 웨딩을 원해요": "트렌디하고 개성 있는 컨셉과 업체를 추천해 주세요.",
        "💡 합리적이고 계획적인 소비가 목표예요": "가성비 좋은 웨딩홀과 업체를 찾고 예산 관리를 도와주세요.",
        "😎 다 귀찮고 알잘딱깔센": "알아서 척척! 마리가 모든 것을 추천하고 계획해 주세요."
    }
    
    # 버튼 클릭 시 실행될 콜백 함수 정의 (st.rerun() 제거)
    def handle_intro_button_click(prompt_content):
        # 1. 버튼 내용을 HumanMessage로 추가
        st.session_state.messages.append(HumanMessage(content=prompt_content))
        # 2. Streamlit이 상태 변경을 감지하고 자동으로 재실행합니다.

    # 1. 메시지 렌더링 및 버튼 표시
    for i, msg in enumerate(st.session_state.messages):
        role = "assistant" if isinstance(msg, AIMessage) else "user"
        with st.chat_message(role):
            st.write(msg.content)
            
            # 첫 번째 AIMessage (인트로 메시지) 바로 아래에만 버튼을 표시합니다.
            if i == 0 and role == "assistant":
                
                col1, col2, col3 = st.columns([1, 1, 1])
                cols = [col1, col2, col3, col1, col2] # 5개의 버튼을 3열로 배치

                st.markdown("어떤 방식으로 시작해볼까요?") 
                
                for j, (btn_label, prompt_content) in enumerate(button_options.items()):
                    with cols[j]:
                        # on_click 인자를 사용하여 콜백 함수와 인자를 명시적으로 연결
                        st.button(
                            btn_label, 
                            key=f"chat_intro_btn_{j}",
                            on_click=handle_intro_button_click,
                            args=(prompt_content,)
                        )
                        

    # 2. 일반 채팅 입력 처리: 입력 시 메시지를 추가하고 RERUN하여 AI 호출을 트리거
    if prompt := st.chat_input("마리에게 물어보세요..."):
        st.session_state.messages.append(HumanMessage(content=prompt))
        st.rerun() # 즉시 재실행하여 아래 AI 호출 블록을 실행하도록 유도

    # 3. 통합 AI 호출 로직: 새로운 사용자 메시지(HumanMessage)가 있으면 AI 호출
    # 버튼 클릭으로 재실행되었거나, 채팅 입력 후 재실행되었을 때 모두 이 블록을 통해 AI 응답을 생성합니다.
    if st.session_state.messages and isinstance(st.session_state.messages[-1], HumanMessage):
        
        with st.chat_message("assistant"):
            with st.spinner("마리가 생각 중이에요..."):
                try:
                    initial_state = State(
                        messages=st.session_state.messages,
                        memo=st.session_state.user_memo,
                        intent="",
                        tools_needed=[],
                        tool_results={}
                    )
                    
                    result = langgraph_app.invoke(initial_state)
                    
                    if result["messages"]:
                        ai_response = result["messages"][-1]
                        st.write(ai_response.content)
                        
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
                    

def render_liked_vendors():
    st.markdown("<h2 style='text-align: center; color: var(--text-color);'>❤️ 찜한 업체 목록</h2>", unsafe_allow_html=True)
    if not st.session_state.liked_vendors:
        st.info("찜한 업체가 아직 없어요. '업체 찾기'에서 마음에 드는 업체를 찜해보세요!")
        return

    for i, vendor in enumerate(st.session_state.liked_vendors):
        with st.container():
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown(f"<h3>{vendor.get('image', '🏢')} {vendor['name']}</h3>", unsafe_allow_html=True)
            st.markdown(f"**{vendor['type']}** | <span style='color: var(--subtext-color);'>{vendor['description']}</span>", unsafe_allow_html=True)
            st.markdown("---")
            st.markdown(f"**별점:** {vendor.get('rating', 'N/A')} ({vendor.get('reviews', 0)} 리뷰) | **가격:** {vendor.get('price', '문의')}")
            
            if st.button("💔 찜 취소", key=f"unlike_{i}_{vendor['name']}"):
                st.session_state.liked_vendors.pop(i)
                st.toast(f"💔 {vendor['name']}이(가) 찜 목록에서 삭제되었습니다.")
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

# --- 메인 함수 및 페이지 라우팅 ---
create_sidebar()

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
elif st.session_state.page == 'liked':
    render_liked_vendors()