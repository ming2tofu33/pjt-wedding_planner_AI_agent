# 목적: vendor × offering 스키마에서 카테고리별 추천/목록 조회
# - 지역 우선 → 가격 오름차순(NULL 뒤)
# - 컬럼 자동 매핑(없으면 생략하여도 쿼리 동작)
import sqlite3, re
from typing import Optional, Dict, Any, List, Tuple

DB_DEFAULT = "marryroute.db"

def _conn(db: str):
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    return c

# ---------- 스키마 탐색 ----------
def _tables(c: sqlite3.Connection) -> List[str]:
    rows = c.execute("SELECT lower(name) AS name FROM sqlite_master WHERE type='table'").fetchall()
    return [r["name"] for r in rows]

def _vendor_cols(c: sqlite3.Connection) -> Dict[str, Optional[str]]:
    cols = [r["name"].lower() for r in c.execute("PRAGMA table_info(vendor)")]
    if not cols:
        raise RuntimeError("vendor 테이블의 컬럼 정보를 가져올 수 없습니다.")
    def first(*cands):
        for x in cands:
            if x in cols:
                return x
        return None
    vid     = first("vendor_id", "id", "vid") or cols[0]
    name    = first("conm", "name", "title", "vendor", "brand", "company", "shop") or (cols[1] if len(cols)>1 else cols[0])
    region  = first("subway", "region", "area", "location", "district", "addr", "address") or (cols[2] if len(cols)>2 else cols[0])
    vcat    = first("category", "cat", "type")  # 없으면 None (=> offering.category 사용 시도)
    return {"id": vid, "name": name, "region": region, "category": vcat}

def _offering_cols(c: sqlite3.Connection) -> Dict[str, Optional[str]]:
    cols = [r["name"].lower() for r in c.execute("PRAGMA table_info(offering)")]
    if not cols:
        raise RuntimeError("offering 테이블의 컬럼 정보를 가져올 수 없습니다.")
    def first(*cands):
        for x in cands:
            if x in cols:
                return x
        return None
    vref   = first("vendor_id", "vid", "vendor") or "vendor_id"
    price  = first("min_price", "price_min", "lowest", "min", "low_price", "start_price")  # 없으면 None
    item   = first("item", "name", "option", "title")  # 표시용(없어도 됨)
    ocat   = first("category", "cat", "type")  # 없으면 None
    return {"vref": vref, "min_price": price, "item": item, "category": ocat}

# ---------- 선호(예산/지역) ----------
def _get_budget(c: sqlite3.Connection, cat: str) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    r = c.execute(
        "SELECT min_manwon,max_manwon,notes FROM budget_pref WHERE user_id=? AND category=?",
        (1, cat)
    ).fetchone()
    if not r:
        return None, None, None
    notes = r["notes"] or ""
    m = re.search(r"지역:([^|]+)", notes)
    region_hint = m.group(1).split(",")[0].strip() if m else None
    return r["min_manwon"], r["max_manwon"], region_hint

def _get_profile_region(c: sqlite3.Connection) -> Optional[str]:
    r = c.execute("SELECT region FROM user_profile WHERE user_id=1").fetchone()
    return r["region"] if r and r["region"] else None

def _pick_region_hint(c: sqlite3.Connection, cat: str) -> Optional[str]:
    lo, hi, r = _get_budget(c, cat)
    return r or _get_profile_region(c)

# ---------- 카테고리 정규화(영/한) ----------
CAT_ALIASES = {
    "dress":  ["dress", "드레스", "본식드레스", "촬영드레스"],
    "makeup": ["makeup", "메이크업", "메컵", "헤어", "헤메"],
    "studio": ["studio", "스튜디오", "촬영", "리허설", "스냅"],
    "hall":   ["hall", "웨딩홀", "홀", "예식홀", "결혼식장", "예식장"],
}
def normalize_cat(token: str) -> Optional[str]:
    t = token.lower()
    for k, arr in CAT_ALIASES.items():
        if any(t == a.lower() for a in arr):
            return k
    return None

# ---------- 쿼리 빌더 ----------
def _order_clause(v_region_col: str, price_alias: Optional[str], region_hint: Optional[str]) -> Tuple[str, List[Any]]:
    params: List[Any] = []
    parts: List[str] = []
    if region_hint:
        parts.append(f"(CASE WHEN {v_region_col} LIKE ? THEN 1 ELSE 0 END) DESC")
        params.append(f"%{region_hint}%")
    if price_alias:
        parts.append(f"CASE WHEN {price_alias} IS NULL THEN 1 ELSE 0 END")
        parts.append(f"{price_alias} ASC")
    return (" ORDER BY " + ", ".join(parts)) if parts else "", params

def _price_where(min_price_col: Optional[str], lo: Optional[int], hi: Optional[int]) -> Tuple[str, List[Any]]:
    if not min_price_col:
        return "", []
    where, params = [], []
    if lo is not None and hi is not None:
        where.append(f"o.{min_price_col} IS NOT NULL AND o.{min_price_col}>=? AND o.{min_price_col}<=?")
        params += [lo, hi]
    elif lo is not None:
        where.append(f"o.{min_price_col} IS NOT NULL AND o.{min_price_col}>=?")
        params += [lo]
    elif hi is not None:
        where.append(f"o.{min_price_col} IS NOT NULL AND o.{min_price_col}<=?")
        params += [hi]
    return (" AND " + " AND ".join(where)) if where else "", params

def _category_condition(vcat: Optional[str], ocat: Optional[str]) -> Tuple[str, List[Any]]:
    """vendor.category 또는 offering.category 중 존재하는 쪽으로 필터"""
    if vcat:
        return f" AND LOWER(v.{vcat}) = ?", []
    if ocat:
        return f" AND LOWER(o.{ocat}) = ?", []
    return "", []

# ---------- 퍼블릭 API ----------
def recommend(db: str, cat_token: str, limit: int = 5) -> List[Dict[str, Any]]:
    with _conn(db) as c:
        tabs = _tables(c)
        if "vendor" not in tabs or "offering" not in tabs:
            raise RuntimeError(f"vendor/offering 테이블이 필요합니다. (보유 테이블: {tabs})")

        cat_key = (normalize_cat(cat_token) or cat_token or "").lower()
        v = _vendor_cols(c)
        o = _offering_cols(c)

        lo, hi, _ = _get_budget(c, cat_key)
        region_hint = _pick_region_hint(c, cat_key)

        price_and, pparams = _price_where(o["min_price"], lo, hi)
        cat_and, _ = _category_condition(v["category"], o["category"])

        # price 컬럼이 없으면 SELECT에서 NULL 별칭 사용
        price_select = f"MIN(o.{o['min_price']}) AS min_price" if o["min_price"] else "NULL AS min_price"
        price_alias = "min_price" if o["min_price"] else None

        sql = f"""
        SELECT
            v.{v['id']}     AS id,
            v.{v['name']}   AS name,
            v.{v['region']} AS region,
            {price_select}
        FROM vendor v
        LEFT JOIN offering o ON o.{o['vref']} = v.{v['id']}
        WHERE 1=1
        """

        params: List[Any] = []
        if cat_and:
            sql += cat_and
            params.append(cat_key)

        if price_and:
            sql += price_and
            params += pparams

        sql += f" GROUP BY v.{v['id']}, v.{v['name']}, v.{v['region']}"

        order, oparams = _order_clause(f"v.{v['region']}", price_alias, region_hint)
        sql += order + " LIMIT ?"
        params += oparams + [limit]

        rows = c.execute(sql, params).fetchall()
        return [{
            "id": r["id"],
            "name": r["name"],
            "region": r["region"],
            "min_price": r["min_price"],
        } for r in rows]

def catalog(db: str, cat_token: str, limit: int = 20) -> List[Dict[str, Any]]:
    return recommend(db, cat_token, limit=limit)
