# demo_cli.py
# 콘솔에서 추천 → 상세 보기 (만원 단위 입출력, --db 지원)
import argparse
from catalog import find_vendors, get_offerings

VTYPES = ["hall", "studio", "dress", "makeup"]

def fmt_price(v):
    if v is None:
        return "-"
    mw = v / 10000.0
    s = f"{mw:.1f}".rstrip("0").rstrip(".")
    return f"{s}만원"

def ask(prompt):
    try:
        return input(prompt).strip()
    except EOFError:
        return ""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="marryroute.db", help="SQLite DB 경로 (기본: marryroute.db)")
    ap.add_argument("--limit", type=int, default=10, help="추천 리스트 최대 개수")
    args = ap.parse_args()

    db_path = args.db
    limit = args.limit

    print("=== 메리루트 | 콘솔 데모 ===")
    while True:
        print("\n[추천 조건 입력] (엔터=건너뛰기, q=종료)")
        vtype = ask(f"유형 [{', '.join(VTYPES)}]: ")
        if vtype.lower() == "q":
            print("종료합니다. 감사합니다!")
            break
        if vtype == "":
            vtype = None
        elif vtype not in VTYPES:
            print("⚠️  유형이 올바르지 않습니다. 예) makeup")
            continue

        region = ask("지역(예: 강남, 홍대): ")
        if region.lower() == "q":
            print("종료합니다. 감사합니다!")
            break
        region = region or None

        price_s = ask("예산 상한(만원, 예: 120 또는 5.5): ")
        if price_s.lower() == "q":
            print("종료합니다. 감사합니다!")
            break
        price_max = None
        if price_s:
            try:
                price_max = int(round(float(price_s) * 10000))
            except:
                price_max = None

        keyword = ask("키워드(업체명 일부): ")
        if keyword.lower() == "q":
            print("종료합니다. 감사합니다!")
            break
        keyword = keyword or None

        rows = find_vendors(
            db_path=db_path,
            vtype=vtype,
            region=region,
            price_max=price_max,
            keyword=keyword,
            limit=limit,
        )
        if not rows:
            print("\n검색 결과가 없습니다. 조건을 바꿔보세요.")
            continue

        print(f"\n[추천 결과 상위 {limit}]")
        for i, r in enumerate(rows, 1):
            print(f"{i:>2}. #{r['vendor_id']} [{r['type']}] {r['name']} ({r.get('region') or '-'})"
                  f" | 최저가 {fmt_price(r['min_price'])} | 상품 {r['cnt_offers']}개")

        sel = ask("\n상세를 볼 번호(1~{}), 다시검색=엔터, 종료=q: ".format(len(rows)))
        if sel.lower() == "q":
            print("종료합니다. 감사합니다!")
            break
        if not sel:
            continue
        if not sel.isdigit() or not (1 <= int(sel) <= len(rows)):
            print("⚠️  번호를 다시 입력하세요.")
            continue

        chosen = rows[int(sel) - 1]
        items = get_offerings(db_path, chosen["vendor_id"])
        print(f"\n[상세] {chosen['name']}  (#{chosen['vendor_id']})")
        if not items:
            print("등록된 오퍼링이 없습니다.")
        else:
            for it in items:
                meta = f" {it['meta_json']}" if it["meta_json"] else ""
                print(f"- [{it['category']}] {it['package_name']}: {fmt_price(it['price'])}{meta}")

        _ = ask("\n엔터=이전으로, q=종료: ")
        if _.lower() == "q":
            print("종료합니다. 감사합니다!")
            break

if __name__ == "__main__":
    main()
