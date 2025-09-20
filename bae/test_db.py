from sqlalchemy import text
from db import engine, db, table_info

print(table_info())  # 필요할 때만 호출

with engine.begin() as conn:
    rows = conn.execute(text("SELECT COUNT(*) FROM public.wedding_hall")).scalar()
    print("hall count:", rows)