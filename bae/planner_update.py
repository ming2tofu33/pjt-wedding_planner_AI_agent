# 목적: 자연어 입력 → parser.py → DB 반영(프로필/예산/이벤트 upsert) → 최신 요약 갱신
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

def _replace_region_in_notes(prev: Optional[str], new_regions: List[str]) -> Optional[str]:
    """기존 메모에서 '지역:' 파트를 새 리스트로 교체(합치지 않음). 다른 메모는 유지."""
    base = _REGION_PART_RE.sub("", (prev or "")).strip()
    region_part = f"지역:{','.join(new_regions)}" if new_regions else ""
    if base and region_part: return f"{base} | {region_part}"
    return base or region_part or None

def upsert_budget_pref(db: str, category: str,
                       min_manwon: Optional[int], max_manwon: Optional[int],
                       note_regions_replace: Optional[List[str]] = None,
                       user_id: int = 1):
    with _conn(db) as c:
        row = c.execute("SELECT budget_id, notes FROM budget_pref WHERE user_id=? AND category=?",
                        (user_id, category)).fetchone()
        if row:
            sets, params = [], []
            if min_manwon is not None: sets.append("min_manwon=?"); params.append(min_manwon)
            if max_manwon is not None: sets.append("max_manwon=?"); params.append(max_manwon)
            if note_regions_replace is not None:
                new_notes = _replace_region_in_notes(row["notes"], note_regions_replace)
                sets.append("notes=?"); params.append(new_notes)
            if sets:
                params += [user_id, category]
                c.execute(f"UPDATE budget_pref SET {', '.join(sets)} WHERE user_id=? AND category=?", params)
        else:
            notes = f"지역:{','.join(note_regions_replace)}" if note_regions_replace else None
            c.execute("""INSERT INTO budget_pref(user_id,category,min_manwon,max_manwon,locked,notes)
                         VALUES (?,?,?,?,0,?)""",
                      (user_id, category, min_manwon, max_manwon, notes))
        c.commit()

def upsert_event(db: str, ev: Dict[str, Any], user_id: int = 1) -> int:
    """
    같은 type의 기존 레코드들을 병합 후 1건 유지.
    새 필드는 우선 적용(없으면 기존 유지).
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

        # 새 입력 덮어쓰기(날짜만 들어와도 location/budget 유지)
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
        # 동일 type 나머지는 정리
        c.execute("DELETE FROM event WHERE user_id=? AND type=? AND event_id<>?", (user_id, etype, keep_id))
        c.commit()
        return keep_id

def _extract_region_from_notes(notes: Optional[str]) -> Optional[str]:
    if not notes: return None
    m = re.search(r'지역:([^|]+)', notes)
    return m.group(1).strip() if m else None

def _fmt_budget_line(cat: str, lo: Optional[int], hi: Optional[int], notes: Optional[str]) -> str:
    def _p(v): return "-" if v is None else f"{v}만원"
    if lo is None and hi is None: rng = "-"
    elif lo is not None and hi is not None: rng = f"{_p(lo)} ~ {_p(hi)}"
    elif lo is not None: rng = f"최소 {_p(lo)}"
    else: rng = f"최대 {_p(hi)}"
    reg = _extract_region_from_notes(notes)
    return f"{cat}: {rng}" + (f" (지역:{reg})" if reg else "")

def _fetch_state(db: str, user_id: int = 1) -> Dict[str, Any]:
    with _conn(db) as c:
        prof = c.execute("SELECT user_id,name,region,contact FROM user_profile WHERE user_id=?", (user_id,)).fetchone()
        budgets = c.execute("""SELECT category,min_manwon,max_manwon,locked,notes
                               FROM budget_pref WHERE user_id=? ORDER BY category""", (user_id,)).fetchall()
        wedding = c.execute("""SELECT date FROM event
                               WHERE user_id=? AND type='wedding' AND date IS NOT NULL
                               ORDER BY event_id DESC LIMIT 1""", (user_id,)).fetchone()
    return {"region": prof["region"] if prof else None,
            "budgets": [dict(r) for r in budgets],
            "wedding_date": wedding["date"] if wedding else None}

def build_summary_text(state: Dict[str, Any]) -> str:
    lines = []
    if state.get("wedding_date"): lines.append(f"예식: {state['wedding_date']}")
    if state.get("region"):       lines.append(f"지역: {state['region']}")
    if state.get("budgets"):
        lines.append("예산: " + "; ".join(
            _fmt_budget_line(b["category"], b["min_manwon"], b["max_manwon"], b.get("notes"))
            for b in state["budgets"]
        ))
    return " / ".join(lines) if lines else "요약 정보 없음"

def set_latest_summary(db: str, content: str, user_id: int = 1) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    with _conn(db) as c:
        c.execute("UPDATE conversation_summary SET latest=0 WHERE user_id=? AND latest=1", (user_id,))
        cur = c.execute("""INSERT INTO conversation_summary(user_id,latest,content,updated_at)
                           VALUES(?,1,?,?)""", (user_id, content, now))
        c.commit(); return cur.lastrowid

def update_from_text(db: str, text: str, dry_run: bool = False, user_id: int = 1) -> Dict[str, Any]:
    parsed = parse_text(text); _ensure_user(db, user_id)

    to_commit = {"region": None, "budget_updates": [], "event": None}
    # 전역 지역(문장 전반)
    regs = parsed.get("regions") or []
    if regs: to_commit["region"] = regs[0]

    # 카테고리 지역: 이번 입력에 등장한 카테고리는 '교체' 정책
    cat_regions = parsed.get("category_regions") or {}
    seen = set()
    for b in parsed.get("budgets", []):
        cat, lo, hi = b["category"], b["min_manwon"], b["max_manwon"]
        replace_regions = cat_regions.get(cat) if cat in cat_regions else None
        to_commit["budget_updates"].append({
            "category": cat, "min": lo, "max": hi,
            "regions": replace_regions  # None이면 지역 변화 없음
        })
        seen.add(cat)
    # 금액 없이 지역만 말한 카테고리도 교체 적용
    for cat, regs2 in cat_regions.items():
        if cat not in seen:
            to_commit["budget_updates"].append({
                "category": cat, "min": None, "max": None, "regions": regs2
            })

    # 이벤트
    evs = parsed.get("events") or []
    if evs: to_commit["event"] = evs[0]

    # 재입력요청
    reinput = [f"[{e.get('category','-')}] 다시 입력해주세요." for e in (parsed.get("errors") or [])]

    if dry_run:
        return {"parsed": parsed, "to_commit": to_commit, "reinput": reinput}

    if to_commit["region"]:
        upsert_region(db, to_commit["region"], user_id=user_id)
    for u in to_commit["budget_updates"]:
        upsert_budget_pref(db, u["category"], u["min"], u["max"], u["regions"], user_id=user_id)
    if to_commit["event"]:
        upsert_event(db, to_commit["event"], user_id=user_id)

    state = _fetch_state(db, user_id=user_id)
    sid = set_latest_summary(db, build_summary_text(state), user_id=user_id)
    return {"parsed": parsed, "committed": state, "summary_id": sid, "reinput": reinput}

def main():
    ap = argparse.ArgumentParser(description="Planner Update: 자연어→DB 반영 & 요약 갱신")
    ap.add_argument("--db", default=DB_DEFAULT)
    ap.add_argument("--text"); ap.add_argument("--file"); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    txt = open(a.file,"r",encoding="utf-8").read() if a.file else (a.text or "")
    if not txt.strip(): print("❌ 입력이 없습니다. --text 또는 --file 사용"); return
    res = update_from_text(a.db, txt, dry_run=a.dry_run)
    if a.dry_run: print("=== DRY RUN ===")
    print("\n[재입력요청]"); print("- 없음" if not res["reinput"] else "\n".join(f"- {m}" for m in res["reinput"]))
    print("\n[파싱결과]"); print(json.dumps(res["parsed"], ensure_ascii=False, indent=2))
    if not a.dry_run:
        print("\n[DB 반영 후 상태]"); print(json.dumps(res["committed"], ensure_ascii=False, indent=2))
        print(f"\n✅ 최신 요약 저장 완료 (summary_id={res['summary_id']})")

if __name__ == "__main__":
    main()