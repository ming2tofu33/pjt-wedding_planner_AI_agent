# 목적: 타임라인 CRUD + (이벤트 기준 자동 생성)
# 내부적으로는 DB의 milestone 테이블 사용
import sqlite3, argparse
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

DB_DEFAULT = "marryroute.db"

# --- 이벤트 기준 자동 생성 ---
DEFAULT_PLAN = [
    (-340, "웨딩홀 투어 및 예약"),
    (-300, "스드메 상담 및 계약"),
    (-250, "예복 상담"),
    (-180, "촬영드레스 셀렉, 신랑 예복 가봉"),
    (-150, "리허설 촬영"),
    (-50,  "사진 셀렉, 청첩장 제작"),
    (-35,  "본식 드레스 가봉"),
    (-30,  "예식 D-30 체크"),
    (-1,   "한복 챙기기, 준비물 최종 점검"),
    (0,    "예식 당일"),
]

# ---------- 공통 ----------
def _conn(db_path: str):
    c = sqlite3.connect(db_path); c.row_factory = sqlite3.Row
    return c

def _ensure_user(db_path: str, user_id: int = 1):
    with _conn(db_path) as c:
        c.execute("""INSERT INTO user_profile(user_id,name,region,contact,notes)
                     SELECT ?,NULL,NULL,NULL,NULL
                     WHERE NOT EXISTS(SELECT 1 FROM user_profile WHERE user_id=?)""",(user_id,user_id))
        c.commit()

def _parse_date(s: str) -> datetime: return datetime.strptime(s, "%Y-%m-%d")
def _date_str(dt: datetime) -> str:  return dt.strftime("%Y-%m-%d")

# ---------- CRUD ----------
def add_item(db: str, title: str, due_date: str, source: str="manual",
             notes: Optional[str]=None, done: int=0, user_id: int=1) -> int:
    _ensure_user(db, user_id)
    with _conn(db) as c:
        cur = c.execute("""INSERT INTO milestone(user_id,title,due_date,completed,source,notes)
                           VALUES (?,?,?,?,?,?)""",
                        (user_id, title, due_date, int(bool(done)), source, notes))
        c.commit()
        return cur.lastrowid

def list_items(db: str, user_id: int=1, date_from: Optional[str]=None,
               date_to: Optional[str]=None, done: Optional[int]=None,
               limit: int=100) -> List[Dict[str,Any]]:
    sql = "SELECT ms_id,title,due_date,completed,source,notes FROM milestone WHERE user_id=?"
    params = [user_id]
    if date_from: sql += " AND due_date>=?"; params.append(date_from)
    if date_to:   sql += " AND due_date<=?"; params.append(date_to)
    if done is not None: sql += " AND completed=?"; params.append(int(bool(done)))
    sql += " ORDER BY due_date, ms_id LIMIT ?"; params.append(limit)
    with _conn(db) as c:
        rows = c.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

def update_item(db: str, ms_id: int, **fields) -> bool:
    allowed = {"title","due_date","completed","source","notes"}
    sets, params = [], []
    for k,v in fields.items():
        if k in allowed:
            sets.append(f"{k}=?"); params.append(v)
    if not sets: return False
    params.append(ms_id)
    with _conn(db) as c:
        cur = c.execute(f"UPDATE milestone SET {', '.join(sets)} WHERE ms_id=?", params)
        c.commit()
        return cur.rowcount>0

def set_done(db: str, ms_id: int, done: int=1) -> bool:
    return update_item(db, ms_id, completed=int(bool(done)))

def delete_item(db: str, ms_id: int) -> bool:
    with _conn(db) as c:
        cur = c.execute("DELETE FROM milestone WHERE ms_id=?", (ms_id,))
        c.commit()
        return cur.rowcount>0

# ---------- 이벤트 기준 자동 생성 ----------
def _get_event_date(db: str, event_type: str="wedding", user_id: int=1) -> Optional[str]:
    with _conn(db) as c:
        r = c.execute("""SELECT date FROM event
                         WHERE user_id=? AND type=? AND date IS NOT NULL
                         ORDER BY date DESC LIMIT 1""", (user_id, event_type)).fetchone()
        return r["date"] if r and r["date"] else None

def generate_from_event(db: str, event_type: str="wedding",
                        plan: List[tuple]=DEFAULT_PLAN,
                        override_date: Optional[str]=None,
                        source: str="auto", user_id: int=1) -> List[int]:
    base_date = override_date or _get_event_date(db, event_type, user_id)
    if not base_date:
        raise ValueError("이벤트 날짜가 없습니다. --date 로 직접 지정하거나 event 테이블에 먼저 저장하세요.")
    d0 = _parse_date(base_date)
    ids = []
    for offset, title in plan:
        due = _date_str(d0 + timedelta(days=offset))
        ids.append(add_item(db, title=title, due_date=due, source=source, user_id=user_id))
    return ids

# ---------- CLI ----------
def _fmt(m: Dict[str,Any]) -> str:
    flag = "✅" if m["completed"] else "□"
    note = f" | {m['notes']}" if m.get("notes") else ""
    return f"#{m['ms_id']} {flag} {m['due_date']} — {m['title']} [{m.get('source') or '-'}]{note}"

def main():
    ap = argparse.ArgumentParser(description="Timeline CRUD & generator")
    ap.add_argument("--db", default=DB_DEFAULT, help="SQLite DB 경로(기본: marryroute.db)")
    sub = ap.add_subparsers(dest="cmd")

    # add
    s = sub.add_parser("add"); s.add_argument("--title", required=True); s.add_argument("--due", required=True)
    s.add_argument("--source", default="manual"); s.add_argument("--notes"); s.add_argument("--done", type=int, choices=[0,1])

    # list
    s = sub.add_parser("list"); s.add_argument("--from"); s.add_argument("--to")
    s.add_argument("--done", type=int, choices=[0,1]); s.add_argument("--limit", type=int, default=100)

    # done/undone
    s = sub.add_parser("done"); s.add_argument("--id", type=int, required=True)
    s = sub.add_parser("undone"); s.add_argument("--id", type=int, required=True)

    # update
    s = sub.add_parser("update"); s.add_argument("--id", type=int, required=True)
    s.add_argument("--title"); s.add_argument("--due-date"); s.add_argument("--source"); s.add_argument("--notes")
    s.add_argument("--done", type=int, choices=[0,1])

    # delete
    s = sub.add_parser("delete"); s.add_argument("--id", type=int, required=True)

    # generate from event
    s = sub.add_parser("gen"); s.add_argument("--event-type", default="wedding")
    s.add_argument("--date", help="YYYY-MM-DD (지정 시 event 조회 생략)")

    args = ap.parse_args()
    db = args.db

    if args.cmd == "add":
        mid = add_item(db, args.title, args.due, source=args.source, notes=args.notes,
                       done=(args.done or 0))
        print(f"✅ 타임라인 추가됨: #{mid}")

    elif args.cmd == "list":
        rows = list_items(db, date_from=args.__dict__.get("from"), date_to=args.to,
                          done=args.done, limit=args.limit)
        if not rows: print("결과 없음"); return
        for m in rows: print(_fmt(m))

    elif args.cmd == "done":
        print("✅ 완료 처리" if set_done(db, args.id, 1) else "⚠️ 대상 없음")

    elif args.cmd == "undone":
        print("⏪ 미완료 처리" if set_done(db, args.id, 0) else "⚠️ 대상 없음")

    elif args.cmd == "update":
        fields = {k:v for k,v in vars(args).items() if k in {"title","due_date","source","notes"} and v is not None}
        if args.done is not None: fields["completed"] = int(bool(args.done))
        print("✅ 업데이트됨" if update_item(db, args.id, **fields) else "⚠️ 대상 없음")

    elif args.cmd == "delete":
        print("🗑️ 삭제됨" if delete_item(db, args.id) else "⚠️ 대상 없음")

    elif args.cmd == "gen":
        try:
            ids = generate_from_event(db, event_type=args.event_type, override_date=args.date)
            print(f"✅ 자동 생성됨: {len(ids)}개 ({', '.join(map(str,ids))})")
        except ValueError as e:
            print(f"⚠️ {e}")
    else:
        ap.print_help()

if __name__ == "__main__":
    main()