# 목적: LLM이 사용할 도구 래퍼 3종과 런타임 디스패처
#  - update_from_text(text)
#  - recommend(category, limit=5)
#  - catalog(category, limit=20)

from typing import Any, Dict, List, Optional
import argparse, json

from planner_update import update_from_text as _update_from_text
from planner_update import _fetch_state as _fetch_state
from planner_update import build_summary_text as _build_summary_text

from catalog_bridge import recommend as _recommend
from catalog_bridge import catalog as _catalog
from catalog_bridge import normalize_cat as _normalize_cat

DB_DEFAULT = "marryroute.db"
ALLOWED_CATS = {"dress", "makeup", "studio", "hall"}

# --- LLM Function/Tool 메타 (assistant.py에서 그대로 사용 가능) ---
TOOL_SPECS: List[Dict[str, Any]] = [
    {
        "name": "update_from_text",
        "description": "자연어 한 문장을 파싱/검증하고 DB에 반영(지역 교체/예식 병합 유지/예산 하한). 결과로 요약과 재입력요청을 돌려줌.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "사용자 입력 원문"},
                "db": {"type": "string", "description": "SQLite DB 경로", "default": DB_DEFAULT},
            },
            "required": ["text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "recommend",
        "description": "카테고리별 추천 Top-N (지역 우선 → 가격 오름차순)",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "enum": ["dress","makeup","studio","hall"],
                             "description": "카테고리 또는 한국어 별칭(드레스/메이크업/스튜디오/홀)도 허용"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 5},
                "db": {"type": "string", "description": "SQLite DB 경로", "default": DB_DEFAULT},
            },
            "required": ["category"],
            "additionalProperties": False,
        },
    },
    {
        "name": "catalog",
        "description": "카테고리 목록(최대 20·지역 우선 → 가격 오름차순)",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "enum": ["dress","makeup","studio","hall"],
                             "description": "카테고리 또는 한국어 별칭(드레스/메이크업/스튜디오/홀)도 허용"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
                "db": {"type": "string", "description": "SQLite DB 경로", "default": DB_DEFAULT},
            },
            "required": ["category"],
            "additionalProperties": False,
        },
    },
]

# --- 구현 함수들 ---

def tool_update_from_text(text: str, db: str = DB_DEFAULT) -> Dict[str, Any]:
    """자연어 상태 반영 + 요약 반환 (재입력요청 포함)"""
    res = _update_from_text(db, text, dry_run=False)
    state = res.get("committed") or _fetch_state(db)
    return {
        "ok": True,
        "reinput": res.get("reinput") or [],
        "summary": _build_summary_text(state),
        "state": state,
    }

def _norm_cat(cat_token: str) -> str:
    cat = (_normalize_cat(cat_token) or (cat_token or "").lower())
    if cat not in ALLOWED_CATS:
        raise ValueError(f"지원하지 않는 카테고리: {cat_token}")
    return cat

def tool_recommend(category: str, limit: int = 5, db: str = DB_DEFAULT) -> Dict[str, Any]:
    """추천 Top-N (지역 우선 → 가격 오름차순)"""
    cat = _norm_cat(category)
    rows = _recommend(db, cat, limit=limit)
    return {"ok": True, "category": cat, "items": rows}

def tool_catalog(category: str, limit: int = 20, db: str = DB_DEFAULT) -> Dict[str, Any]:
    """목록(지역 우선 → 가격 오름차순)"""
    cat = _norm_cat(category)
    rows = _catalog(db, cat, limit=limit)
    return {"ok": True, "category": cat, "items": rows}

# --- 런타임 디스패처 (assistant.py에서 공용) ---

def run_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """이름/인자(dict)로 도구 실행 → dict 결과 반환 (에러는 메시지로 래핑)"""
    try:
        if name == "update_from_text":
            return tool_update_from_text(text=args["text"], db=args.get("db", DB_DEFAULT))
        elif name == "recommend":
            return tool_recommend(category=args["category"], limit=args.get("limit", 5), db=args.get("db", DB_DEFAULT))
        elif name == "catalog":
            return tool_catalog(category=args["category"], limit=args.get("limit", 20), db=args.get("db", DB_DEFAULT))
        else:
            return {"ok": False, "error": f"Unknown tool: {name}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# --- CLI 점검용 ---
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="MarryRoute Tools (CLI)")
    sub = ap.add_subparsers(dest="cmd")

    p1 = sub.add_parser("update", help="자연어 반영")
    p1.add_argument("--text", required=True)
    p1.add_argument("--db", default=DB_DEFAULT)

    p2 = sub.add_parser("recommend", help="추천 Top-N")
    p2.add_argument("--cat", required=True)
    p2.add_argument("--limit", type=int, default=5)
    p2.add_argument("--db", default=DB_DEFAULT)

    p3 = sub.add_parser("catalog", help="목록 조회")
    p3.add_argument("--cat", required=True)
    p3.add_argument("--limit", type=int, default=20)
    p3.add_argument("--db", default=DB_DEFAULT)

    args = ap.parse_args()
    if args.cmd == "update":
        print(json.dumps(tool_update_from_text(args.text, db=args.db), ensure_ascii=False, indent=2))
    elif args.cmd == "recommend":
        print(json.dumps(tool_recommend(args.cat, limit=args.limit, db=args.db), ensure_ascii=False, indent=2))
    elif args.cmd == "catalog":
        print(json.dumps(tool_catalog(args.cat, limit=args.limit, db=args.db), ensure_ascii=False, indent=2))
    else:
        ap.print_help()
