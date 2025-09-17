# 목적: 대화 요약 저장/조회(최신본 latest=1 보장) + 히스토리 관리
import sqlite3, argparse, sys
from datetime import datetime
from typing import Dict, Any, List, Optional

DB_DEFAULT = "marryroute.db"

def _conn(db_path: str):
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    return c

def _ensure_user(db_path: str, user_id: int = 1):
    with _conn(db_path) as c:
        c.execute("""INSERT INTO user_profile(user_id,name,region,contact,notes)
                     SELECT ?,NULL,NULL,NULL,NULL
                     WHERE NOT EXISTS(SELECT 1 FROM user_profile WHERE user_id=?)""",
                  (user_id, user_id))
        c.commit()

# ---------- Core ----------
def set_summary(db_path: str, content: str, user_id: int = 1) -> int:
    """이전 latest=0으로 내리고, 새 요약을 latest=1로 추가"""
    _ensure_user(db_path, user_id)
    now = datetime.now().isoformat(timespec="seconds")
    with _conn(db_path) as c:
        c.execute("UPDATE conversation_summary SET latest=0 WHERE user_id=? AND latest=1", (user_id,))
        cur = c.execute("""INSERT INTO conversation_summary(user_id, latest, content, updated_at)
                           VALUES(?, 1, ?, ?)""", (user_id, content, now))
        c.commit()
        return cur.lastrowid

def get_latest_summary(db_path: str, user_id: int = 1) -> Optional[Dict[str, Any]]:
    with _conn(db_path) as c:
        r = c.execute("""SELECT summary_id,content,updated_at
                         FROM conversation_summary
                         WHERE user_id=? AND latest=1
                         ORDER BY summary_id DESC LIMIT 1""", (user_id,)).fetchone()
        return dict(r) if r else None

def list_summaries(db_path: str, limit: int = 20, user_id: int = 1) -> List[Dict[str, Any]]:
    with _conn(db_path) as c:
        rows = c.execute("""SELECT summary_id, latest, updated_at, substr(content,1,80)||CASE WHEN length(content)>80 THEN '…' ELSE '' END AS preview
                            FROM conversation_summary
                            WHERE user_id=?
                            ORDER BY summary_id DESC LIMIT ?""", (user_id, limit)).fetchall()
        return [dict(r) for r in rows]

def promote_summary(db_path: str, summary_id: int, user_id: int = 1) -> bool:
    """지정한 요약을 최신본으로 승격"""
    with _conn(db_path) as c:
        exists = c.execute("SELECT 1 FROM conversation_summary WHERE summary_id=? AND user_id=?", (summary_id, user_id)).fetchone()
        if not exists: return False
        c.execute("UPDATE conversation_summary SET latest=0 WHERE user_id=?", (user_id,))
        c.execute("UPDATE conversation_summary SET latest=1 WHERE summary_id=? AND user_id=?", (summary_id, user_id))
        c.commit()
        return True

def delete_summary(db_path: str, summary_id: int, user_id: int = 1) -> bool:
    with _conn(db_path) as c:
        cur = c.execute("DELETE FROM conversation_summary WHERE summary_id=? AND user_id=?", (summary_id, user_id))
        c.commit()
        return cur.rowcount > 0

# ---------- CLI ----------
def main():
    ap = argparse.ArgumentParser(description="Conversation summary CRUD")
    ap.add_argument("--db", default=DB_DEFAULT, help="SQLite DB 경로(기본: marryroute.db)")
    sub = ap.add_subparsers(dest="cmd")

    s = sub.add_parser("set", help="새 요약 저장(최신본으로)")
    s.add_argument("--content", help="요약 본문")
    s.add_argument("--file", help="요약을 파일에서 읽기")

    sub.add_parser("latest", help="최신 요약 보기")

    s = sub.add_parser("list", help="요약 히스토리")
    s.add_argument("--limit", type=int, default=20)

    s = sub.add_parser("promote", help="지정 ID를 최신본으로")
    s.add_argument("--id", type=int, required=True)

    s = sub.add_parser("delete", help="지정 ID 삭제")
    s.add_argument("--id", type=int, required=True)

    args = ap.parse_args()
    db = args.db

    if args.cmd == "set":
        if args.file:
            content = open(args.file, "r", encoding="utf-8").read()
        else:
            content = args.content or sys.stdin.read()
        sid = set_summary(db, content)
        print(f"✅ 저장됨: summary_id={sid}")
    elif args.cmd == "latest":
        r = get_latest_summary(db)
        if not r: print("요약 없음"); return
        print(f"# {r['summary_id']} | {r['updated_at']}\n{r['content']}")
    elif args.cmd == "list":
        for row in list_summaries(db, args.limit):
            flag = "★" if row["latest"] else " "
            print(f"{flag} #{row['summary_id']} | {row['updated_at']} | {row['preview']}")
    elif args.cmd == "promote":
        ok = promote_summary(db, args.id)
        print("✅ 최신본으로 승격" if ok else "⚠️ 대상 없음")
    elif args.cmd == "delete":
        ok = delete_summary(db, args.id)
        print("🗑️ 삭제됨" if ok else "⚠️ 대상 없음")
    else:
        ap.print_help()

if __name__ == "__main__":
    main()
