# 목적: Step3 메모리 레이어(프로필/예산) - SQLite
import sqlite3, argparse, os
from typing import Optional, Dict, Any, List

DB_DEFAULT = "marryroute.db"

# ---------- 내부 공통 ----------
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

# ---------- 프로필 ----------
def upsert_profile(db_path: str = DB_DEFAULT,
                   name: Optional[str] = None,
                   region: Optional[str] = None,
                   contact: Optional[str] = None,
                   notes: Optional[str] = None,
                   user_id: int = 1) -> None:
    """제공된 필드만 업데이트(나머지는 유지)"""
    _ensure_user(db_path, user_id)
    sets, params = [], []
    if name   is not None: sets.append("name=?");   params.append(name)
    if region is not None: sets.append("region=?"); params.append(region)
    if contact is not None: sets.append("contact=?"); params.append(contact)
    if notes  is not None: sets.append("notes=?");  params.append(notes)
    if not sets: return
    params.append(user_id)
    with _conn(db_path) as c:
        c.execute(f"UPDATE user_profile SET {', '.join(sets)} WHERE user_id=?", params)
        c.commit()

def get_profile(db_path: str = DB_DEFAULT, user_id: int = 1) -> Dict[str, Any]:
    _ensure_user(db_path, user_id)
    with _conn(db_path) as c:
        r = c.execute("SELECT user_id,name,region,contact,notes FROM user_profile WHERE user_id=?", (user_id,)).fetchone()
        return dict(r) if r else {}

# ---------- 카테고리 예산 ----------
# 카테고리 예시: hall|studio|dress|makeup|other ...
def set_budget_pref(db_path: str = DB_DEFAULT,
                    category: str = "",
                    min_manwon: Optional[int] = None,
                    max_manwon: Optional[int] = None,
                    locked: Optional[int] = None,
                    notes: Optional[str] = None,
                    user_id: int = 1) -> None:
    """budget_pref 업서트(만원 단위). 제공 필드만 갱신."""
    if not category:
        raise ValueError("category는 필수입니다.")
    _ensure_user(db_path, user_id)
    with _conn(db_path) as c:
        # 존재 여부 확인
        exists = c.execute(
            "SELECT budget_id FROM budget_pref WHERE user_id=? AND category=?",
            (user_id, category)
        ).fetchone()
        if not exists:
            c.execute("""
                INSERT INTO budget_pref(user_id, category, min_manwon, max_manwon, locked, notes)
                VALUES (?,?,?,?,?,?)
            """, (user_id, category, min_manwon, max_manwon, locked or 0, notes))
        else:
            sets, params = [], []
            if min_manwon is not None: sets.append("min_manwon=?"); params.append(min_manwon)
            if max_manwon is not None: sets.append("max_manwon=?"); params.append(max_manwon)
            if locked     is not None: sets.append("locked=?");     params.append(int(bool(locked)))
            if notes      is not None: sets.append("notes=?");      params.append(notes)
            if sets:
                params.extend([user_id, category])
                c.execute(f"UPDATE budget_pref SET {', '.join(sets)} WHERE user_id=? AND category=?", params)
        c.commit()

def get_budget_pref(db_path: str = DB_DEFAULT,
                    category: str = "",
                    user_id: int = 1) -> Optional[Dict[str, Any]]:
    with _conn(db_path) as c:
        r = c.execute("""
            SELECT budget_id, user_id, category, min_manwon, max_manwon, locked, notes
            FROM budget_pref WHERE user_id=? AND category=?
        """, (user_id, category)).fetchone()
        return dict(r) if r else None

def list_budget_prefs(db_path: str = DB_DEFAULT,
                      user_id: int = 1) -> List[Dict[str, Any]]:
    with _conn(db_path) as c:
        rows = c.execute("""
            SELECT budget_id, user_id, category, min_manwon, max_manwon, locked, notes
            FROM budget_pref WHERE user_id=? ORDER BY category
        """, (user_id,)).fetchall()
        return [dict(r) for r in rows]

# ---------- 간단 CLI ----------
def _fmt_manwon(v):
    if v is None: return "-"
    return f"{int(v)}만원"

def main():
    ap = argparse.ArgumentParser(description="Step3 Memory: profile & budget")
    ap.add_argument("--db", default=DB_DEFAULT, help="SQLite DB 경로 (기본: marryroute.db)")
    sub = ap.add_subparsers(dest="cmd")

    sp = sub.add_parser("profile-set")
    sp.add_argument("--name"); sp.add_argument("--region"); sp.add_argument("--contact"); sp.add_argument("--notes")

    sp = sub.add_parser("profile-show")

    sb = sub.add_parser("budget-set")
    sb.add_argument("--category", required=True)
    sb.add_argument("--min", type=int, help="최소(만원)")
    sb.add_argument("--max", type=int, help="최대(만원)")
    sb.add_argument("--locked", type=int, choices=[0,1], help="1=확정")
    sb.add_argument("--notes")

    sb = sub.add_parser("budget-list")
    sb.add_argument("--category", help="특정 카테고리만")

    args = ap.parse_args()
    db = args.db

    if args.cmd == "profile-set":
        upsert_profile(db, name=args.name, region=args.region, contact=args.contact, notes=args.notes)
        print("✅ 프로필 저장 완료")
    elif args.cmd == "profile-show":
        print(get_profile(db))
    elif args.cmd == "budget-set":
        set_budget_pref(db, category=args.category, min_manwon=args.min, max_manwon=args.max,
                        locked=args.locked, notes=args.notes)
        bp = get_budget_pref(db, category=args.category)
        print("✅ 예산 저장:", bp)
    elif args.cmd == "budget-list":
        if args.category:
            print(get_budget_pref(db, args.category))
        else:
            for r in list_budget_prefs(db):
                print(f"- {r['category']}: { _fmt_manwon(r['min_manwon']) } ~ { _fmt_manwon(r['max_manwon']) }"
                      f" (locked={r['locked']}) {('['+r['notes']+']') if r.get('notes') else ''}")
    else:
        ap.print_help()

if __name__ == "__main__":
    main()
