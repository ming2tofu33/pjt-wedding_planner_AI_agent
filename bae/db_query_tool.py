# 목적: vendor_type + region_keyword + limit로 Postgres를 조회해 표준화된 레코드 리스트 반환
# 주의: 모든 금액은 '만원' 단위(정수)로 가정
import os
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# ---------- 연결 ----------
def _pg_uri() -> str:
    # .env 또는 환경변수: POSTGRES_USER/POSTGRES_PASSWORD/POSTGRES_DB 사용
    user = os.getenv("POSTGRES_USER", "marryroute")
    pw   = os.getenv("POSTGRES_PASSWORD", "qwer1234")
    db   = os.getenv("POSTGRES_DB", "marryroute")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    return f"postgresql+psycopg2://{user}:{pw}@{host}:{port}/{db}"

_ENGINE: Optional[Engine] = None
def _engine() -> Engine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = create_engine(_pg_uri(), pool_pre_ping=True)
    return _ENGINE

# ---------- 테이블 스펙 & 컬럼 매핑 ----------
# 표준 출력 필드: name, region, price_manwon, extra(선택)
SPECS = {
    "wedding_hall": {
        "table": "public.wedding_hall",
        "name_col": "conm",
        "region_col": "subway",
        "price_col": "min_fee",  # 만원
        "extra_cols": ["hall_rental_fee", "meal_expense", "num_guarantors", "season", "peak"],
    },
    "studio": {
        "table": "public.studio",
        "name_col": "conm",
        "region_col": "subway",
        "price_col": "std_price",  # 만원
        "extra_cols": ["afternoon_price", "allday_price"],
    },
    "wedding_dress": {
        "table": "public.wedding_dress",
        "name_col": "conm",
        "region_col": "subway",
        "price_col": "min_fee",   # 만원
        "extra_cols": ["wedding", "photo", "wedding+photo", "fitting_fee", "helper"],
    },
    "makeup": {
        "table": "public.makeup",
        "name_col": "conm",
        "region_col": "subway",
        "price_col": "min_fee",   # 만원
        "extra_cols": ["manager(1)", "manager(2)", "vicedirector(1)", "vicedirector(2)", "director(1)", "director(2)"],
    },
}

# ---------- 쿼리 ----------
SQL_TMPL = """
SELECT
  {name_col}   AS name,
  {region_col} AS region,
  {price_col}  AS price_manwon,
  {extra_select}
FROM {table}
WHERE
  (:kw IS NULL)
  OR ({region_col} ILIKE :kw_like OR {name_col} ILIKE :kw_like)
ORDER BY
  price_manwon NULLS LAST, name
LIMIT :lim
"""

def db_query_tool(
    vendor_type: str,
    region_keyword: Optional[str],
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    표준화된 레코드 리스트 반환:
    [{ "name": str, "region": str|None, "price_manwon": int|None, "extra": {...} }, ...]
    """
    if vendor_type not in SPECS:
        return []

    spec = SPECS[vendor_type]
    extra_cols = spec["extra_cols"]
    # extra 컬럼을 JSON으로 묶기 위해 SELECT에 개별로 뽑아온 뒤, 파이썬에서 dict로 재구성
    extra_select = ", ".join(extra_cols) if extra_cols else "NULL::text AS _no_extra"

    sql = SQL_TMPL.format(
        name_col=spec["name_col"],
        region_col=spec["region_col"],
        price_col=spec["price_col"],
        extra_select=extra_select,
        table=spec["table"]
    )

    params = {
        "kw": region_keyword if region_keyword else None,
        "kw_like": f"%{region_keyword}%" if region_keyword else None,
        "lim": max(1, min(int(limit or 5), 20)),
    }

    try:
        with _engine().connect() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
    except Exception as e:
        print(f"[ERROR] DB 쿼리 실패: {e}")
        return []  # 빈 리스트 반환 (크래시 방지)

    out: List[Dict[str, Any]] = []
    for r in rows:
        item = {
            "name": r.get("name"),
            "region": r.get("region"),
            "price_manwon": r.get("price_manwon"),  # 만원 단위
            "extra": {},
            "vendor_type": vendor_type,
        }
        # extra dict 구성
        for c in extra_cols:
            item["extra"][c] = r.get(c)
        out.append(item)
    return out

# 개발용 테스트 함수
if __name__ == "__main__":
    # 빠른 테스트
    try:
        results = db_query_tool("wedding_hall", "강남", 3)
        print(f"✅ 성공: {len(results)}건")
        if results:
            print(f"첫 번째 결과: {results[0]}")
    except Exception as e:
        print(f"❌ 실패: {e}")