# demo_cli.py
# 콘솔에서 추천 → 상세 (만원 단위 입출력, vendor.min_price 우선 표시)
import argparse
from catalog import find_vendors, get_offerings

VTYPES = ["hall", "studio", "dress", "makeup"]

def fmt_price(v):
    if v is None: return "-"
    s = f"{v/10000.0:.1f}".rstrip("0").rstrip(".")
    return f"{s}만원"

def ask(msg):
    try: return input(msg).strip()
    except EOFError: return ""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="marryroute.db", help="SQLite DB 경로")
    ap.add_argument("--limit", type=int, default=10, help="추천 리스트 최대 개수")
    args = ap.parse_args()
    db_path, limit = args.db, args.limit

    print("=== 메리루트 | 콘솔 데모 ===  (q=종료)")
    while True:
        vtype = ask(f"\n유형 [{', '.join(VTYPES)}] (엔터=전체): ")
        if vtype.lower() == "q": break
        if vtype and vtype not in VTYPES:
            print("⚠️  유형이 올바르지 않습니다. 예) makeup"); continue

        region = ask("지역(예: 강남, 홍대 / 엔터=전체): ")
        if region.lower() == "q": break
        region = region or None

        price_s = ask("예산 상한(만원, 예: 120 또는 5.5 / 엔터=제한없음): ")
        if price_s.lower() == "q": break
        price_max = None
        if price_s:
            try: price_max = int(round(float(price_s)*10000))
            except: price_max = None

        keyword = ask("키워드(업체명 일부 / 엔터=없음): ")
        if keyword.lower() == "q": break
        keyword = keyword or None

        rows = find_vendors(
            db_path=db_path, vtype=vtype or None, region=region,
            price_max=price_max, keyword=keyword, limit=limit
        )
        if not rows:
            print("\n검색 결과가 없습니다. 조건을 바꿔보세요.")
            continue

        print(f"\n[추천 결과 상위 {limit}]")
        for i, r in enumerate(rows, 1):
            src = "표준(min_fee)" if r.get("min_source") == "vendor" else "계산"
            print(f"{i:>2}. #{r['vendor_id']} [{r['type']}] {r['name']} ({r.get('region') or '-'})"
                  f" | 최저가 {fmt_price(r['min_price'])} [{src}] | 상품 {r['cnt_offers']}개")

        sel = ask("\n상세를 볼 번호(엔터=다시검색, q=종료): ")
        if sel.lower() == "q": break
        if not sel: continue
        if not sel.isdigit() or not (1 <= int(sel) <= len(rows)):
            print("⚠️  번호를 다시 입력하세요."); continue

        chosen = rows[int(sel)-1]
        items = get_offerings(db_path, chosen["vendor_id"])
        print(f"\n[상세] {chosen['name']}  (#{chosen['vendor_id']})")
        if not items:
            print("등록된 오퍼링이 없습니다.")
        else:
            for it in items:
                meta = f" {it['meta_json']}" if it["meta_json"] else ""
                print(f"- [{it['category']}] {it['package_name']}: {fmt_price(it['price'])}{meta}")

        back = ask("\n엔터=이전으로, q=종료: ")
        if back.lower() == "q": break

if __name__ == "__main__":
    main()