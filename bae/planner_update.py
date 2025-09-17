# 목적: 자연어 입력 → parser.py → DB 반영(프로필/예산/이벤트 upsert) → 최신 요약 갱신
# planner_update.py
import argparse, sqlite3, json, re
from datetime import datetime
from typing import Dict, Any, List, Optional
from parser import parse_text

DB_DEFAULT = "marryroute.db"

def _conn(db_path: str):
    c = sqlite3.connect(db_path); c.row_factory = sqlite3.Row
    return c

def _ensure_user(db: str, user_id: int = 1):
    with _conn(db) as c:
        c.execute("""INSERT INTO user_profile(user_id,name,region,contact,notes)
                     SELECT ?,NULL,NULL,NULL,NULL
                     WHERE NOT EXISTS(SELECT 1 FROM user_profile WHERE user_id=?)""",(user_id,user_id))
        c.commit()

def upsert_region(db: str, region: Optional[str], user_id: int = 1):
    if not region: return
    with _conn(db) as c:
        c.execute("UPDATE user_profile SET region=? WHERE user_id=?", (region, user_id)); c.commit()

_REGION_PART_RE = re.compile(r' ?\|? ?지역:[^|]+')

def _normalize_regions(lst: List[str]) -> List[str]:
    # 중복 제거 + 접두 중복 제거(예: '압구'는 '압구정역'이 있으면 제거)
    uniq = []
    for r in lst:
        if r not in uniq: uniq.append(r)
    filtered = []
    for r in uniq:
        if any((r != o and o.startswith(r)) for o in uniq):
            continue
        filtered.append(r)
    return filtered

def _merge_notes(prev: Optional[str], note_append: Optional[str]) -> Optional[str]:
    if not prev and not note_append: return None
    prev = (prev or "").strip()
    note_append = (note_append or "").strip()

    def _regions(s: str) -> List[str]:
        m = re.search(r'지역:([^|]+)', s)
        if not m: return []
        toks = [t.strip() for t in m.group(1).split(",") if t.strip()]
        return toks

    regions = _regions(prev) + _regions(note_append)
    regions = _normalize_regions(regions)

    base = _REGION_PART_RE.sub("", prev).strip()
    region_part = f"지역:{','.join(regions)}" if regions else ""
    if base and region_part: return f"{base} | {region_part}"
    return base or region_part or None

def upsert_budget_pref(db: str, category: str,
                       min_manwon: Optional[int], max_manwon: Optional[int],
                       note_append: Optional[str] = None,
                       user_id: int = 1):
    with _conn(db) as c:
        row = c.execute("SELECT budget_id, notes FROM budget_pref WHERE user_id=? AND category=?",
                        (user_id, category)).fetchone()
        if row:
            sets, params = [], []
            if min_manwon is not None: sets.append("min_manwon=?"); params.append(min_manwon)
            if max_manwon is not None: sets.append("max_manwon=?"); params.append(max_manwon)
            if note_append is not None:
                merged = _merge_notes(row["notes"], note_append)
                sets.append("notes=?"); params.append(merged)
            if sets:
                params += [user_id, category]
                c.execute(f"UPDATE budget_pref SET {', '.join(sets)} WHERE user_id=? AND category=?", params)
        else:
            c.execute("""INSERT INTO budget_pref(user_id,category,min_manwon,max_manwon,locked,notes)
                         VALUES (?,?,?,?,0,?)""",
                      (user_id, category, min_manwon, max_manwon, note_append))
        c.commit()

def upsert_event(db: str, ev: Dict[str, Any], user_id: int = 1) -> int:
    """
    같은 type의 기존 레코드들을 병합 후 1건으로 유지.
    새 입력 필드가 있으면 그 값으로 덮어쓰기(우선 적용).
    """
    if not ev or not ev.get("type"): return 0
    etype = ev.get("type")
    new_fields = {k: ev.get(k) for k in ("title","date","time","location","budget_manwon") if ev.get(k) is not None}

    with _conn(db) as c:
        rows = c.execute("""SELECT event_id,title,date,time,location,budget_manwon
                            FROM event WHERE user_id=? AND type=? ORDER BY event_id ASC""",
                         (user_id, etype)).fetchall()

        merged = {k: None for k in ("title","date","time","location","budget_manwon")}
        keep_id = rows[0]["event_id"] if rows else None

        # 기존 값 병합(앞에서부터 첫 non-null 채택)
        for r in rows:
            for k in merged.keys():
                if merged[k] is None and r[k] is not None:
                    merged[k] = r[k]

        # 새 입력 덮어쓰기
        for k, v in new_fields.items():
            merged[k] = v

        if keep_id is None:
            c.execute("""INSERT INTO event(user_id,type,title,date,time,location,budget_manwon,memo)
                         VALUES (?,?,?,?,?,?,?,?)""",
                      (user_id, etype, merged["title"], merged["date"], merged["time"],
                       merged["location"], merged["budget_manwon"], None))
            keep_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        else:
            sets = [f"{k}=?" for k in merged.keys()]
            params = [merged[k] for k in merged.keys()] + [keep_id]
            c.execute(f"UPDATE event SET {', '.join(sets)} WHERE event_id=?", params)

        # 무조건 동일 type 나머지 정리(1건만 유지)
        c.execute("DELETE FROM event WHERE user_id=? AND type=? AND event_id<>?",
                  (user_id, etype, keep_id))
        c.commit()
        return keep_id

def _extract_region_from_notes(notes: Optional[str]) -> Optional[str]:
    if not notes: return None
    m = re.search(r'지역:([^|]+)', notes)
    return m.group(1).strip() if m else None

def _fmt_budget_line(cat: str, lo: Optional[int], hi: Optional[int], notes: Optional[str]) -> str:
    def _p(v): return "-" if v is None else f"{v}만원"
    if lo is None and hi is None: range_txt = "-"
    elif lo is not None and hi is not None: range_txt = f"{_p(lo)} ~ {_p(hi)}"
    elif lo is not None: range_txt = f"최소 {_p(lo)}"
    else: range_txt = f"최대 {_p(hi)}"
    reg = _extract_region_from_notes(notes)
    return f"{cat}: {range_txt}" + (f" (지역:{reg})" if reg else "")

def _fetch_state(db: str, user_id: int = 1) -> Dict[str, Any]:
    with _conn(db) as c:
        prof = c.execute("SELECT user_id,name,region,contact FROM user_profile WHERE user_id=?", (user_id,)).fetchone()
        budgets = c.execute("""SELECT category,min_manwon,max_manwon,locked,notes
                               FROM budget_pref WHERE user_id=? ORDER BY category""", (user_id,)).fetchall()
        wedding = c.execute("""SELECT date FROM event
                               WHERE user_id=? AND type='wedding' AND date IS NOT NULL
                               ORDER BY event_id DESC LIMIT 1""", (user_id,)).fetchone()
    return {
        "region": prof["region"] if prof else None,
        "budgets": [dict(r) for r in budgets],
        "wedding_date": wedding["date"] if wedding else None
    }

def build_summary_text(state: Dict[str, Any]) -> str:
    lines = []
    if state.get("wedding_date"): lines.append(f"예식: {state['wedding_date']}")
    if state.get("region"):       lines.append(f"지역: {state['region']}")
    if state.get("budgets"):
        blines = [_fmt_budget_line(b["category"], b["min_manwon"], b["max_manwon"], b.get("notes"))
                  for b in state["budgets"]]
        lines.append("예산: " + "; ".join(blines))
    return " / ".join(lines) if lines else "요약 정보 없음"

def set_latest_summary(db: str, content: str, user_id: int = 1) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    with _conn(db) as c:
        c.execute("UPDATE conversation_summary SET latest=0 WHERE user_id=? AND latest=1", (user_id,))
        cur = c.execute("""INSERT INTO conversation_summary(user_id,latest,content,updated_at)
                           VALUES(?,1,?,?)""", (user_id, content, now))
        c.commit()
        return cur.lastrowid

def update_from_text(db: str, text: str, dry_run: bool = False, user_id: int = 1) -> Dict[str, Any]:
    _ensure_user(db, user_id)
    parsed = parse_text(text)
    to_commit = {"region": None, "budget_updates": [], "event": None}

    regions = parsed.get("regions") or []
    if regions: to_commit["region"] = regions[0]

    cat_regions = parsed.get("category_regions") or {}
    updated_cats = set()
    for b in parsed.get("budgets", []):
        cat, lo, hi = b["category"], b["min_manwon"], b["max_manwon"]
        note = f"지역:{','.join(cat_regions[cat])}" if cat in cat_regions and cat_regions[cat] else None
        to_commit["budget_updates"].append({"category": cat, "min": lo, "max": hi, "notes": note})
        updated_cats.add(cat)
    for cat, regs in cat_regions.items():
        if regs and cat not in updated_cats:
            note = f"지역:{','.join(regs)}"
            to_commit["budget_updates"].append({"category": cat, "min": None, "max": None, "notes": note})

    events = parsed.get("events") or []
    if events: to_commit["event"] = events[0]

    errors = parsed.get("errors") or []
    reinput = [f"[{e.get('category','-')}] 다시 입력해주세요." for e in errors]

    if dry_run:
        return {"parsed": parsed, "to_commit": to_commit, "reinput": reinput}

    if to_commit["region"]:
        upsert_region(db, to_commit["region"], user_id=user_id)
    for u in to_commit["budget_updates"]:
        upsert_budget_pref(db, u["category"], u["min"], u["max"], u["notes"], user_id=user_id)
    if to_commit["event"]:
        upsert_event(db, to_commit["event"], user_id=user_id)

    state = _fetch_state(db, user_id=user_id)
    sid = set_latest_summary(db, build_summary_text(state), user_id=user_id)
    return {"parsed": parsed, "committed": state, "summary_id": sid, "reinput": reinput}

def main():
    ap = argparse.ArgumentParser(description="Planner Update: 자연어→DB 반영 & 요약 갱신")
    ap.add_argument("--db", default=DB_DEFAULT)
    ap.add_argument("--text"); ap.add_argument("--file"); ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    text = open(args.file,"r",encoding="utf-8").read() if args.file else (args.text or "")
    if not text.strip():
        print("❌ 입력이 없습니다. --text 또는 --file 사용"); return
    result = update_from_text(args.db, text, dry_run=args.dry_run)
    if args.dry_run: print("=== DRY RUN ===")
    print("\n[재입력요청]")
    if result["reinput"]: [print("-", msg) for msg in result["reinput"]]
    else: print("- 없음")
    print("\n[파싱결과]"); print(json.dumps(result["parsed"], ensure_ascii=False, indent=2))
    if not args.dry_run:
        print("\n[DB 반영 후 상태]"); print(json.dumps(result["committed"], ensure_ascii=False, indent=2))
        print(f"\n✅ 최신 요약 저장 완료 (summary_id={result['summary_id']})")

if __name__ == "__main__":
    main()
