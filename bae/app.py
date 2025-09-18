# 목적: 메리루트 미니 웹 UI (LLM/오프라인 자동 전환)
# 실행: streamlit run app.py

import os
import json
import traceback
from typing import List, Dict, Any

import streamlit as st

# .env 자동 로드
try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv())
except Exception:
    pass

# 내부 모듈 가져오기
from tools import DB_DEFAULT, tool_update_from_text, tool_recommend, tool_catalog
from planner_update import _fetch_state, build_summary_text

# LLM 모드 (가능하면 사용)
USE_LLM = True
try:
    import assistant  # 우리가 만든 assistant.py
    HAS_ASSISTANT = True
except Exception:
    HAS_ASSISTANT = False
    USE_LLM = False

if not os.environ.get("OPENAI_API_KEY"):
    USE_LLM = False

st.set_page_config(page_title="메리루트 · AI 웨딩플래너", page_icon="💍", layout="wide")

# ---------------------------
# 세션 스테이트 초기화
# ---------------------------
def _init_session():
    if "history" not in st.session_state:
        st.session_state.history: List[Dict[str, str]] = []
    if "last_answer" not in st.session_state:
        st.session_state.last_answer = ""
    if "mode_forced" not in st.session_state:
        st.session_state.mode_forced = None  # None/ "LLM"/"OFFLINE"
    if "reco_result" not in st.session_state:
        st.session_state.reco_result: Dict[str, Any] = {}
    if "catalog_result" not in st.session_state:
        st.session_state.catalog_result: Dict[str, Any] = {}

_init_session()

# ---------------------------
# 유틸
# ---------------------------
CATS = [("dress","드레스"), ("makeup","메이크업"), ("studio","스튜디오"), ("hall","홀")]

def _mode_label():
    if st.session_state.mode_forced == "LLM":
        return "LLM(강제)"
    if st.session_state.mode_forced == "OFFLINE":
        return "오프라인(강제)"
    return "LLM" if USE_LLM else "오프라인"

def _run_offline(text: str) -> str:
    # 선반영 + 요약 표시 + 추천 키워드 감지는 단순화
    upd = tool_update_from_text(text, db=DB_DEFAULT)
    lines = []
    if upd.get("reinput"):
        lines.append("**[재입력요청]**")
        for m in upd["reinput"]:
            lines.append(f"- {m}")
    lines.append("**[요약]** " + (upd.get("summary") or ""))
    return "\n".join(lines)

def _run_llm(text: str) -> str:
    # assistant.py의 라우팅 사용 (선반영 내장)
    try:
        return assistant.call_llm_with_tools(text, st.session_state.history)
    except Exception as e:
        # 오류 시 오프라인으로 폴백
        st.toast("LLM 오류로 오프라인으로 대체했어요.", icon="⚠️")
        return _run_offline(text)

def _append_history(role: str, content: str):
    st.session_state.history.append({"role": role, "content": content})

# ---------------------------
# 사이드바: 상태/요약/모드
# ---------------------------
with st.sidebar:
    st.markdown("### 💍 메리루트")
    # 모드 강제 토글
    mode = st.radio("모드", ["자동", "LLM", "오프라인"], horizontal=True, index=0)
    if mode == "자동":
        st.session_state.mode_forced = None
    elif mode == "LLM":
        st.session_state.mode_forced = "LLM"
    else:
        st.session_state.mode_forced = "OFFLINE"

    st.caption(f"현재 모드: **{_mode_label()}**")

    # 현재 상태 요약
    try:
        state = _fetch_state(DB_DEFAULT)
        summary = build_summary_text(state)
        st.markdown("#### 🧾 현재 요약")
        st.write(summary)
    except Exception as e:
        st.error(f"상태 로드 오류: {e}")

    # 빠른 추천/목록 실행 UI
    st.markdown("---")
    st.markdown("#### ⚡ 빠른 조회")
    cat_ko = st.selectbox("카테고리", [ko for _, ko in CATS], index=0)
    cat = [en for en, ko in CATS if ko == cat_ko][0]

    col1, col2 = st.columns(2)
    with col1:
        if st.button("추천 보기 (Top5)"):
            st.session_state.reco_result = tool_recommend(cat, limit=5, db=DB_DEFAULT)
            st.session_state.catalog_result = {}
    with col2:
        if st.button("목록 보기 (Top20)"):
            st.session_state.catalog_result = tool_catalog(cat, limit=20, db=DB_DEFAULT)
            st.session_state.reco_result = {}

# ---------------------------
# 메인: 대화 영역
# ---------------------------
st.title("메리루트 · AI 웨딩플래너 (MVP)")

with st.container(border=True):
    st.markdown("##### 대화")
    user_text = st.text_input(
        "자연어로 말씀해 주세요 (예: '스튜디오는 청담역, 드레스 300~400', '예식 10/26')",
        key="chat_input",
        placeholder="드레스 150 정도 생각해, 홀 4000이하, 메컵은 청담역이 좋아 ..."
    )

    cols = st.columns([1,1,2])
    with cols[0]:
        send_clicked = st.button("보내기", type="primary", use_container_width=True)
    with cols[1]:
        if st.button("요약 새로고침", use_container_width=True):
            try:
                st.session_state.last_answer = "**[요약]** " + build_summary_text(_fetch_state(DB_DEFAULT))
            except Exception as e:
                st.session_state.last_answer = f"요약 오류: {e}"

    if send_clicked and user_text.strip():
        # 모드 결정
        effective_mode = st.session_state.mode_forced or ("LLM" if USE_LLM else "OFFLINE")
        if effective_mode == "LLM" and HAS_ASSISTANT and USE_LLM:
            answer = _run_llm(user_text)
        else:
            answer = _run_offline(user_text)

        _append_history("user", user_text)
        _append_history("assistant", answer)
        st.session_state.last_answer = answer

    if st.session_state.last_answer:
        st.markdown(st.session_state.last_answer)

# ---------------------------
# 추천/목록 결과 표시
# ---------------------------
def _render_items(title: str, items: List[Dict[str, Any]]):
    st.markdown(f"#### {title}")
    if not items:
        st.info("결과가 없습니다.")
        return
    for i, r in enumerate(items, 1):
        name = r.get("name") or "-"
        region = r.get("region") or "-"
        mp = r.get("min_price")
        ptxt = "-" if mp in (None, "") else f"{int(mp)}만원~"
        st.write(f"**{i}. {name}**  ·  {region}  ·  {ptxt}")

# 추천
if st.session_state.reco_result:
    _render_items("추천 결과 (지역 우선 → 가격 오름차순)", st.session_state.reco_result.get("items", []))

# 목록
if st.session_state.catalog_result:
    _render_items("카탈로그 (상위 20)", st.session_state.catalog_result.get("items", []))

# ---------------------------
# 하단: 디버그/기타
# ---------------------------
with st.expander("🔧 디버그 보기"):
    st.write("MODE:", _mode_label())
    st.write("DB:", DB_DEFAULT)
    st.write("history:", st.session_state.history[-6:])
