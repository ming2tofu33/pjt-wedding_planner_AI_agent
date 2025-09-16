# 목적: 엑셀 시트를 '롱 포맷'으로 변환해 SQLite(marryroute.db)에 적재
import pandas as pd
import sqlite3, json, argparse, re
from pathlib import Path

DB_PATH = "marryroute.db"

# --- 숫자 파서(소수 유지) ---
def to_number(v):
    if pd.isna(v): return None
    s = str(v).strip().replace(",", "")
    if s == "" or s == "-": return None
    m = re.findall(r"[0-9]+(?:\.[0-9]+)?", s)  # 소수 포함
    if not m: return None
    return float(m[0])

# --- 스케일 결정(만원/원 자동 감지) ---
def decide_scale(series):
    vals = [to_number(x) for x in series if not pd.isna(x)]
    vals = [v for v in vals if v is not None]
    if not vals: return 1
    vals.sort()
    med = vals[len(vals)//2]
    return 10000 if med < 500 else 1  # 중앙값<500이면 '만원' 가정 → 원 환산

# --- 컬럼 자동 선택 ---
def pick_col(columns, candidates):
    cols_low = {str(c).strip().lower(): c for c in columns}
    for key in candidates:
        if key in cols_low: return cols_low[key]
    return None

# --- 벤더 upsert ---
def upsert_vendor(conn, vtype, name, region=None, notes=None):
    cur = conn.execute("SELECT vendor_id FROM vendor WHERE type=? AND name=?", (vtype, name))
    row = cur.fetchone()
    if row:
        vid = row[0]
        if region or notes:
            conn.execute(
                "UPDATE vendor SET region=COALESCE(?,region), notes=COALESCE(?,notes) WHERE vendor_id=?",
                (region, notes, vid)
            )
        return vid
    cur = conn.execute(
        "INSERT INTO vendor(type,name,region,notes) VALUES (?,?,?,?)",
        (vtype, name, region, notes)
    )
    return cur.lastrowid

# --- 오퍼링 insert ---
def insert_offering(conn, vendor_id, category, package_name, price, meta=None):
    conn.execute(
        "INSERT INTO offering(vendor_id,category,package_name,price,meta_json) VALUES (?,?,?,?,?)",
        (vendor_id, category, package_name, price, json.dumps(meta or {}, ensure_ascii=False))
    )

# --- wedding_hall ---
def import_wedding_hall(conn, df):
    name_col   = pick_col(df.columns, ["name","hall_name","conm","unnamed: 0"])
    region_col = pick_col(df.columns, ["region","subway"])

    price_cols = [c for c in ["hall_rental_fee","meal_expense","snapphoto","snapvideo"] if c in df.columns]
    scale = decide_scale(pd.concat([df[c] for c in price_cols], axis=0)) if price_cols else 1

    season_col = pick_col(df.columns, ["season","season(t/f)","seaon(t/f)"])  # 오타 포함
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
        vid = upsert_vendor(conn, "hall", name, region=region)

        meta_base = {}
        if season_col: meta_base["season"] = str(r[season_col]).strip()
        if peak_col:   meta_base["peak"]   = str(r[peak_col]).strip()
        if guar_col and not pd.isna(r[guar_col]): meta_base["num_guarantors"] = int(to_number(r[guar_col]))

        for col in price_cols:
            p = to_number(r[col])
            price = int(round(p*scale)) if p is not None else None
            cat, pkg = mapping[col]
            insert_offering(conn, vid, cat, pkg, price, meta_base)

# --- studio ---
def import_studio(conn, df):
    name_col   = pick_col(df.columns, ["name","studio","conm","unnamed: 0"])
    region_col = pick_col(df.columns, ["region","subway"])
    cands = [("std_price","std"), ("afternoon_price","afternoon"), ("allday_price","allday")]
    price_cols = [c for c,_ in cands if c in df.columns]
    scale = decide_scale(pd.concat([df[c] for c in price_cols], axis=0)) if price_cols else 1

    for _, r in df.iterrows():
        name = str(r[name_col]).strip() if name_col and not pd.isna(r[name_col]) else None
        if not name: continue
        region = str(r[region_col]).strip() if region_col and not pd.isna(r[region_col]) else None
        vid = upsert_vendor(conn, "studio", name, region=region)
        for col, pkg in cands:
            if col in df.columns:
                p = to_number(r[col])
                price = int(round(p*scale)) if p is not None else None
                insert_offering(conn, vid, "studio_shoot", pkg, price, {})

# --- wedding_dress ---
def import_wedding_dress(conn, df):
    name_col   = pick_col(df.columns, ["name","dessshop_name","dressshop_name","conm","unnamed: 0"])
    region_col = pick_col(df.columns, ["region","subway"])
    cands = [("wedding","wedding"), ("photo","photo"), ("wedding+photo","wedding+photo"),
             ("fitting_fee","fitting_fee"), ("helper","helper")]
    price_cols = [c for c,_ in cands if c in df.columns]
    scale = decide_scale(pd.concat([df[c] for c in price_cols], axis=0)) if price_cols else 1

    for _, r in df.iterrows():
        name = str(r[name_col]).strip() if name_col and not pd.isna(r[name_col]) else None
        if not name: continue
        region = str(r[region_col]).strip() if region_col and not pd.isna(r[region_col]) else None
        vid = upsert_vendor(conn, "dress", name, region=region)
        for col, pkg in cands:
            if col in df.columns:
                p = to_number(r[col])
                price = int(round(p*scale)) if p is not None else None
                insert_offering(conn, vid, "dress_rental", pkg, price, {})

# --- makeup ---
def import_makeup(conn, df):
    name_col   = pick_col(df.columns, ["name","shop","brand","conm","unnamed: 0"])
    region_col = pick_col(df.columns, ["region","subway"])
    role_cols = [(c, c.split("(")[0].strip().lower()) for c in df.columns
                 if any(k in str(c).lower() for k in ["manager","vicedirector","director"])]
    price_cols = [c for c,_ in role_cols]
    scale = decide_scale(pd.concat([df[c] for c in price_cols], axis=0)) if price_cols else 1

    for _, r in df.iterrows():
        name = str(r[name_col]).strip() if name_col and not pd.isna(r[name_col]) else None
        if not name: continue
        region = str(r[region_col]).strip() if region_col and not pd.isna(r[region_col]) else None
        vid = upsert_vendor(conn, "makeup", name, region=region)
        for col, role in role_cols:
            p = to_number(r[col])
            if p is None: continue
            m = re.search(r"\((\d+)\)", str(col))
            meta = {"role": role}
            if m: meta["variant"] = m.group(1)
            price = int(round(p*scale))
            insert_offering(conn, vid, "makeup_package", role, price, meta)

# --- 메인 ---
def main(xlsx_path, db_path=DB_PATH):
    xlsx = pd.ExcelFile(xlsx_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("DELETE FROM offering;")
        conn.execute("DELETE FROM vendor;")
        conn.commit()

        for sheet in xlsx.sheet_names:
            df = xlsx.parse(sheet)
            low = sheet.strip().lower()
            if low in ["wedding_hall","hall"]:
                import_wedding_hall(conn, df);  print(f"[{sheet}] OK")
            elif low in ["studio","studios"]:
                import_studio(conn, df);        print(f"[{sheet}] OK")
            elif low in ["wedding_dress","dress"]:
                import_wedding_dress(conn, df); print(f"[{sheet}] OK")
            elif low in ["makeup","mua"]:
                import_makeup(conn, df);        print(f"[{sheet}] OK")
            else:
                print(f"[{sheet}] 스킵")

        v = conn.execute("SELECT COUNT(*) FROM vendor").fetchone()[0]
        o = conn.execute("SELECT COUNT(*) FROM offering").fetchone()[0]
        print(f"✅ Import 완료 | vendors={v}, offerings={o}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("excel", help="엑셀 경로 (예: MarryRoute.DB.xlsx)")
    ap.add_argument("--db", default=DB_PATH)
    args = ap.parse_args()
    if not Path(args.excel).exists():
        raise FileNotFoundError(args.excel)
    main(args.excel, args.db)
