# 1단계: DB 연결 및 데이터 확인 (별도 스크립트로 실행)
import psycopg2
from db import engine
import sqlalchemy as sa

def test_db_connection():
    """DB 연결 및 실제 데이터 확인"""
    try:
        print("=== DB 연결 테스트 ===")
        
        with engine.connect() as conn:
            # 각 테이블 존재 여부 및 데이터 개수 확인
            tables = ["wedding_hall", "studio", "wedding_dress", "makeup"]
            
            for table_name in tables:
                try:
                    # 테이블 존재 및 데이터 개수 확인
                    count_query = f"SELECT COUNT(*) FROM {table_name}"
                    result = conn.execute(sa.text(count_query))
                    count = result.fetchone()[0]
                    print(f"✅ {table_name}: {count}개 데이터")
                    
                    if count > 0:
                        # 샘플 데이터 1개 확인
                        sample_query = f"SELECT * FROM {table_name} LIMIT 1"
                        result = conn.execute(sa.text(sample_query))
                        columns = list(result.keys())
                        row = result.fetchone()
                        
                        print(f"   샘플 데이터: {dict(zip(columns[:5], row[:5]))}")  # 처음 5개 컬럼만
                        
                except Exception as e:
                    print(f"❌ {table_name}: 오류 - {e}")
                    
        return True
        
    except Exception as e:
        print(f"❌ DB 연결 실패: {e}")
        return False

# 실행 코드
if __name__ == "__main__":
    test_db_connection()