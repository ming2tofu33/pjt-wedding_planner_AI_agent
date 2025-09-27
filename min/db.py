# db.py
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect
from langchain_community.utilities import SQLDatabase

load_dotenv()

URI = (
    "postgresql+psycopg2://"
    f"{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
    f"@{os.getenv('POSTGRES_HOST', 'localhost')}:{os.getenv('POSTGRES_PORT', '5432')}"
    f"/{os.getenv('POSTGRES_DB')}"
)

# SQLAlchemy 엔진
engine = create_engine(URI, future=True)

def create_schedule_table():
    """일정 관리 테이블 생성"""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_schedule (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(50) NOT NULL,
                title VARCHAR(200) NOT NULL,
                scheduled_date DATE,
                scheduled_time TIME,
                status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('completed', 'in_progress', 'pending', 'cancelled')),
                category VARCHAR(50) DEFAULT 'general',
                description TEXT,
                priority VARCHAR(10) DEFAULT 'medium' CHECK (priority IN ('high', 'medium', 'low')),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """))
        conn.commit()
        print("user_schedule 테이블이 생성되었습니다.")

def get_existing_tables():
    """데이터베이스에 존재하는 테이블 확인"""
    inspector = inspect(engine)
    return inspector.get_table_names()

def initialize_db():
    """DB 초기화 및 LangChain SQLDatabase 생성"""
    # 1. 일정 테이블 생성
    create_schedule_table()
    
    # 2. 존재하는 테이블 확인
    existing_tables = get_existing_tables()
    
    # 3. 기본 테이블 + 존재하는 경우에만 user_schedule 포함
    base_tables = ["wedding_hall", "studio", "wedding_dress", "makeup"]
    include_tables = []
    
    for table in base_tables:
        if table in existing_tables:
            include_tables.append(table)
    
    if "user_schedule" in existing_tables:
        include_tables.append("user_schedule")
    
    print(f"포함할 테이블: {include_tables}")
    
    # 4. LangChain SQLDatabase 생성
    return SQLDatabase.from_uri(
        URI,
        include_tables=include_tables,
        sample_rows_in_table_info=0,
    )

# DB 초기화
db = initialize_db()

def table_info() -> str:
    return db.get_table_info()

# 앱 시작시 테이블 생성
if __name__ == "__main__":
    print("DB 초기화 중...")
    db = initialize_db()
    print("DB 초기화 완료!")