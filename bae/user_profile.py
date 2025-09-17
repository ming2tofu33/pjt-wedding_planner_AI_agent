import sqlite3
with sqlite3.connect("marryroute.db") as c:
    # user_id=1 없으면 생성
    c.execute("""
        INSERT INTO user_profile(user_id, name, region, contact, notes)
        SELECT 1, NULL, NULL, NULL, NULL
        WHERE NOT EXISTS (SELECT 1 FROM user_profile WHERE user_id=1)
    """)
    c.commit()
print("✅ user_profile 준비 완료")
