# 목적: LLM + 툴콜 기반 대화형 웨딩플래너 (오프라인 백업 라우터 포함)
# 실행: python assistant.py

import os, json, sys, re
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

# -------- 선(先) 반영 가드레일 & 카테고리 추정 --------
_BUDGET_TRIGGERS = [
    r"\b예산\b", r"\b변경\b", r"바꿔", r"바꾸", r"설정", r"잡아줘",
    r"이하", r"이상", r"[~\-–—]", r"만원", r"\d+\s*(?:만원|만|원)\b", r"\b\d{2,4}\b",
    # 의지/선호/범위 표현
    r"생각해", r"생각이야", r"할래", r"하고\s*싶", r"원해", r"좋[아을]", r"맞춰", r"맞출래",
    r"정도", r"대로", r"잡자", r"잡을래", r"정해줘", r"정하자"
]
_CAT_HINTS = ["드레스","dress","메이크업","makeup","스튜디오","studio","홀","hall","예식","본식","결혼","웨딩"]

_CAT_MAP_IN = {
    "드레스":"dress","dress":"dress",
    "메이크업":"makeup","메컵":"makeup","makeup":"makeup","헤어":"makeup","헤메":"makeup",
    "스튜디오":"studio","studio":"studio","촬영":"studio","리허설":"studio","스냅":"studio",
    "홀":"hall","웨딩홀":"hall","예식장":"hall","hall":"hall"
}
_KO_BY_CAT = {"dress":"드레스","makeup":"메이크업","studio":"스튜디오","hall":"홀"}

def needs_state_update(text: str) -> bool:
    if not text: return False
    low = text.lower()
    if any(h in text or h in low for h in _CAT_HINTS):
        if any(re.search(p, text) for p in _BUDGET_TRIGGERS):
            return True
    # 숫자만/숫자+이하/이상 등 단독 입력
    if re.search(r"^\s*\d+\s*(만원|만|원)?\s*(이하|이상|이내|초과|정도|대로)?\s*$", text):
        return True
    return False

def _infer_recent_category(history: List[Dict[str,str]], fallback: Optional[str] = None) -> Optional[str]:
    for m in reversed(history[-6:]):
        t = (m.get("content") or "").lower()
        for k, v in _CAT_MAP_IN.items():
            if k.lower() in t:
                return v
    return fallback

def _ensure_category_in_text(text: str, history: List[Dict[str,str]]) -> str:
    # ex) "150 정도 생각해" → 최근 맥락이 드레스면 "드레스 150 정도 생각해"
    bare = re.match(r"^\s*\d+\s*(만원|만|원)?\s*(이하|이상|이내|초과|정도|대로)?\s*$", text)
    vague = (("예산" in text) or ("정도" in text) or ("대로" in text)) and not any(k in text for k in _KO_BY_CAT.values())
    if bare or vague:
        cat = _infer_recent_category(history)
        if cat:
            ko = _KO_BY_CAT.get(cat, cat)
            return f"{ko} {text}"
    return text

def pre_update_if_needed(user_text: str, history: Optional[List[Dict[str,str]]] = None) -> Dict[str, Any]:
    """
    예산/변경 요청이면 DB에 먼저 반영하고,
    LLM에 넘길 system 힌트와 사용자 프리픽스를 만들어 반환.
    """
    history = history or []
    user_text = _ensure_category_in_text(user_text, history)

    if not needs_state_update(user_text):
        return {"did_update": False}

    upd = tool_update_from_text(user_text, db=DB_DEFAULT)
    state = upd.get("state") or {}
    summary = upd.get("summary", "")
    reinput = upd.get("reinput") or []

    sys_hint = "[사전 반영 결과]\n" + (summary or "(요약없음)")
    if reinput:
        sys_hint += "\n[재입력요청]\n- " + "\n- ".join(reinput)

    user_prefix = "[변경 적용 완료] " + summary if not reinput else "[재입력요청]\n" + "\n".join(f"- {m}" for m in reinput)

    return {"did_update": True, "system_hint": sys_hint, "user_prefix": user_prefix, "state": state}

# -------- 오프라인 라우터 --------
def offline_route(user_text: str) -> str:
    out_lines = []
    try:
        if needs_state_update(user_text):
            upd = tool_update_from_text(user_text, db=DB_DEFAULT)
        else:
            upd = {"summary": build_summary_text(_fetch_state(DB_DEFAULT)), "reinput": []}

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

# -------- LLM 호출 루프 (툴콜 지원 + 선반영 보조) --------
def call_llm_with_tools(user_text: str, history: List[Dict[str,str]]) -> str:
    """
    1) 필요 시 선반영(tool_update_from_text) → system 힌트로 첨부
    2) build_messages(...)로 컨텍스트 구성
    3) tool_calls 나오면 run_tool(...) 실행 → role:tool 추가 → 재호출
    """
    # 1) 선 반영
    pre = pre_update_if_needed(user_text, history)

    # 1-1) 상태
    try:
        state = pre.get("state") or _fetch_state(DB_DEFAULT)
    except Exception:
        state = {}

    # 2) 메시지 구성
    messages = build_messages(user_text, state, recent_messages=history)
    if pre.get("did_update") and pre.get("system_hint"):
        # 선반영 결과를 LLM에 시스템 힌트로 추가
        # 보통 system, developer, user 순이므로 2번째 인덱스 정도에 삽입 (문맥에 과도하게 앞서지 않게)
        insert_at = 2 if len(messages) >= 2 else len(messages)
        messages.insert(insert_at, {"role": "system", "content": pre["system_hint"]})

    # OpenAI function tools 정의
    tool_defs = [{
        "type": "function",
        "function": {
            "name": spec["name"],
            "description": spec["description"],
            "parameters": spec["parameters"],
        }
    } for spec in TOOL_SPECS]

    chat_messages: List[Dict[str, Any]] = [{"role": m["role"], "content": m["content"]} for m in messages]

    # 최대 3회 루프
    for _ in range(3):
        resp = client.chat.completions.create(
            model=MODEL,
            messages=chat_messages,
            tools=tool_defs,
            tool_choice="auto",
            temperature=0.2,
        )
        choice = resp.choices[0]
        msg = choice.message

        # 툴 호출?
        if msg.tool_calls and len(msg.tool_calls) > 0:
            # tool_calls 포함 assistant 메시지 추가 (중요!)
            tool_calls_payload = []
            for tc in msg.tool_calls:
                tool_calls_payload.append({
                    "id": tc.id,
                    "type": tc.type,
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                })
            chat_messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": tool_calls_payload})

            # 각 툴 실행 → role:tool 메시지 추가
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
            continue

        # 최종 응답 (선반영 프리픽스 포함)
        answer = (msg.content or "").strip()
        if pre.get("did_update") and pre.get("user_prefix"):
            answer = pre["user_prefix"] + "\n" + (answer or "")
        return answer or _short_suggest()

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
        history.append({"role":"user","content":text})
        history.append({"role":"assistant","content":answer})

if __name__ == "__main__":
    if sys.version_info < (3,8):
        print("⚠️ Python 3.8+ 권장")
    main()
