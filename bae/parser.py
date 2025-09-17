# 목적: 한국어 입력에서 날짜/지역/카테고리별 예산(만원) 추출 → JSON
import re, json, argparse
from datetime import datetime
from typing import Optional, List, Dict, Any

TODAY = datetime.now()  # Asia/Seoul 가정

CAT_MAP: Dict[str, List[str]] = {
    "dress":  ["드레스", "본식드레스", "촬영드레스"],
    "makeup": ["메이크업", "메컵", "헤어", "헤메"],
    "studio": ["스튜디오", "촬영", "리허설", "스냅", "스냅촬영", "리허설촬영", "본식스냅"],
    "hall":   ["예식장", "결혼식장", "웨딩홀", "홀", "예식홀"],
}
EVENT_WEDDING = ["본식", "예식", "결혼식", "웨딩", "결혼"]

# 카테고리별 최소 합리값(만원) — 너무 낮으면 오류로 처리
MIN_REQ_MANWON = {"hall": 100, "studio": 30, "dress": 50, "makeup": 10}

# 모든 카테고리 키워드(경계 탐지용)
ALL_CAT_KEYS: List[str] = [k for keys in CAT_MAP.values() for k in keys]
CAT_KEYS_SORTED = sorted(ALL_CAT_KEYS, key=len, reverse=True)
CAT_BOUNDARY_RE = re.compile("|".join(map(re.escape, CAT_KEYS_SORTED)))

# -------- 숫자/단위 파싱(만원 환산) --------
def _to_manwon(num_str: str, unit_hint: Optional[str]) -> float:
    v = float(num_str)
    if unit_hint is None:
        return v
    unit = unit_hint.replace(" ", "")
    if unit in ("만원", "만"): return v
    if unit == "원":           return v / 10000.0
    if unit == "천원":         return (v * 1000) / 10000.0
    if unit in ("백만원", "백만"): return v * 100.0
    if unit in ("억원", "억"):     return v * 10000.0
    return v

def parse_amount_block(s: str):
    """
    금액 표현 인식:
      - A±B, A~B
      - '최대/상한/이하/까지' || '최소/하한/이상/부터'
      - 단일값은 (x,x)로 돌려주고, ±10% 추정은 카테고리 단계에서 처리
    반환: (min_man, max_man, kind)  kind ∈ {plusminus, range, le, ge, single, none}
    """
    t = s.replace(" ", "")

    # ① A±B
    m = re.search(r'(\d+(?:\.\d+)?)[±\+\-]\s*(\d+(?:\.\d+)?)(만원|만|원|천원|백만원|백만|억|억원)?', t)
    if m:
        base = _to_manwon(m.group(1), None)
        delta = _to_manwon(m.group(2), m.group(3))
        return max(0, base - delta), base + delta, "plusminus"

    # ② A~B
    m = re.search(r'(\d+(?:\.\d+)?)\s*[~\-]\s*(\d+(?:\.\d+)?)(만원|만|원|천원|백만원|백만|억|억원)?', t)
    if m:
        a = _to_manwon(m.group(1), None)
        b = _to_manwon(m.group(2), m.group(3))
        lo, hi = sorted([a, b])
        return lo, hi, "range"

    # ③ 숫자 뒤에 이하/최대/상한/까지
    m = re.search(r'(\d+(?:\.\d+)?)(만원|만|원|천원|백만원|백만|억|억원)?(이하|최대|상한|까지)', t)
    if m:
        hi = _to_manwon(m.group(1), m.group(2))
        return None, hi, "le"

    # ④ 숫자 뒤에 이상/최소/하한/부터
    m = re.search(r'(\d+(?:\.\d+)?)(만원|만|원|천원|백만원|백만|억|억원)?(이상|최소|하한|부터)', t)
    if m:
        lo = _to_manwon(m.group(1), m.group(2))
        return lo, None, "ge"

    # ⑤ 단어 뒤에 숫자: 이하/최대/상한/까지
    m = re.search(r'(최대|상한|이하|까지)\s*(\d+(?:\.\d+)?)(만원|만|원|천원|백만원|백만|억|억원)?', t)
    if m:
        hi = _to_manwon(m.group(2), m.group(3))
        return None, hi, "le"

    # ⑥ 단어 뒤에 숫자: 이상/최소/하한/부터
    m = re.search(r'(최소|하한|이상|부터)\s*(\d+(?:\.\d+)?)(만원|만|원|천원|백만원|백만|억|억원)?', t)
    if m:
        lo = _to_manwon(m.group(2), m.group(3))
        return lo, None, "ge"

    # ⑦ 단일값
    m = re.search(r'(\d+(?:\.\d+)?)(만원|만|원|천원|백만원|백만|억|억원)?', t)
    if m:
        x = _to_manwon(m.group(1), m.group(2))
        return x, x, "single"

    return None, None, "none"

# -------- 날짜 파싱 --------
DATE_PAT_FULL = re.compile(r'(?P<y>20\d{2})[.\-/](?P<m>\d{1,2})[.\-/](?P<d>\d{1,2})')
DATE_PAT_MD   = re.compile(r'(?P<m>\d{1,2})[.\-/](?P<d>\d{1,2})')
DATE_PAT_MKOR = re.compile(r'(?P<m>\d{1,2})\s*월\s*(?P<d>\d{1,2})\s*일')
DATE_CLUES = ("본식","예식","결혼","촬영","예약","일정","리허설","청첩장","피팅","시간","오전","오후","PM","AM")

def _infer_year(m: int, d: int) -> int:
    y = TODAY.year
    try:
        cand = datetime(year=y, month=m, day=d)
    except ValueError:
        return y
    return y if cand.date() >= TODAY.date() else y + 1

def _has_date_context(text: str, start: int, end: int) -> bool:
    win = text[max(0, start-15):min(len(text), end+15)]
    return any(k in win for k in DATE_CLUES) or ("월" in win or "일" in win)

def _near_category(text: str, start: int, distance: int = 8) -> bool:
    left = text[max(0, start-distance):start]
    return any(k in left for k in ALL_CAT_KEYS)

def parse_dates(text: str):
    out: List[str] = []
    # YYYY-MM-DD / YYYY.MM.DD
    for m in DATE_PAT_FULL.finditer(text):
        y, mm, dd = int(m.group("y")), int(m.group("m")), int(m.group("d"))
        try:
            dt = datetime(y, mm, dd).strftime("%Y-%m-%d")
            if dt not in out: out.append(dt)
        except ValueError: pass
    # M월 D일
    for m in DATE_PAT_MKOR.finditer(text):
        y = _infer_year(int(m.group("m")), int(m.group("d")))
        try:
            dt = datetime(y, int(m.group("m")), int(m.group("d"))).strftime("%Y-%m-%d")
            if dt not in out: out.append(dt)
        except ValueError: pass
    # M.D / M-D — 컨텍스트/카테고리 근접 시 무시
    for m in DATE_PAT_MD.finditer(text):
        s, e = m.span()
        if not _has_date_context(text, s, e):
            continue
        if _near_category(text, s):
            continue
        y = _infer_year(int(m.group("m")), int(m.group("d")))
        try:
            dt = datetime(y, int(m.group("m")), int(m.group("d"))).strftime("%Y-%m-%d")
            if dt not in out: out.append(dt)
        except ValueError: pass
    return out

# -------- 지역 추출(전역 vs 카테고리국소) --------
REGION_PAT = re.compile(r'([가-힣A-Za-z0-9]+)\s*(역|권|구|동)')

def parse_regions_scoped(text: str):
    globals_, by_cat = [], {}  # 전역 지역, 카테고리별 지역
    for m in REGION_PAT.finditer(text):
        token = (m.group(1) + m.group(2)).strip()
        s = m.start()
        # 카테고리 키워드가 바로 앞(8자) 이내면 카테고리 지역으로
        if _near_category(text, s, distance=8):
            for cat, keys in CAT_MAP.items():
                left = text[max(0, s-12):s]
                if any(k in left for k in keys):
                    by_cat.setdefault(cat, [])
                    if token not in by_cat[cat]:
                        by_cat[cat].append(token)
                    break
        else:
            if token not in globals_:
                globals_.append(token)
    return globals_, by_cat

# -------- 카테고리 예산 --------
BOUNDARY_PUNC_RE = re.compile(r'[\.!\?;,\n]')

def _window_after_keyword(text: str, start_idx: int, max_len: int = 40) -> str:
    """
    키워드 바로 뒤에서 다음 경계(문장부호/다음 카테고리 키워드)까지의 슬라이스만 사용.
    → '메이크업은 강남역 근처로! 드레스 300~400' 에서 메이크업 창은 '!...' 전까지로 제한
    """
    end_limit = min(len(text), start_idx + max_len)

    # 다음 문장부호 위치
    punc_m = BOUNDARY_PUNC_RE.search(text, pos=start_idx, endpos=end_limit)
    punc_idx = punc_m.start() if punc_m else None

    # 다음 카테고리 키워드 위치
    cat_m = CAT_BOUNDARY_RE.search(text, pos=start_idx, endpos=end_limit)
    cat_idx = cat_m.start() if cat_m else None

    # 가장 가까운 경계 선택
    candidates = [i for i in [punc_idx, cat_idx] if i is not None]
    cut = min(candidates) if candidates else end_limit
    return text[start_idx:cut]

def parse_category_budgets(text: str):
    results: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    for cat, keys in CAT_MAP.items():
        for k in keys:
            for m in re.finditer(re.escape(k), text):
                # 키워드 뒤 40자 이내에서, 경계 전까지만 스캔
                window_full = text[m.end(): m.end()+40]
                window = _window_after_keyword(text, m.end(), max_len=40)

                lo, hi, kind = parse_amount_block(window)
                if lo is None and hi is None:
                    continue

                # 단일값 → ±10% 추정
                if kind == "single" and lo is not None and hi is not None:
                    v = lo
                    lo = max(0, v * 0.9)
                    hi = v * 1.1

                # 합리 하한 체크/클램프/제거
                floor = MIN_REQ_MANWON.get(cat)
                if floor is not None:
                    too_low = (
                        (hi is not None and hi < floor) or
                        (hi is None and lo is not None and lo < floor) or
                        (lo is not None and hi is not None and hi < floor)
                    )
                    if too_low:
                        errors.append({
                            "code": "min_too_low",
                            "category": cat,
                            "min_required": floor,
                            "observed": {"lo": round(lo) if lo is not None else None,
                                         "hi": round(hi) if hi is not None else None},
                            "context": window.strip(),
                            "suggest": f"{floor}만원 이상으로 다시 입력해주세요."
                        })
                        continue
                    if lo is not None and lo < floor:
                        lo = floor

                results.append({
                    "category": cat,
                    "min_manwon": None if lo is None else round(lo),
                    "max_manwon": None if hi is None else round(hi),
                    "matched": k,
                    "kind": kind
                })

    # 같은 카테고리는 '마지막 언급' 우선(덮어쓰기)
    by_cat: Dict[str, Dict[str, Any]] = {}
    for r in results:
        by_cat[r["category"]] = r
    return list(by_cat.values()), errors

# -------- 이벤트(wedding) --------
def detect_wedding_event(text: str, dates: List[str]):
    if any(kw in text for kw in EVENT_WEDDING) and dates:
        return {"type": "wedding", "date": dates[0]}
    return None

# -------- 메인 --------
def parse_text(text: str):
    text_norm = re.sub(r'\s+', ' ', text.strip())
    dates = parse_dates(text_norm)
    global_regions, category_regions = parse_regions_scoped(text_norm)
    budgets, errors = parse_category_budgets(text_norm)
    wedding = detect_wedding_event(text_norm, dates)

    return {
        "dates": dates,
        "regions": global_regions,              # 전역 지역(카테고리 문맥 제외)
        "category_regions": category_regions,   # 카테고리별 지역
        "budgets": budgets,                     # [{category, min_manwon, max_manwon, ...}]
        "events": [wedding] if wedding else [],
        "errors": errors                        # [{code, category, suggest, ...}]
    }

def main():
    ap = argparse.ArgumentParser(description="Korean wedding NLU parser")
    ap.add_argument("mode", choices=["parse"])
    ap.add_argument("--text", help="자연어 입력(직접)")
    ap.add_argument("--file", help="텍스트 파일에서 읽기")
    args = ap.parse_args()

    if args.mode == "parse":
        text = open(args.file, "r", encoding="utf-8").read() if args.file else (args.text or "")
        print(json.dumps(parse_text(text), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
