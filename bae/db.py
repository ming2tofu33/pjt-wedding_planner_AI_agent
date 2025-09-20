# db.py  — super minimal
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from langchain_community.utilities import SQLDatabase

load_dotenv()

URI = (
    "postgresql+psycopg2://"
    f"{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
    f"@{os.getenv('POSTGRES_HOST', 'localhost')}:{os.getenv('POSTGRES_PORT', '5432')}"
    f"/{os.getenv('POSTGRES_DB')}"
)

# SQLAlchemy 엔진 (일반 쿼리용)
engine = create_engine(URI, future=True)

# LangChain용 래퍼 (우리가 쓸 4개 테이블만 스캔 → 초기화 빠름)
db = SQLDatabase.from_uri(
    URI,
    include_tables=["wedding_hall", "studio", "wedding_dress", "makeup"],
    sample_rows_in_table_info=0,
)

# 테이블 스키마 요약 문자열(LLM 프롬프트 등에 필요할 때)
def table_info() -> str:
    return db.get_table_info()
