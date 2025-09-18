# 목적: LLM + 툴콜 기반 대화형 웨딩플래너 (오프라인 백업 라우터 포함)
# 실행: python assistant.py

import os, json, sys, traceback
from typing import List, Dict, Any, Optional

# --- (.env) 자동 로드 ---
try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv())
except Exception:
    pass

# 내부 모듈
from prompts import build_messages
from tools import TOOL_SPECS, run_tool, tool_update_from_text, tool_recommend, tool_catalog, DB_DEFAULT
from planner_update import _fetch_state, build_summary_text

# -------- 설정 --------
MODEL    = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
API_KEY  = os.environ.get("OPENAI_API_KEY")
BASE_URL = os.environ.get("OPENAI_BASE_URL")

USE_LLM = True
client = None
if not API_KEY:
    USE_LLM = False
else:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=API_KEY, base_url=BASE_URL) if BASE_URL else OpenAI(api_key=API_KEY)
    except Exception:
        USE_LLM = False

# -------- 공통 유틸 --------
def _print_summary():
    try:
        st = _fetch_state(DB_DEFAULT)
        print("요약:", build_summary_text(st))
    except Exception as e:
        print("⚠️ 요약 표시 오류:", e)

def _short_suggest():
    return "다음으로 무엇을 해볼까요? 예: `/추천 스튜디오`, `/목록 드레스`, `예식 날짜 10/26로 바꿔줘`"

def _pretty_items(items: List[Dict[str, Any]]) -> str:
    lines = []
    for i, r in enumerate(items, 1):
        name = r.get("name") or "-"
        region = r.get("region") or "-"
        mp = r.get("min_price")
        price = "-" if mp in (None, "") else f"{int(mp)}만원~"
        lines.append(f"{i}. {name} | {region} | {price}")
    return "\n".join(lines) if lines else "(결과 없음)"

# -------- 오프라인 라우터 --------
def offline_route(user_text: str) -> str:
    out_lines = []
    try:
        upd = tool_update_from_text(user_text, db=DB_DEFAULT)
        if upd.get("reinput"):
            out_lines.append("[재입력요청]")
            out_lines += [f"- {m}" for m in upd["reinput"]]
        out_lines.append("[요약] " + upd.get("summary", ""))

        low = user_text.lower()
        want_reco = any(k in low for k in ["추천", "top", "골라", "추천해"])
        want_list = any(k in low for k in ["목록", "리스트", "전체", "더 보여", "더봐", "더봐줘"])
        if want_reco or want_list:
            cat_map = {"스튜디오":"studio","드레스":"dress","메이크업":"makeup","홀":"hall"}
            cat = None
            for k,v in cat_map.items():
                if (k in user_text) or (v in low):
                    cat = v; break
            if not cat:
                out_lines.append("카테고리를 알려주세요. 예: '스튜디오 추천해줘'")
            else:
                if want_reco:
                    rec = tool_recommend(cat, limit=5, db=DB_DEFAULT)
                    out_lines.append(f"[추천:{cat}]")
                    out_lines.append(_pretty_items(rec.get("items", [])))
                if want_list:
                    lst = tool_catalog(cat, limit=20, db=DB_DEFAULT)
                    out_lines.append(f"[목록:{cat}]")
                    out_lines.append(_pretty_items(lst.get("items", [])))
    except Exception as e:
        out_lines.append(f"⚠️ 오프라인 처리 중 오류: {e}")
    out_lines.append(_short_suggest())
    return "\n".join(out_lines)

# -------- LLM 호출 루프 (툴콜 지원) --------
def call_llm_with_tools(user_text: str, history: List[Dict[str,str]]) -> str:
    """
    - build_messages(...)로 컨텍스트 구성
    - tool_calls가 나오면: 그 assistant 메시지를 tool_calls 포함해 추가 → 각 tool 실행 → role:tool 메시지 추가 → 재호출
    - 최종 assistant 텍스트 반환
    """
    # 현재 상태/요약
    try:
        state = _fetch_state(DB_DEFAULT)
    except Exception:
        state = {}

    messages = build_messages(user_text, state, recent_messages=history)

    # OpenAI function tools 정의
    tool_defs = [{
        "type": "function",
        "function": {
            "name": spec["name"],
            "description": spec["description"],
            "parameters": spec["parameters"],
        }
    } for spec in TOOL_SPECS]

    # 초기 메시지들(system/user)
    chat_messages: List[Dict[str, Any]] = [{"role": m["role"], "content": m["content"]} for m in messages]

    # 최대 3회 루프
    for _ in range(3):
        resp = client.chat.completions.create(
            model=MODEL,
            messages=chat_messages,
            tools=tool_defs,
            tool_choice="auto",
            temperature=0.3,
        )
        choice = resp.choices[0]
        msg = choice.message

        # 툴 호출 있는가?
        if msg.tool_calls and len(msg.tool_calls) > 0:
            # 1) tool_calls 포함한 assistant 메시지 추가 (여기가 핵심 수정)
            tool_calls_payload = []
            for tc in msg.tool_calls:
                tool_calls_payload.append({
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                })
            chat_messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": tool_calls_payload
            })

            # 2) 각 툴 실행 → role:tool 메시지 추가 (tool_call_id로 연결)
            for tc in msg.tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except Exception:
                    args = {}
                result = run_tool(name, args)
                chat_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": name,
                    "content": json.dumps(result, ensure_ascii=False)
                })

            # 3) 다음 루프에서 재호출
            continue

        # 최종 텍스트 응답
        return (msg.content or "").strip()

    # 보호적 종료
    return "도구 호출이 반복되어 대화를 마무리합니다. " + _short_suggest()

# -------- 메인 루프 --------
HELP_TEXT = """\
명령어:
  /help        사용법
  /summary     최신 요약 보기
  /mode        현재 모드 표시 (LLM/오프라인)
  /quit        종료
그 외 문장: 자연어로 입력하면 상태 반영(필요 시 추천/목록 포함) 후 답변합니다.
"""

def main():
    print("=== 메리루트 LLM 어시스턴트 ===")
    print(HELP_TEXT)
    print(f"모드: {'LLM' if USE_LLM else '오프라인'} (모델={MODEL if USE_LLM else '-'})")

    history: List[Dict[str,str]] = []
    while True:
        try:
            text = input("You> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n안녕히 가세요!"); break

        if not text:
            continue

        # 명령 처리
        if text.startswith("/"):
            cmd = text.split()[0].lower()
            if cmd == "/help":
                print(HELP_TEXT)
            elif cmd == "/summary":
                _print_summary()
            elif cmd == "/mode":
                print(f"현재 모드: {'LLM' if USE_LLM else '오프라인'} (MODEL={MODEL})")
            elif cmd == "/quit":
                print("안녕히 가세요!"); break
            else:
                print("알 수 없는 명령입니다. /help 를 입력해 보세요.")
            continue

        # 일반 대화
        try:
            if USE_LLM and client is not None:
                answer = call_llm_with_tools(text, history)
            else:
                answer = offline_route(text)
        except Exception as e:
            print("⚠️ 처리 중 오류:", e)
            if USE_LLM:
                print("→ 오프라인 라우터로 대체합니다.")
                answer = offline_route(text)

        print(answer)
        # history에 최근 턴 저장
        history.append({"role":"user","content":text})
        history.append({"role":"assistant","content":answer})

if __name__ == "__main__":
    if sys.version_info < (3,8):
        print("⚠️ Python 3.8+ 권장")
    main()
