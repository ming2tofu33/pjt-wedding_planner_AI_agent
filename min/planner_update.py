# 목적: 사용자의 자연어 한 문장을 파싱하여 DB(user_profile, budget_pref, event, conversation_summary)에 반영

import sqlite3, re, datetime
from typing import Dict, Any, List, Optional
from parser import parse_text

MIN_REQ_MANWON = {"hall": 100, "studio": 30, "dress": 50, "makeup": 10}

# 장소 조사 제거
_LOC_TAIL = r"(에서|으로|로|에|쪽|근처)$"
def _clean_location(loc: Optional[str]) -> Optional[str]:
    if not loc:
        return loc
    s = loc.strip()
    s = re.sub(rf"\s*{_LOC_TAIL}", "", s)
    return s.strip()

def _conn(db: str):
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    return c

# ---- 스키마 보정 ----
def _has_column(conn: sqlite3.Connection, table: str, col: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any((r[1].lower() == col.lower()) for r in rows)

def _ensure_conversation_summary(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversation_summary (
            user_id INTEGER PRIMARY KEY,
            summary TEXT,
            updated_at TEXT
        )
    """)
    if not _has_column(conn, "conversation_summary", "summary"):
        conn.execute("ALTER TABLE conversation_summary ADD COLUMN summary TEXT")
    if not _has_column(conn, "conversation_summary", "updated_at"):
        conn.execute("ALTER TABLE conversation_summary ADD COLUMN updated_at TEXT")

def _ensure_user_profile(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_profile (
            user_id INTEGER PRIMARY KEY,
            region TEXT
        )
    """)

# ---- Upsert ----
def _upsert_profile_region(conn: sqlite3.Connection, region: Optional[str]):
    if region is None: return
    _ensure_user_profile(conn)
    conn.execute("INSERT OR IGNORE INTO user_profile(user_id, region) VALUES(1, NULL)")
    conn.execute("UPDATE user_profile SET region=? WHERE user_id=1", (region,))

def _get_existing_wedding(conn: sqlite3.Connection) -> Dict[str, Optional[str]]:
    r = conn.execute("SELECT date, time, location, budget_manwon FROM event WHERE type='wedding' ORDER BY event_id DESC LIMIT 1").fetchone()
    if not r:
        return {"date": None, "time": None, "location": None, "budget": None}
    return {"date": r["date"], "time": r["time"], "location": r["location"], "budget": r["budget_manwon"]}

def _upsert_wedding_event(conn: sqlite3.Connection, ev: Dict[str, Any]):
    cur = conn.execute("SELECT event_id, date, time, location, budget_manwon FROM event WHERE type='wedding' ORDER BY event_id DESC LIMIT 1")
    row = cur.fetchone()
    incoming_date   = ev.get("date")
    incoming_time   = ev.get("time")
    incoming_loc    = _clean_location(ev.get("location"))
    incoming_budget = ev.get("budget_manwon")

    if row:
        date = incoming_date or row["date"]
        time = incoming_time or row["time"]
        loc  = incoming_loc  or row["location"]
        bud  = incoming_budget if incoming_budget is not None else row["budget_manwon"]
        conn.execute("UPDATE event SET date=?, time=?, location=?, budget_manwon=? WHERE event_id=?",
                     (date, time, loc, bud, row["event_id"]))
    else:
        conn.execute(
            "INSERT INTO event(type, title, date, time, location, budget_manwon) VALUES(?,?,?,?,?,?)",
            ("wedding", "결혼식", incoming_date, incoming_time, incoming_loc, incoming_budget)
        )

def _set_budget_pref(conn: sqlite3.Connection, cat: str, lo: Optional[int], hi: Optional[int], region_note: Optional[str]):
    # 항상 단일값 덮어쓰기 보장: "지역:청담역" 형식으로 저장
    note_val = f"지역:{_clean_location(region_note)}" if region_note else None
    r = conn.execute("SELECT 1 FROM budget_pref WHERE user_id=? AND category=?", (1, cat)).fetchone()
    if r:
        if lo is not None:
            conn.execute("UPDATE budget_pref SET min_manwon=? WHERE user_id=? AND category=?", (lo, 1, cat))
        if hi is not None:
            conn.execute("UPDATE budget_pref SET max_manwon=? WHERE user_id=? AND category=?", (hi, 1, cat))
        if region_note is not None:
            conn.execute("UPDATE budget_pref SET notes=? WHERE user_id=? AND category=?", (note_val, 1, cat))
    else:
        conn.execute(
            "INSERT INTO budget_pref(user_id, category, min_manwon, max_manwon, notes) VALUES(?,?,?,?,?)",
            (1, cat, lo, hi, note_val)
        )

def _save_summary(conn: sqlite3.Connection, text: str):
    _ensure_conversation_summary(conn)
    conn.execute("INSERT OR IGNORE INTO conversation_summary(user_id, summary, updated_at) VALUES(1, '', datetime('now'))")
    conn.execute("UPDATE conversation_summary SET summary=?, updated_at=datetime('now') WHERE user_id=1", (text,))

def _year_for_mmdd(mm: int, dd: int, keep_year: Optional[int] = None) -> int:
    if keep_year: return keep_year
    today = datetime.date.today()
    y = today.year
    try:
        d = datetime.date(y, mm, dd)
    except ValueError:
        return y
    return y if d >= today else y + 1

def _merge_event_from_parsed(conn: sqlite3.Connection, ev: Dict[str, Any]):
    ex = _get_existing_wedding(conn)
    date_in = ev.get("date")  # "YYYY-MM-DD" or "MM/DD"
    time_in = ev.get("time")
    loc_in  = ev.get("location")
    bud_in  = ev.get("budget_manwon")
    if date_in and "/" in date_in and "-" not in date_in:
        mm, dd = date_in.split("/")
        yy = None
        if ex.get("date"):
            try: yy = int(ex["date"].split("-")[0])
            except: yy = None
        year = _year_for_mmdd(int(mm), int(dd), keep_year=yy)
        date_in = f"{year}-{int(mm):02d}-{int(dd):02d}"
    _upsert_wedding_event(conn, {"date": date_in, "time": time_in, "location": loc_in, "budget_manwon": bud_in})

def _validate_budgets(collected: List[Dict[str, Any]]) -> List[str]:
    msgs: List[str] = []
    for b in collected:
        cat = b["category"]
        lo = b.get("min_manwon")
        hi = b.get("max_manwon")
        lo_chk = (lo is not None and lo < MIN_REQ_MANWON.get(cat, 0))
        hi_chk = (hi is not None and hi < MIN_REQ_MANWON.get(cat, 0))
        if lo_chk or hi_chk:
            msgs.append(f"{cat} 예산이 너무 낮아요. 다시 입력해주세요.")
    return msgs

def _apply_updates(conn: sqlite3.Connection, parsed: Dict[str, Any]) -> List[str]:
    reinputs: List[str] = []

    # 1) 일반 지역 → 프로필 기본 지역
    general_regions = parsed.get("regions") or []
    if general_regions:
        _upsert_profile_region(conn, general_regions[0])

    # 2) 카테고리 지역/예산
    cat_regions = parsed.get("category_regions") or {}
    budgets     = parsed.get("budgets") or []

    reinputs.extend(_validate_budgets(budgets))

    for cat, reg in cat_regions.items():
        _set_budget_pref(conn, cat, lo=None, hi=None, region_note=reg)

    for b in budgets:
        _set_budget_pref(conn, b["category"], b.get("min_manwon"), b.get("max_manwon"), None)

    # 3) 예식 병합
    for ev in (parsed.get("events") or []):
        if (ev.get("type") or "").lower() == "wedding":
            _merge_event_from_parsed(conn, ev)

    return reinputs

def _rows_to_budgets(rows: List[sqlite3.Row]) -> List[Dict[str, Any]]:
    out = []
    for r in rows:
        out.append({
            "category": r["category"],
            "min_manwon": r["min_manwon"],
            "max_manwon": r["max_manwon"],
            "notes": r["notes"],
        })
    return out

def _fetch_budgets(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT category, min_manwon, max_manwon, notes FROM budget_pref WHERE user_id=1 ORDER BY category"
    ).fetchall()
    return _rows_to_budgets(rows)

def _fetch_profile_region(conn: sqlite3.Connection) -> Optional[str]:
    r = conn.execute("SELECT region FROM user_profile WHERE user_id=1").fetchone()
    return r["region"] if r and r["region"] else None

def _fetch_wedding_date(conn: sqlite3.Connection) -> Optional[str]:
    r = conn.execute("SELECT date FROM event WHERE type='wedding' ORDER BY event_id DESC LIMIT 1").fetchone()
    return r["date"] if r and r["date"] else None

def _fetch_state(db: str) -> Dict[str, Any]:
    with _conn(db) as c:
        state = {
            "region": _fetch_profile_region(c),
            "budgets": _fetch_budgets(c),
            "wedding_date": _fetch_wedding_date(c),
        }
    return state

def build_summary_text(state: Dict[str, Any]) -> str:
    region = state.get("region") or "-"
    wdate  = state.get("wedding_date") or "-"
    parts = []
    for b in (state.get("budgets") or []):
        cat = b["category"]
        lo, hi = b.get("min_manwon"), b.get("max_manwon")
        notes = b.get("notes") or ""
        if lo is not None and hi is not None:
            rng = f"{lo}만원 ~ {hi}만원"
        elif lo is not None:
            rng = f"{lo}만원 이상"
        elif hi is not None:
            rng = f"최대 {hi}만원"
        else:
            rng = "-"
        parts.append(f"{cat}: {rng}" + (f" ({notes})" if notes else ""))
    budgets_str = "; ".join(parts) if parts else "-"
    return f"예식: {wdate} / 지역: {region} / 예산: {budgets_str}"

def update_from_text(db: str, text: str, dry_run: bool = False) -> Dict[str, Any]:
    parsed = parse_text(text)
    with _conn(db) as c:
        if dry_run:
            reinputs = _validate_budgets(parsed.get("budgets") or [])
            state = _fetch_state(db)
            return {"committed": state, "reinput": reinputs}
        reinputs = _apply_updates(c, parsed)
        state = _fetch_state(db)
        _save_summary(c, build_summary_text(state))
        return {"committed": state, "reinput": reinputs}
