# app.py
import os
import time
import sqlalchemy as sa
import streamlit as st

# LangChain 메시지 타입 (버전 호환)
try:
    from langchain_core.messages import HumanMessage
except Exception:
    try:
        from langchain.schema import HumanMessage
    except Exception:
        # LangChain이 없더라도 최소 동작 보장을 위한 폴백
        class HumanMessage:
            def __init__(self, content: str):
                self.content = content

# --- DB 모듈 ---
# 프로젝트의 db.py 에서 제공된 함수/엔진을 사용
from db import initialize_db, engine

# -------------------------------
# 페이지 설정 (가장 먼저)
# -------------------------------
st.set_page_config(
    page_title="MarryRoute by Marry",
    page_icon="💒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 공통 스타일(카드 등)
st.markdown(
    """
    <style>
    :root {
        --text-color: #1f2937;
    }
    .card{
        border:1px solid #e5e7eb;
        border-radius:12px;
        padding:1rem 1.2rem;
        margin:0.5rem 0 1rem 0;
        background:#ffffff;
    }
    .sidebar-logo h1{margin:0;}
    .sidebar-logo p{margin:0; color:#6b7280;}
    </style>
    """,
    unsafe_allow_html=True
)

# 세션 상태 기본값
if "page" not in st.session_state:
    st.session_state.page = "home"
if "messages" not in st.session_state:
    st.session_state.messages = []

# -------------------------------
# DB 초기화 (앱 시작시 한 번)
# -------------------------------
try:
    db = initialize_db()
    print("DB 초기화 성공")
except Exception as e:
    st.error(f"DB 초기화 오류: {e}")

# -------------------------------
# 유틸 / 매핑
# -------------------------------
def map_db_status_to_timeline(db_status: str) -> str:
    """DB 상태를 타임라인 상태로 매핑"""
    mapping = {
        "completed": "completed",
        "in_progress": "upcoming",
        "pending": "pending",
        "cancelled": "cancelled",
    }
    return mapping.get((db_status or "").lower(), "pending")


def get_category_icon(category: str) -> str:
    """카테고리별 아이콘 반환"""
    icons = {
        "venue": "🏛️",
        "dress": "👗",
        "photo": "📸",
        "makeup": "💄",
        "general": "📝",
    }
    return icons.get((category or "general").lower(), "📝")


# -------------------------------
# DB 조회 with 캐시
# -------------------------------
@st.cache_data(ttl=60)
def fetch_schedule_from_db():
    """DB에서 사용자 일정 조회 (1분 캐시)"""
    user_id = os.getenv("DEFAULT_USER_ID", "mvp-test-user")

    try:
        with engine.connect() as conn:
            result = conn.execute(
                sa.text(
                    """
                    SELECT id, title, scheduled_date, scheduled_time, status, category, description, priority
                    FROM user_schedule
                    WHERE user_id = :user_id
                    ORDER BY scheduled_date ASC, scheduled_time ASC
                    """
                ),
                {"user_id": user_id},
            )

            schedules = result.fetchall()

            timeline_items = []
            for s in schedules:
                timeline_items.append(
                    {
                        "id": s[0],
                        "title": s[1],
                        "date": str(s[2]) if s[2] else "",
                        "time": str(s[3]) if s[3] else "",
                        "status": map_db_status_to_timeline(s[4]),
                        "category": s[5] or "general",
                        "description": s[6] or "",
                        "priority": (s[7] or "medium").lower(),
                    }
                )

            return timeline_items
    except Exception as e:
        print(f"일정 조회 오류: {e}")
        return []


# -------------------------------
# 사이드바
# -------------------------------
def create_sidebar():
    with st.sidebar:
        st.markdown(
            '<div class="sidebar-logo"><h1>💒 MarryRoute</h1><p>AI 웨딩 플래너</p></div>',
            unsafe_allow_html=True,
        )
        st.markdown("---")

        nav_buttons = {
            "💬 마리": "chat",
            "🏠 홈": "home",
            "📅 일정": "schedule",
            "🔍 찾기": "search",
            "🗓️ 타임라인": "timeline",
            "💰 예산": "budget",
            "❤️ 찜": "liked",
        }

        for label, page_id in nav_buttons.items():
            if st.button(label, key=f"nav_{page_id}_sidebar"):
                st.session_state.page = page_id
                st.rerun()

        st.markdown("---")
        st.caption("마리에게 물어보기: 사이드바 이동 버튼으로 원하는 페이지에서 바로 작업해요.")


# -------------------------------
# 타임라인
# -------------------------------
def render_timeline():
    st.markdown(
        "<h2 style='text-align: center; color: var(--text-color);'>🗓️ 결혼 준비 타임라인</h2>",
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("### 📋 전체 일정")
    with col2:
        if st.button("🔄 새로고침"):
            st.cache_data.clear()
            st.rerun()

    timeline_items = fetch_schedule_from_db()

    if not timeline_items:
        st.info("등록된 일정이 없습니다. 마리에게 '일정 추가해줘'라고 말해보세요!")
        return

    status_groups = {"completed": [], "upcoming": [], "pending": [], "cancelled": []}
    for item in timeline_items:
        status = item["status"]
        if status in status_groups:
            status_groups[status].append(item)

    # 완료된 일정
    if status_groups["completed"]:
        st.markdown("#### ✅ 완료된 일정")
        for item in status_groups["completed"]:
            with st.container():
                st.markdown('<div class="card">', unsafe_allow_html=True)
                icon = get_category_icon(item["category"])
                st.markdown(f"<h4>{icon} ✅ {item['title']}</h4>", unsafe_allow_html=True)
                st.markdown(f"**완료일:** {item['date']} {item.get('time', '')}")
                if item.get("description"):
                    st.markdown(f"**메모:** {item['description']}")
                st.success("완료")
                st.markdown("</div>", unsafe_allow_html=True)

    # 진행중 일정 (in_progress → upcoming 으로 매핑)
    if status_groups["upcoming"]:
        st.markdown("#### ⏳ 진행중 일정")
        for item in status_groups["upcoming"]:
            with st.container():
                st.markdown('<div class="card">', unsafe_allow_html=True)
                icon = get_category_icon(item["category"])
                st.markdown(f"<h4>{icon} ⏳ {item['title']}</h4>", unsafe_allow_html=True)
                st.markdown(f"**예정일:** {item['date']} {item.get('time', '')}")
                if item.get("description"):
                    st.markdown(f"**메모:** {item['description']}")

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ 완료", key=f"complete_{item['id']}"):
                        complete_msg = f"{item['title']} 완료했어"
                        st.session_state.messages.append(HumanMessage(content=complete_msg))
                        st.cache_data.clear()
                        st.rerun()
                with col2:
                    if st.button("📝 수정", key=f"edit_{item['id']}"):
                        st.info("마리에게 '일정 변경해줘'라고 말해보세요!")

                st.info("진행중")
                st.markdown("</div>", unsafe_allow_html=True)

    # 예정 일정
    if status_groups["pending"]:
        st.markdown("#### 📋 예정 일정")
        for item in status_groups["pending"]:
            with st.container():
                st.markdown('<div class="card">', unsafe_allow_html=True)
                icon = get_category_icon(item["category"])
                priority_color = {
                    "high": "🔴",
                    "medium": "🟡",
                    "low": "🟢",
                }.get(item.get("priority", "medium"), "🟡")
                st.markdown(
                    f"<h4>{icon} {priority_color} {item['title']}</h4>",
                    unsafe_allow_html=True,
                )
                st.markdown(f"**예정일:** {item['date']} {item.get('time', '')}")
                if item.get("description"):
                    st.markdown(f"**메모:** {item['description']}")

                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("🚀 시작", key=f"start_{item['id']}"):
                        start_msg = f"{item['title']} 시작했어"
                        st.session_state.messages.append(HumanMessage(content=start_msg))
                        st.cache_data.clear()
                        st.rerun()
                with col2:
                    if st.button("📝 수정", key=f"edit_pending_{item['id']}"):
                        st.info("마리에게 '일정 변경해줘'라고 말해보세요!")
                with col3:
                    if st.button("❌ 취소", key=f"cancel_{item['id']}"):
                        cancel_msg = f"{item['title']} 취소해줘"
                        st.session_state.messages.append(HumanMessage(content=cancel_msg))
                        st.cache_data.clear()
                        st.rerun()

                st.warning("예정")
                st.markdown("</div>", unsafe_allow_html=True)

    # 취소된 일정
    if status_groups["cancelled"]:
        st.markdown("#### 🚫 취소된 일정")
        for item in status_groups["cancelled"]:
            with st.container():
                st.markdown('<div class="card">', unsafe_allow_html=True)
                icon = get_category_icon(item["category"])
                st.markdown(f"<h4>{icon} 🚫 {item['title']}</h4>", unsafe_allow_html=True)
                st.markdown(f"**취소일(예정일):** {item['date']} {item.get('time', '')}")
                if item.get("description"):
                    st.markdown(f"**메모:** {item['description']}")
                st.error("취소됨")
                st.markdown("</div>", unsafe_allow_html=True)


# -------------------------------
# 일정 페이지
# -------------------------------
def render_schedule():
    st.markdown(
        "<h2 style='text-align: center; color: var(--text-color);'>📅 일정 관리</h2>",
        unsafe_allow_html=True,
    )

    with st.expander("➕ 빠른 일정 추가", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            quick_title = st.text_input("일정 제목", placeholder="예: 드레스 피팅")
            quick_date = st.date_input("날짜")
        with col2:
            quick_time = st.time_input("시간 (선택사항)")
            quick_category = st.selectbox(
                "카테고리",
                ["venue", "dress", "photo", "makeup", "general"],
                format_func=lambda x: {
                    "venue": "웨딩홀",
                    "dress": "드레스",
                    "photo": "촬영",
                    "makeup": "메이크업",
                    "general": "기타",
                }[x],
            )

        quick_description = st.text_area("메모 (선택사항)")

        if st.button("📅 일정 추가", type="primary"):
            if quick_title:
                time_str = f" {quick_time}" if quick_time else ""
                schedule_msg = f"{quick_date}{time_str}에 {quick_title} 일정 추가해줘"
                if quick_description:
                    schedule_msg += f". 메모: {quick_description}"
                if quick_category and quick_category != "general":
                    schedule_msg += f". 카테고리: {quick_category}"

                st.session_state.messages.append(HumanMessage(content=schedule_msg))
                st.success(f"'{quick_title}' 일정 추가 요청을 마리에게 전달했습니다!")
                st.cache_data.clear()
                time.sleep(1)
                st.rerun()
            else:
                st.error("일정 제목을 입력해주세요!")

    st.markdown("---")
    # 현재 일정 표시 (타임라인 재사용)
    render_timeline()


# -------------------------------
# (선택) 다른 페이지 플레이스홀더
# 프로젝트에 이미 구현되어 있다면 해당 함수들은 제거하세요.
# -------------------------------
def render_home():
    st.subheader("🏠 홈")
    st.info("홈 페이지는 준비 중이거나 별도 파일에 구현되어 있을 수 있습니다.")

def render_search():
    st.subheader("🔍 찾기")
    st.info("검색 페이지는 준비 중이거나 별도 파일에 구현되어 있을 수 있습니다.")

def render_budget():
    st.subheader("💰 예산")
    st.info("예산 페이지는 준비 중이거나 별도 파일에 구현되어 있을 수 있습니다.")

def render_chat():
    st.subheader("💬 마리")
    st.write("여기에 채팅 UI가 표시됩니다. (LangChain/Responses 연동 등)")

def render_liked_vendors():
    st.subheader("❤️ 찜")
    st.info("찜한 업체 페이지는 준비 중이거나 별도 파일에 구현되어 있을 수 있습니다.")


# -------------------------------
# 앱 레이아웃 & 라우팅
# -------------------------------
def main():
    create_sidebar()

    page = st.session_state.page
    if page == "home":
        render_home()
    elif page == "search":
        render_search()
    elif page == "schedule":
        render_schedule()
    elif page == "timeline":
        render_timeline()
    elif page == "budget":
        render_budget()
    elif page == "chat":
        render_chat()
    elif page == "liked":
        render_liked_vendors()
    else:
        render_home()


if __name__ == "__main__":
    main()
