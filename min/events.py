# 목적: event 테이블 CRUD (날짜/시간 문자열 그대로 저장, 예산은 만원 단위)
import sqlite3, argparse
from typing import Optional, Dict, Any, List

DB_DEFAULT = "marryroute.db"

# --- 공통 ---
def _conn(db_path: str):
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    return c

def _ensure_user(db_path: str, user_id: int = 1):
    with _conn(db_path) as c:
        c.execute("""
            INSERT INTO user_profile(user_id, name, region, contact, notes)
            SELECT ?, NULL, NULL, NULL, NULL
            WHERE NOT EXISTS (SELECT 1 FROM user_profile WHERE user_id=?)
        """, (user_id, user_id))
        c.commit()

# --- Create ---
def add_event(db_path: str = DB_DEFAULT,
              type: str = "wedding",
              title: Optional[str] = None,
              date: Optional[str] = None,   # "YYYY-MM-DD"
              time: Optional[str] = None,   # "HH:MM"
              location: Optional[str] = None,
              budget_manwon: Optional[int] = None,  # 만원 단위
              memo: Optional[str] = None,
              user_id: int = 1) -> int:
    _ensure_user(db_path, user_id)
    with _conn(db_path) as c:
        cur = c.execute("""
            INSERT INTO event(user_id,type,title,date,time,location,budget_manwon,memo)
            VALUES (?,?,?,?,?,?,?,?)
        """, (user_id, type, title, date, time, location, budget_manwon, memo))
        c.commit()
        return cur.lastrowid

# --- Read ---
def list_events(db_path: str = DB_DEFAULT,
                user_id: int = 1,
                type: Optional[str] = None,
                date_from: Optional[str] = None,
                date_to: Optional[str] = None,
                limit: int = 50) -> List[Dict[str, Any]]:
    sql = "SELECT event_id,type,title,date,time,location,budget_manwon,memo FROM event WHERE user_id=?"
    params = [user_id]
    if type:
        sql += " AND type=?"; params.append(type)
    if date_from:
        sql += " AND (date IS NOT NULL AND date>=?)"; params.append(date_from)
    if date_to:
        sql += " AND (date IS NOT NULL AND date<=?)"; params.append(date_to)
    sql += " ORDER BY COALESCE(date,'9999-12-31'), COALESCE(time,'23:59') LIMIT ?"
    params.append(limit)
    with _conn(db_path) as c:
        rows = c.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

# --- Update (부분 업데이트) ---
def update_event(db_path: str = DB_DEFAULT, event_id: int = 0, **fields) -> bool:
    if not event_id: return False
    allowed = {"type","title","date","time","location","budget_manwon","memo"}
    sets, params = [], []
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"{k}=?"); params.append(v)
    if not sets: return False
    params.append(event_id)
    with _conn(db_path) as c:
        cur = c.execute(f"UPDATE event SET {', '.join(sets)} WHERE event_id=?", params)
        c.commit()
        return cur.rowcount > 0

# --- Delete ---
def delete_event(db_path: str = DB_DEFAULT, event_id: int = 0) -> bool:
    if not event_id: return False
    with _conn(db_path) as c:
        cur = c.execute("DELETE FROM event WHERE event_id=?", (event_id,))
        c.commit()
        return cur.rowcount > 0

# --- CLI ---
def _fmt(ev: Dict[str,Any]) -> str:
    b = f"{ev['budget_manwon']}만원" if ev.get("budget_manwon") is not None else "-"
    dt = ev.get("date") or "-"
    tm = ev.get("time") or "-"
    loc = ev.get("location") or "-"
    title = ev.get("title") or ""
    return f"#{ev['event_id']} [{ev['type']}] {dt} {tm} @ {loc} | 예산 {b} | {title}"

def main():
    ap = argparse.ArgumentParser(description="Step3 Events CRUD")
    ap.add_argument("--db", default=DB_DEFAULT, help="SQLite DB 경로 (기본: marryroute.db)")
    sub = ap.add_subparsers(dest="cmd")

    # add
    s = sub.add_parser("add")
    s.add_argument("--type", required=True, help="wedding|prewedding|meeting|honeymoon ...")
    s.add_argument("--title")
    s.add_argument("--date")
    s.add_argument("--time")
    s.add_argument("--location")
    s.add_argument("--budget", type=int, help="만원 단위")
    s.add_argument("--memo")

    # list
    s = sub.add_parser("list")
    s.add_argument("--type")
    s.add_argument("--from", dest="date_from")
    s.add_argument("--to", dest="date_to")
    s.add_argument("--limit", type=int, default=50)

    # update
    s = sub.add_parser("update")
    s.add_argument("--id", type=int, required=True)
    s.add_argument("--type")
    s.add_argument("--title")
    s.add_argument("--date")
    s.add_argument("--time")
    s.add_argument("--location")
    s.add_argument("--budget", type=int)
    s.add_argument("--memo")

    # delete
    s = sub.add_parser("delete")
    s.add_argument("--id", type=int, required=True)

    args = ap.parse_args()
    db = args.db

    if args.cmd == "add":
        eid = add_event(db, type=args.type, title=args.title, date=args.date, time=args.time,
                        location=args.location, budget_manwon=args.budget, memo=args.memo)
        print(f"✅ 이벤트 추가됨: #{eid}")
    elif args.cmd == "list":
        rows = list_events(db, type=args.type, date_from=args.date_from, date_to=args.date_to, limit=args.limit)
        if not rows:
            print("결과 없음"); return
        for ev in rows:
            print(_fmt(ev))
    elif args.cmd == "update":
        ok = update_event(db, args.id,
                          type=args.type, title=args.title, date=args.date, time=args.time,
                          location=args.location, budget_manwon=args.budget, memo=args.memo)
        print("✅ 업데이트됨" if ok else "⚠️ 대상 없음")
    elif args.cmd == "delete":
        ok = delete_event(db, args.id)
        print("🗑️ 삭제됨" if ok else "⚠️ 대상 없음")
    else:
        ap.print_help()

if __name__ == "__main__":
    main()