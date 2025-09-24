# 목적: vendor_type + region_keyword + limit로 Postgres를 조회해 표준화된 레코드 리스트 반환
# 주의: 모든 금액은 '만원' 단위(정수)로 가정
import os
from typing import List, Dict, Any, Optional
from decimal import Decimal
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

# ---------- 유틸: 식별자 이스케이프 ----------
def _q(ident: str) -> str:
    """
    SQL 식별자 안전 감싸기. 특수문자/공백/괄호/+/슬래시 등을 포함해도 안전하게 쓰기 위해
    항상 큰따옴표로 감싼다. 내부 큰따옴표는 ""로 이스케이프.
    """
    return '"' + ident.replace('"', '""') + '"'

# ---------- 테이블 스펙 & 컬럼 매핑 ----------
# 표준 출력 필드: name, region, price_manwon, extra(선택)
SPECS = {
    "wedding_hall": {
        "table": "public.wedding_hall",
        "name_col": "conm",
        "region_col": "subway",
        "price_col": "min_fee",  # 만원
        "extra_cols": ["hall_rental_fee", "meal_expense", "num_guarantors", "season(T/F)", "peak(T/F)"],
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

# ---------- 쿼리 템플릿 ----------
SQL_TMPL = """
SELECT
  {name_q}   AS name,
  {region_q} AS region,
  CAST({price_q} AS INTEGER) AS price_manwon,
  {extra_select}
FROM {table_q}
WHERE
  (:kw IS NULL)
  OR ({region_q} ILIKE :kw_like OR {name_q} ILIKE :kw_like)
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
    [{ "name": str, "region": str|None, "price_manwon": int|None, "extra": {...}, "vendor_type": str }, ...]
    """
    if vendor_type not in SPECS:
        return []

    spec = SPECS[vendor_type]

    # 식별자 준비 (항상 큰따옴표로 감싸 안전하게)
    table_q  = spec["table"]  # 스키마.테이블은 그대로 사용하되, 컬럼은 모두 _q로 감쌈
    name_q   = _q(spec["name_col"])
    region_q = _q(spec["region_col"])
    price_q  = _q(spec["price_col"])

    # extra 컬럼들을 모두 이스케이프하고, 원래 키 이름을 그대로 alias로 노출
    extra_cols = spec.get("extra_cols", [])
    if extra_cols:
        extra_select_parts = []
        for c in extra_cols:
            cq = _q(c)
            alias = _q(c)  # 원래 키 이름으로 alias (그대로 r.get(c) 가능)
            extra_select_parts.append(f"{cq} AS {alias}")
        extra_select = ", ".join(extra_select_parts)
    else:
        # 최소 1개는 Select해야 하므로 NULL을 던짐
        extra_select = "NULL AS _no_extra"

    sql = SQL_TMPL.replace("{table_q}", table_q)\
                  .replace("{name_q}", name_q)\
                  .replace("{region_q}", region_q)\
                  .replace("{price_q}", price_q)\
                  .replace("{extra_select}", extra_select)

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
        price_val = r.get("price_manwon")
        if isinstance(price_val, Decimal):
            price_val = int(price_val)
        elif isinstance(price_val, float):
            price_val = int(price_val)

        item = {
            "name": r.get("name"),
            "region": r.get("region"),
            "price_manwon": price_val,  # 만원 단위 정수
            "extra": {},
            "vendor_type": vendor_type,
        }
        for c in extra_cols:
            item["extra"][c] = r.get(c)  # 위에서 alias를 동일한 이름으로 뒀기 때문에 그대로 접근 가능
        out.append(item)
    return out

# 개발용 테스트 함수
if __name__ == "__main__":
    try:
        results = db_query_tool("wedding_hall", "강남", 3)
        print(f"✅ 성공: {len(results)}건")
        if results:
            print(f"첫 번째 결과: {results[0]}")
    except Exception as e:
        print(f"❌ 실패: {e}")
