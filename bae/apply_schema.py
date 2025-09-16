# apply_schema.py
import sqlite3
from pathlib import Path

DB_PATH = "marryroute.db"        # 생성될 DB 파일
SCHEMA = Path("schema.sql")

if not SCHEMA.exists():
    raise FileNotFoundError("schema.sql 이 폴더에 없습니다.")

with sqlite3.connect(DB_PATH) as conn:
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    conn.commit()

print("✅ marryroute.db 스키마 생성 완료")