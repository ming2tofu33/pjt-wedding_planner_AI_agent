# 용도: schema.sql을 적용해 marryroute.db 생성/갱신
import sqlite3
from pathlib import Path

DB_PATH = "marryroute.db"
SCHEMA  = Path("schema.sql")

if not SCHEMA.exists():
    raise FileNotFoundError("schema.sql 이 폴더에 없습니다.")

with sqlite3.connect(DB_PATH) as conn:
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    conn.commit()

print("✅ 스키마 적용 완료:", DB_PATH)