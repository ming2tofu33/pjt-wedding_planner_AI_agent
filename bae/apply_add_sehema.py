# add_schema.sql을 실행해서 marryroute.db에 테이블 추가
import sqlite3, argparse
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--db", default="marryroute.db", help="SQLite DB 경로")
ap.add_argument("--sql", default="add_schema.sql", help="DDL SQL 파일 경로")
args = ap.parse_args()

sql_path = Path(args.sql)
if not sql_path.exists():
    raise FileNotFoundError(sql_path)

with sqlite3.connect(args.db) as conn:
    conn.executescript(sql_path.read_text(encoding="utf-8"))
    conn.commit()

print(f"✅ Step3 스키마 적용 완료 | DB={args.db} | SQL={args.sql}")
