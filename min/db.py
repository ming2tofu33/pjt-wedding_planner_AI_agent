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

# DB 객체를 나중에 초기화하기 위해 None으로 시작
db = None

def get_existing_tables():
    """데이터베이스에 존재하는 테이블 확인"""
    inspector = inspect(engine)
    return inspector.get_table_names()

def initialize_db():
    """DB 초기화 및 LangChain SQLDatabase 생성"""
    global db
    
    # 이미 초기화되었다면 기존 객체 반환
    if db is not None:
        return db
    
    try:
        # 존재하는 테이블 확인
        existing_tables = get_existing_tables()
        print(f"전체 존재하는 테이블: {existing_tables}")  # 디버깅용
        
        # 기본 테이블들
        base_tables = ["wedding_hall", "studio", "wedding_dress", "makeup"]
        include_tables = []
        
        # 기본 테이블 추가
        for table in base_tables:
            if table in existing_tables:
                include_tables.append(table)
                print(f"기본 테이블 추가: {table}")
        
        # user_schedule 테이블 추가 (명시적으로 확인)
        if "user_schedule" in existing_tables:
            include_tables.append("user_schedule")
            print(f"user_schedule 테이블 추가 성공")
        else:
            print(f"WARNING: user_schedule 테이블을 찾을 수 없습니다.")
            print(f"존재하는 테이블들: {existing_tables}")
            # user_schedule 테이블이 없어도 진행 (웨딩 관련 기능은 유지)
        
        print(f"최종 포함할 테이블: {include_tables}")
        
        # include_tables가 비어있으면 기본 테이블이라도 포함
        if not include_tables:
            print("WARNING: 포함할 테이블이 없습니다. 모든 테이블을 포함합니다.")
            include_tables = existing_tables
        
        # LangChain SQLDatabase 생성
        db = SQLDatabase.from_uri(
            URI,
            include_tables=include_tables,
            sample_rows_in_table_info=0,
        )
        
        print("DB 초기화 성공!")
        return db
        
    except Exception as e:
        print(f"DB 초기화 실패: {e}")
        print(f"오류 세부사항: {type(e).__name__}")
        return None

def get_db():
    """DB 객체를 안전하게 가져오는 함수"""
    global db
    if db is None:
        db = initialize_db()
    return db

def table_info() -> str:
    """테이블 정보 반환"""
    current_db = get_db()
    if current_db:
        return current_db.get_table_info()
    return "DB가 초기화되지 않았습니다."

if __name__ == "__main__":
    print("DB 초기화 테스트 중...")
    result_db = initialize_db()
    if result_db:
        print("DB 초기화 완료!")
        print(f"사용 가능한 테이블: {get_existing_tables()}")
    else:
        print("DB 초기화 실패!")