# run_evals.py
# 목적: Step 4-4 회귀 테스트 실행기
# 실행:
#   python run_evals.py
#   python run_evals.py --db marryroute.db --inplace   # 원본 DB 직접 테스트(권장 X)

import os, shutil, json, argparse, re, sys, sqlite3
from typing import Any, Dict, List, Optional

# 내부 함수
from tools import tool_update_from_text, tool_recommend, DB_DEFAULT
from planner_update import _fetch_state

# --- 옵션: YAML 없으면 내장 기본 케이스 사용 ---
DEFAULT_CASES = {
    "cases": [
        {
            "name": "makeup-region-particle",
            "steps": [{"say": "메이크업은 청담역이 좋아"}],
            "assert": {"budgets_has": {"category": "makeup", "notes_contains": "지역:청담역"}}
        },
        {
            "name": "studio-region-particle",
            "steps": [{"say": "스튜디오는 청담역에서 찾을래"}],
            "assert": {"budgets_has": {"category": "studio", "notes_contains": "지역:청담역"}}
        },
        {
            "name": "studio-region-replace",
            "steps": [{"say": "스튜디오는 홍대입구역"}, {"say": "스튜디오는 청담역으로"}],
            "assert": {"budgets_has": {"category": "studio", "notes_exact": "지역:청담역"}}
        },
        {
            "name": "dress-too-low",
            "steps": [{"say": "드레스 3.5"}],
            "assert": {"reinput_contains": "dress"}
        },
        {
            "name": "wedding-merge-keep-location",
            "steps": [{"say": "예식은 교대에서 할거야"}, {"say": "결혼식 10/26"}],
            "assert": {"event": {"type": "wedding", "date_like": "10/26", "location_equals": "교대"}}
        },
        {
            "name": "makeup-single-value-range",
            "steps": [{"say": "메이크업 55"}],
            "assert": {"budgets_range": {"category": "makeup", "min_min": 49, "max_max": 61}}
        },
        {
            "name": "studio-recommend",
            "steps": [{"say": "스튜디오는 청담역"}, {"recommend": {"category": "studio", "limit": 5}}],
            "assert": {"recommend_non_empty": True}
        },
        {
            "name": "hall-budget-recommend",
            "steps": [{"say": "홀 4000이하"}, {"recommend": {"category": "hall", "limit": 5}}],
            "assert": {"recommend_runs": True}
        },
    ]
}

def _load_yaml_cases(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return DEFAULT_CASES
    try:
        import yaml  # pip install pyyaml
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        # YAML 파서가 없거나 실패하면 기본 케이스로
        return DEFAULT_CASES

def _copy_db(src: str, dst: str):
    shutil.copyfile(src, dst)

def _get_budget_entry(state: Dict[str, Any], category: str) -> Optional[Dict[str, Any]]:
    for b in (state.get("budgets") or []):
        if (b.get("category") or "").lower() == category.lower():
            return b
    return None

def _fetch_event(conn: sqlite3.Connection, etype: str = "wedding") -> Optional[Dict[str, Any]]:
    row = conn.execute("SELECT type, date, time, location, budget_manwon FROM event WHERE type=? ORDER BY event_id DESC LIMIT 1", (etype,)).fetchone()
    if not row: return None
    return {"type": row[0], "date": row[1], "time": row[2], "location": row[3], "budget": row[4]}

def run_case(db_path: str, case: Dict[str, Any]) -> Dict[str, Any]:
    name = case.get("name")
    steps = case.get("steps") or []
    result: Dict[str, Any] = {"name": name, "pass": True, "details": []}

    # 각 step 실행
    for st in steps:
        if "say" in st:
            res = tool_update_from_text(st["say"], db=db_path)
            result["details"].append({"say": st["say"], "ok": res.get("ok", True), "reinput": res.get("reinput", [])})
        elif "recommend" in st:
            r = st["recommend"]; cat = r["category"]; limit = int(r.get("limit", 5))
            rec = tool_recommend(cat, limit=limit, db=db_path)
            result["details"].append({"recommend": cat, "count": len(rec.get("items", []))})
        else:
            result["details"].append({"unknown_step": st})

    # 어설션 수행
    state = _fetch_state(db_path)
    details_str = []

    def fail(msg: str):
        result["pass"] = False
        details_str.append("✗ " + msg)

    def ok(msg: str):
        details_str.append("✓ " + msg)

    # budgets_has
    bh = (case.get("assert") or {}).get("budgets_has")
    if bh:
        cat = bh["category"]
        be = _get_budget_entry(state, cat)
        if not be:
            fail(f"budgets_has: {cat} 예산 엔트리 없음")
        else:
            notes = be.get("notes") or ""
            if "notes_contains" in bh and bh["notes_contains"] not in notes:
                fail(f"notes에 '{bh['notes_contains']}' 미포함 (실제: {notes})")
            if "notes_exact" in bh and (notes.strip() != bh["notes_exact"].strip()):
                fail(f"notes 정확히 일치 실패 (기대: {bh['notes_exact']}, 실제: {notes})")

    # reinput_contains
    rc = (case.get("assert") or {}).get("reinput_contains")
    if rc:
        # 마지막 say의 reinput을 검사
        last = result["details"][-1] if result["details"] else {}
        rinp = last.get("reinput", [])
        if not any(rc in (msg or "") for msg in rinp):
            fail(f"reinput_contains: '{rc}' 포함된 재입력요청이 없음")

    # event assertion
    ea = (case.get("assert") or {}).get("event")
    if ea:
        conn = sqlite3.connect(db_path)
        try:
            ev = _fetch_event(conn, etype=ea.get("type", "wedding"))
        finally:
            conn.close()
        if not ev:
            fail("event: wedding 이벤트 없음")
        else:
            if "date_like" in ea and ea["date_like"].replace("/", "-") not in (ev.get("date") or ""):
                fail(f"event.date LIKE 실패 (기대 포함: {ea['date_like']}, 실제: {ev.get('date')})")
            if "location_equals" in ea and (ev.get("location") or "") != ea["location_equals"]:
                fail(f"event.location 일치 실패 (기대: {ea['location_equals']}, 실제: {ev.get('location')})")

    # budgets_range
    br = (case.get("assert") or {}).get("budgets_range")
    if br:
        cat = br["category"]; be = _get_budget_entry(state, cat)
        if not be:
            fail(f"budgets_range: {cat} 예산 엔트리 없음")
        else:
            lo = be.get("min_manwon"); hi = be.get("max_manwon")
            if lo is None or hi is None:
                fail(f"budgets_range: 범위값(None) (실제: lo={lo}, hi={hi})")
            else:
                if lo < br["min_min"] or hi > br["max_max"]:
                    fail(f"budgets_range: 기대 범위를 벗어남 (기대: {br['min_min']}~{br['max_max']}, 실제: {lo}~{hi})")

    # recommend_non_empty / recommend_runs
    rne = (case.get("assert") or {}).get("recommend_non_empty")
    rr  = (case.get("assert") or {}).get("recommend_runs")
    if rne or rr:
        # details에서 마지막 recommend의 count 확인
        counts = [d.get("count") for d in result["details"] if "recommend" in d]
        last_cnt = counts[-1] if counts else None
        if rne and (last_cnt is None or last_cnt <= 0):
            fail("recommend_non_empty: 추천 결과가 비어 있음")
        if rr and (last_cnt is None):
            fail("recommend_runs: recommend 호출 기록 없음")

    if result["pass"]:
        ok("모든 어설션 통과")

    result["summary"] = "\n".join(details_str)
    return result

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB_DEFAULT, help="원본 SQLite DB 경로")
    ap.add_argument("--cases", default="evals/dialog_cases.yaml", help="케이스 YAML 경로")
    ap.add_argument("--inplace", action="store_true", help="원본 DB에 직접 테스트(권장 X)")
    args = ap.parse_args()

    # 테스트용 DB 준비
    test_db = args.db
    if not args.inplace:
        base, ext = os.path.splitext(args.db)
        test_db = base + "_eval" + ext
        shutil.copyfile(args.db, test_db)

    cases = _load_yaml_cases(args.cases)
    total = 0
    passed = 0
    print(f"[RUN] DB='{test_db}', cases='{args.cases if os.path.exists(args.cases) else 'default built-in'}'")

    for case in (cases.get("cases") or []):
        total += 1
        res = run_case(test_db, case)
        status = "PASS" if res["pass"] else "FAIL"
        if res["summary"]:
            print(f"\n[{status}] {res['name']}\n{res['summary']}")
        else:
            print(f"\n[{status}] {res['name']}")
        if res["pass"]:
            passed += 1

    print(f"\n== 결과: {passed}/{total} 케이스 통과 ==")
    if not args.inplace:
        print(f"(참고) 테스트 DB 사본: {test_db}")

if __name__ == "__main__":
    if sys.version_info < (3,8):
        print("⚠️ Python 3.8+ 권장")
    main()
