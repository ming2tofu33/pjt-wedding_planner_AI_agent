# 목적: 업체 검색/상세 조회 (vendor.min_price 우선, 옵션 제외 fallback, 만원 단위 입출력)
import sqlite3, json, argparse, os
from typing import List, Optional, Dict, Any

EXCLUDE_FROM_MIN = ("fitting_fee", "helper", "snapphoto", "snapvideo")  # 최저가 계산에서 제외

def _conn(db_path: str):
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    return c

def _fmt_price_won_to_manwon(v: Optional[int]) -> str:
    if v is None:
        return "-"
    mw = v / 10000.0
    s = f"{mw:.1f}".rstrip("0").rstrip(".")
    return f"{s}만원"

def find_vendors(
    db_path: str,
    vtype: Optional[str] = None,
    region: Optional[str] = None,
    price_max: Optional[int] = None,   # 원 단위
    keyword: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    업체 리스트 조회:
      - min_price: vendor.min_price가 있으면 그 값, 없으면 offering에서 옵션 제외 후 계산한 MIN
    """
    # 그룹 집계에서 coalesce(v.min_price, calc_min) 사용
    base = f"""
    SELECT
        v.vendor_id, v.type, v.name, v.region,
        COALESCE(
            v.min_price,
            MIN(CASE
                    WHEN o.package_name IS NULL
                         OR LOWER(o.package_name) NOT IN ({",".join(["?"]*len(EXCLUDE_FROM_MIN))})
                    THEN o.price
                END)
        ) AS min_price,
        COUNT(o.offering_id) AS cnt_offers,
        CASE WHEN v.min_price IS NOT NULL THEN 'vendor' ELSE 'computed' END AS min_source
    FROM vendor v
    LEFT JOIN offering o ON o.vendor_id = v.vendor_id
    WHERE 1=1
    """
    params = [*EXCLUDE_FROM_MIN]

    if vtype:
        base += " AND v.type = ?"
        params.append(vtype)
    if region:
        base += " AND IFNULL(v.region,'') LIKE ?"
        params.append(f"%{region}%")
    if keyword:
        base += " AND v.name LIKE ?"
        params.append(f"%{keyword}%")

    base += " GROUP BY v.vendor_id, v.type, v.name, v.region, v.min_price"

    # 바깥에서 price_max(원) 필터 적용
    sql = f"SELECT * FROM ({base}) t"
    if price_max is not None:
        sql += " WHERE t.min_price IS NULL OR t.min_price <= ?"
        params.append(price_max)

    sql += " ORDER BY (t.min_price IS NULL), t.min_price, t.name LIMIT ?"
    params.append(limit)

    with _conn(db_path) as c:
        rows = c.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

def get_offerings(db_path: str, vendor_id: int) -> List[Dict[str, Any]]:
    sql = """
    SELECT offering_id, category, package_name, price, meta_json
    FROM offering
    WHERE vendor_id = ?
    ORDER BY (price IS NULL), price, category, package_name
    """
    with _conn(db_path) as c:
        rows = c.execute(sql, (vendor_id,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["meta_json"] = json.loads(d["meta_json"]) if d["meta_json"] else {}
            out.append(d)
        return out

# ---------------- CLI ----------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="marryroute.db", help="SQLite DB 경로 (기본: marryroute.db)")
    ap.add_argument("--type", help="업체 유형: hall|studio|dress|makeup")
    ap.add_argument("--region", help="지역 문자열 (예: 강남, 홍대)")
    ap.add_argument("--price-max", type=float, help="최저가 상한(만원, 예: 120 또는 5.5)")
    ap.add_argument("--keyword", help="업체명 키워드")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--vendor-id", type=int, help="지정 벤더 상세 보기")
    args = ap.parse_args()

    db_path = args.db
    if not os.path.exists(db_path):
        print(f"❌ DB 파일을 찾을 수 없습니다: {db_path}")
        return

    # 상세 보기
    if args.vendor_id:
        items = get_offerings(db_path, args.vendor_id)
        if not items:
            print("해당 벤더의 오퍼링이 없습니다.")
            return
        for o in items:
            print(f"[{o['category']}] {o['package_name']}: {_fmt_price_won_to_manwon(o['price'])} {o['meta_json']}")
        return

    # 리스트(추천) 보기
    price_max_won = int(round(args.price_max * 10000)) if args.price_max is not None else None
    rows = find_vendors(
        db_path=db_path,
        vtype=args.type,
        region=args.region,
        price_max=price_max_won,
        keyword=args.keyword,
        limit=args.limit,
    )
    if not rows:
        print("검색 결과가 없습니다.")
        return

    for r in rows:
        src = "표준(min_fee)" if r["min_source"] == "vendor" else "계산"
        print(
            f"#{r['vendor_id']} [{r['type']}] {r['name']} ({r.get('region') or '-'})"
            f" | 최저가: {_fmt_price_won_to_manwon(r['min_price'])} [{src}]"
            f" | 상품:{r['cnt_offers']}개"
        )

if __name__ == "__main__":
    main()
