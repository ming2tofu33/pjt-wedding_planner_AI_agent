# 용도: CSV들을 읽어 SQLite(marryroute.db)에 적재 + vendor.min_price 반영
import pandas as pd
import sqlite3, json, argparse, re, os
from pathlib import Path

EXCLUDE_FOR_MIN = {"fitting_fee","helper","snapphoto","snapvideo"}  # 옵션

# --- 숫자/스케일/컬럼 유틸 ---
def to_number(v):
    if pd.isna(v): return None
    s = str(v).strip().replace(",", "")
    if s in ("", "-"): return None
    m = re.findall(r"[0-9]+(?:\.[0-9]+)?", s)  # 소수 포함
    return float(m[0]) if m else None

def decide_scale(series):
    vals = [to_number(x) for x in series if not pd.isna(x)]
    vals = [v for v in vals if v is not None]
    if not vals: return 1
    vals.sort()
    med = vals[len(vals)//2]
    return 10000 if med < 500 else 1  # 중앙값<500 => '만원'으로 보고 원 환산

def pick_col(columns, candidates):
    low = {str(c).strip().lower(): c for c in columns}
    for key in candidates:
        if key in low: return low[key]
    return None

# --- DB 도우미 ---
def upsert_vendor(conn, vtype, name, region=None, min_price=None, notes=None):
    cur = conn.execute("SELECT vendor_id FROM vendor WHERE type=? AND name=?", (vtype, name))
    row = cur.fetchone()
    if row:
        vid = row[0]
        conn.execute(
            "UPDATE vendor SET region=COALESCE(?,region), min_price=COALESCE(?,min_price), notes=COALESCE(?,notes) WHERE vendor_id=?",
            (region, min_price, notes, vid)
        )
        return vid
    cur = conn.execute(
        "INSERT INTO vendor(type,name,region,min_price,notes) VALUES (?,?,?,?,?)",
        (vtype, name, region, min_price, notes)
    )
    return cur.lastrowid

def insert_offering(conn, vendor_id, category, package_name, price, meta=None):
    conn.execute(
        "INSERT INTO offering(vendor_id,category,package_name,price,meta_json) VALUES (?,?,?,?,?)",
        (vendor_id, category, package_name, price, json.dumps(meta or {}, ensure_ascii=False))
    )

# --- 시트별 임포터 ---
def import_wedding_hall(conn, df):
    name_col   = pick_col(df.columns, ["conm","name","hall_name","unnamed: 0"])
    region_col = pick_col(df.columns, ["subway","region"])
    min_col    = pick_col(df.columns, ["min_fee","minprice","min_price"])

    price_cols = [c for c in ["hall_rental_fee","meal_expense","snapphoto","snapvideo"] if c in df.columns]
    scale = decide_scale(pd.concat([df[c] for c in price_cols + ([min_col] if min_col else [])], axis=0)) if price_cols or min_col else 1

    season_col = pick_col(df.columns, ["season","season(t/f)","seaon(t/f)"])
    peak_col   = pick_col(df.columns, ["peak","peak(t/f)"])
    guar_col   = next((c for c in df.columns if "guarantor" in str(c).lower()), None)

    mapping = {
        "hall_rental_fee": ("hall_package", "hall_rental_fee"),
        "meal_expense":    ("hall_package", "meal_expense"),
        "snapphoto":       ("photo_option", "snapphoto"),
        "snapvideo":       ("video_option", "snapvideo"),
    }

    for _, r in df.iterrows():
        name = str(r[name_col]).strip() if name_col and not pd.isna(r[name_col]) else None
        if not name: continue
        region = str(r[region_col]).strip() if region_col and not pd.isna(r[region_col]) else None
        min_price = None
        if min_col and not pd.isna(r[min_col]):
            mv = to_number(r[min_col])
            min_price = int(round(mv*scale)) if mv is not None else None

        vid = upsert_vendor(conn, "hall", name, region=region, min_price=min_price)

        meta_base = {}
        if season_col: meta_base["season"] = str(r[season_col]).strip()
        if peak_col:   meta_base["peak"]   = str(r[peak_col]).strip()
        if guar_col and not pd.isna(r[guar_col]): meta_base["num_guarantors"] = int(to_number(r[guar_col]))

        for col in price_cols:
            p = to_number(r[col]); price = int(round(p*scale)) if p is not None else None
            cat, pkg = mapping[col]
            insert_offering(conn, vid, cat, pkg, price, meta_base)

def import_studio(conn, df):
    name_col   = pick_col(df.columns, ["conm","name","studio","unnamed: 0"])
    region_col = pick_col(df.columns, ["subway","region"])
    min_col    = pick_col(df.columns, ["min_fee","minprice","min_price"])
    cands      = [("std_price","std"), ("afternoon_price","afternoon"), ("allday_price","allday")]

    price_cols = [c for c,_ in cands if c in df.columns]
    scale = decide_scale(pd.concat([df[c] for c in price_cols + ([min_col] if min_col else [])], axis=0)) if price_cols or min_col else 1

    for _, r in df.iterrows():
        name = str(r[name_col]).strip() if name_col and not pd.isna(r[name_col]) else None
        if not name: continue
        region = str(r[region_col]).strip() if region_col and not pd.isna(r[region_col]) else None
        min_price = None
        if min_col and not pd.isna(r[min_col]):
            mv = to_number(r[min_col]); min_price = int(round(mv*scale)) if mv is not None else None

        vid = upsert_vendor(conn, "studio", name, region=region, min_price=min_price)
        for col, pkg in cands:
            if col in df.columns:
                p = to_number(r[col]); price = int(round(p*scale)) if p is not None else None
                insert_offering(conn, vid, "studio_shoot", pkg, price, {})

def import_wedding_dress(conn, df):
    name_col   = pick_col(df.columns, ["conm","name","dessshop_name","dressshop_name","unnamed: 0"])
    region_col = pick_col(df.columns, ["subway","region"])
    min_col    = pick_col(df.columns, ["min_fee","minprice","min_price"])
    cands      = [("wedding","wedding"), ("photo","photo"), ("wedding+photo","wedding+photo"),
                  ("fitting_fee","fitting_fee"), ("helper","helper")]

    price_cols = [c for c,_ in cands if c in df.columns]
    scale = decide_scale(pd.concat([df[c] for c in price_cols + ([min_col] if min_col else [])], axis=0)) if price_cols or min_col else 1

    for _, r in df.iterrows():
        name = str(r[name_col]).strip() if name_col and not pd.isna(r[name_col]) else None
        if not name: continue
        region = str(r[region_col]).strip() if region_col and not pd.isna(r[region_col]) else None
        min_price = None
        if min_col and not pd.isna(r[min_col]):
            mv = to_number(r[min_col]); min_price = int(round(mv*scale)) if mv is not None else None

        vid = upsert_vendor(conn, "dress", name, region=region, min_price=min_price)
        for col, pkg in cands:
            if col in df.columns:
                p = to_number(r[col]); price = int(round(p*scale)) if p is not None else None
                insert_offering(conn, vid, "dress_rental", pkg, price, {})

def import_makeup(conn, df):
    name_col   = pick_col(df.columns, ["conm","name","shop","brand","unnamed: 0"])
    region_col = pick_col(df.columns, ["subway","region"])
    min_col    = pick_col(df.columns, ["min_fee","minprice","min_price"])

    role_cols = [(c, c.split("(")[0].strip().lower()) for c in df.columns
                 if any(k in str(c).lower() for k in ["manager","vicedirector","director"])]
    price_cols = [c for c,_ in role_cols]
    scale = decide_scale(pd.concat([df[c] for c in price_cols + ([min_col] if min_col else [])], axis=0)) if price_cols or min_col else 1

    for _, r in df.iterrows():
        name = str(r[name_col]).strip() if name_col and not pd.isna(r[name_col]) else None
        if not name: continue
        region = str(r[region_col]).strip() if region_col and not pd.isna(r[region_col]) else None
        min_price = None
        if min_col and not pd.isna(r[min_col]):
            mv = to_number(r[min_col]); min_price = int(round(mv*scale)) if mv is not None else None

        vid = upsert_vendor(conn, "makeup", name, region=region, min_price=min_price)
        for col, role in role_cols:
            p = to_number(r[col])
            if p is None: continue
            m = re.search(r"\((\d+)\)", str(col))
            meta = {"role": role}
            if m: meta["variant"] = m.group(1)
            price = int(round(p*scale))
            insert_offering(conn, vid, "makeup_package", role, price, meta)

# --- CSV 타입 감지(파일명/컬럼으로) ---
def detect_type(df, path: Path):
    lowname = path.name.lower()
    cols = [c.lower() for c in df.columns]
    if "wedding_hall" in lowname or "hall" in lowname or "hall_rental_fee" in cols:
        return "wedding_hall"
    if "studio" in lowname or "std_price" in cols or "allday_price" in cols:
        return "studio"
    if "wedding_dress" in lowname or "dress" in lowname or "wedding+photo" in cols:
        return "wedding_dress"
    if "makeup" in lowname or any(("manager" in c or "director" in c) for c in cols):
        return "makeup"
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csvs", nargs="+", help="임포트할 CSV 파일들")
    ap.add_argument("--db", default="marryroute.db", help="SQLite DB 경로")
    ap.add_argument("--encoding", default="utf-8", help="CSV 인코딩(기본 utf-8)")
    ap.add_argument("--reset", action="store_true", help="기존 데이터 삭제 후 재적재")
    args = ap.parse_args()

    for p in args.csvs:
        if not Path(p).exists():
            raise FileNotFoundError(p)

    with sqlite3.connect(args.db) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        if args.reset:
            conn.execute("DELETE FROM offering;")
            conn.execute("DELETE FROM vendor;")

        total_v = 0
        total_o = 0
        for p in args.csvs:
            path = Path(p)
            try:
                df = pd.read_csv(path, encoding=args.encoding)
            except Exception:
                df = pd.read_csv(path, engine="python", encoding=args.encoding)

            t = detect_type(df, path)
            if t == "wedding_hall":
                import_wedding_hall(conn, df); print(f"[{path.name}] hall OK")
            elif t == "studio":
                import_studio(conn, df); print(f"[{path.name}] studio OK")
            elif t == "wedding_dress":
                import_wedding_dress(conn, df); print(f"[{path.name}] dress OK")
            elif t == "makeup":
                import_makeup(conn, df); print(f"[{path.name}] makeup OK")
            else:
                print(f"[{path.name}] 스킵(타입 미확인)"); continue

        conn.commit()
        v = conn.execute("SELECT COUNT(*) FROM vendor").fetchone()[0]
        o = conn.execute("SELECT COUNT(*) FROM offering").fetchone()[0]
        print(f"✅ Import 완료 | vendors={v}, offerings={o}")

if __name__ == "__main__":
    main()