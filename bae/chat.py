# chat.py
# 목적: 콘솔 챗 → parser + planner_update 연동 + 카탈로그 추천/검색
import sys
from planner_update import update_from_text, _fetch_state, build_summary_text
from catalog_bridge import recommend, catalog, normalize_cat

DB_PATH = "marryroute.db"

HELP_TEXT = """\
명령어:
  /help                    사용법 보기
  /summary                 최신 요약 보기
  /recommend <cat>         예산/지역 기반 Top 추천 (지역 우선 → 가격 오름차순)
  /catalog <cat>           필터 적용 리스트 (상위 20개)
  /추천 <카테고리>             (동일기능) 예: /추천 드레스
  /목록 <카테고리>             (동일기능) 예: /목록 홀
  *오타 허용: /recommand, /catlog 도 동작
cat: dress|makeup|studio|hall 또는 드레스|메이크업|스튜디오|홀
그 외 문장: 자연어 입력 → 파싱→DB반영→요약 갱신
예) 본식은 10/26, 스튜디오는 홍대입구역, 드레스 300~400
"""

def show_summary(db=DB_PATH):
    try:
        state = _fetch_state(db)
        print("요약:", build_summary_text(state))
    except Exception as e:
        print("⚠️ 요약 표시 중 오류:", e)

def _norm_cat(token: str) -> str:
    return (normalize_cat(token) or token or "").lower()

def show_reco(cat_token: str):
    try:
        rows = recommend(DB_PATH, _norm_cat(cat_token), limit=5)
    except Exception as e:
        print("⚠️ 추천 조회 중 오류:", e)
        print("  - vendor/offering 테이블과 category/price/region 컬럼을 확인하세요.")
        return
    if not rows:
        print("추천 결과가 없습니다. (예산/지역 선호를 먼저 설정해 보세요)")
        return
    print(f"[추천:{_norm_cat(cat_token)}] (지역 우선 → 가격 오름차순)")
    for i, r in enumerate(rows, 1):
        price = "-" if r.get("min_price") is None else f"{int(r['min_price'])}만원~"
        region = r.get("region") or "-"
        print(f"{i}. {r['name']} | {region} | {price}")

def show_catalog(cat_token: str):
    try:
        rows = catalog(DB_PATH, _norm_cat(cat_token), limit=20)
    except Exception as e:
        print("⚠️ 카탈로그 조회 중 오류:", e)
        print("  - vendor/offering 테이블과 category/price/region 컬럼을 확인하세요.")
        return
    if not rows:
        print("목록이 없습니다.")
        return
    print(f"[카탈로그:{_norm_cat(cat_token)}] (지역 우선 → 가격 오름차순)")
    for r in rows:
        price = "-" if r.get("min_price") is None else f"{int(r['min_price'])}만원~"
        region = r.get("region") or "-"
        print(f"- #{r['id']} {r['name']} | {region} | {price}")

def main():
    print("=== 메리루트 미니 챗 데모 ===")
    print(HELP_TEXT)
    while True:
        try:
            text = input("You> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n안녕히 가세요!"); break

        if not text:
            continue

        if text.startswith("/"):
            toks = text.split()
            cmd = toks[0].lower()
            arg = toks[1] if len(toks) >= 2 else None

            if cmd in ("/help", "/도움말"):
                print(HELP_TEXT)
            elif cmd in ("/summary", "/요약"):
                show_summary(DB_PATH)
            elif cmd in ("/recommend", "/추천", "/recommand"):  # 오타 허용
                if not arg: print("사용법: /추천 <카테고리>"); continue
                show_reco(arg)
            elif cmd in ("/catalog", "/목록", "/리스트", "/catlog"):  # 오타 허용
                if not arg: print("사용법: /목록 <카테고리>"); continue
                show_catalog(arg)
            elif cmd in ("/quit", "/종료"):
                print("안녕히 가세요!"); break
            else:
                print("알 수 없는 명령입니다. /help 를 입력해 보세요.")
            continue

        # 일반 문장 → 업데이트
        try:
            result = update_from_text(DB_PATH, text, dry_run=False)
        except Exception as e:
            print("⚠️ 업데이트 중 오류:", e)
            continue

        if result.get("reinput"):
            print("[재입력요청]")
            for m in result["reinput"]:
                print("-", m)

        print("[요약 갱신 완료]")
        state = result.get("committed")
        print(build_summary_text(state) if state else "(요약 없음)")

if __name__ == "__main__":
    if sys.version_info < (3,8):
        print("Python 3.8+ 권장")
    main()
