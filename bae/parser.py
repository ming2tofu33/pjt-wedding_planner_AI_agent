# 목적: 한국어 입력에서 날짜/지역/카테고리별 예산(만원) 추출 → JSON
import re, json, argparse
from datetime import datetime
from typing import Optional, List, Dict, Any

TODAY = datetime.now()

CAT_MAP: Dict[str, List[str]] = {
    "dress":  ["드레스", "본식드레스", "촬영드레스"],
    "makeup": ["메이크업", "메컵", "헤어", "헤메"],
    "studio": ["스튜디오", "촬영", "리허설", "스냅", "스냅촬영", "리허설촬영", "본식스냅"],
    "hall":   ["예식장", "결혼식장", "웨딩홀", "홀", "예식홀"],
}
EVENT_WEDDING = ["본식", "예식", "결혼식", "웨딩", "결혼"]
MIN_REQ_MANWON = {"hall": 100, "studio": 30, "dress": 50, "makeup": 10}

ALL_CAT_KEYS: List[str] = [k for keys in CAT_MAP.values() for k in keys]
CAT_KEYS_SORTED = sorted(ALL_CAT_KEYS, key=len, reverse=True)
CAT_BOUNDARY_RE = re.compile("|".join(map(re.escape, CAT_KEYS_SORTED)))

def _to_manwon(num_str: str, unit_hint: Optional[str]) -> float:
    v = float(num_str)
    if unit_hint is None: return v
    unit = unit_hint.replace(" ", "")
    if unit in ("만원", "만"): return v
    if unit == "원": return v/10000.0
    if unit == "천원": return (v*1000)/10000.0
    if unit in ("백만원","백만"): return v*100.0
    if unit in ("억원","억"):     return v*10000.0
    return v

def parse_amount_block(s: str):
    t = s.replace(" ", "")
    m = re.search(r'(\d+(?:\.\d+)?)[±\+\-]\s*(\d+(?:\.\d+)?)(만원|만|원|천원|백만원|백만|억|억원)?', t)
    if m:
        base = _to_manwon(m.group(1), None)
        delta = _to_manwon(m.group(2), m.group(3))
        return max(0, base-delta), base+delta, "plusminus"
    m = re.search(r'(\d+(?:\.\d+)?)\s*[~\-]\s*(\d+(?:\.\d+)?)(만원|만|원|천원|백만원|백만|억|억원)?', t)
    if m:
        a = _to_manwon(m.group(1), None)
        b = _to_manwon(m.group(2), m.group(3))
        lo, hi = sorted([a,b]); return lo, hi, "range"
    m = re.search(r'(\d+(?:\.\d+)?)(만원|만|원|천원|백만원|백만|억|억원)?(이하|최대|상한|까지)', t)
    if m: hi = _to_manwon(m.group(1), m.group(2)); return None, hi, "le"
    m = re.search(r'(\d+(?:\.\d+)?)(만원|만|원|천원|백만원|백만|억|억원)?(이상|최소|하한|부터)', t)
    if m: lo = _to_manwon(m.group(1), m.group(2)); return lo, None, "ge"
    m = re.search(r'(최대|상한|이하|까지)\s*(\d+(?:\.\d+)?)(만원|만|원|천원|백만원|백만|억|억원)?', t)
    if m: hi = _to_manwon(m.group(2), m.group(3)); return None, hi, "le"
    m = re.search(r'(최소|하한|이상|부터)\s*(\d+(?:\.\d+)?)(만원|만|원|천원|백만원|백만|억|억원)?', t)
    if m: lo = _to_manwon(m.group(2), m.group(3)); return lo, None, "ge"
    m = re.search(r'(\d+(?:\.\d+)?)(만원|만|원|천원|백만원|백만|억|억원)?', t)
    if m: x = _to_manwon(m.group(1), m.group(2)); return x, x, "single"
    return None, None, "none"

DATE_PAT_FULL = re.compile(r'(?P<y>20\d{2})[.\-/](?P<m>\d{1,2})[.\-/](?P<d>\d{1,2})')
DATE_PAT_MD   = re.compile(r'(?P<m>\d{1,2})[.\-/](?P<d>\d{1,2})')
DATE_PAT_MKOR = re.compile(r'(?P<m>\d{1,2})\s*월\s*(?P<d>\d{1,2})\s*일')
DATE_CLUES = ("본식","예식","결혼","촬영","예약","일정","리허설","청첩","피팅","세레모니","시간","오전","오후","PM","AM")

def _infer_year(m: int, d: int) -> int:
    y = TODAY.year
    try: cand = datetime(year=y, month=m, day=d)
    except ValueError: return y
    return y if cand.date() >= TODAY.date() else y+1

def _has_date_context(text: str, start: int, end: int) -> bool:
    win = text[max(0,start-15):min(len(text), end+15)]
    return any(k in win for k in DATE_CLUES) or ("월" in win or "일" in win)

def _near_category(text: str, start: int, distance: int = 8) -> bool:
    left = text[max(0, start-distance):start]
    return any(k in left for k in ALL_CAT_KEYS)

def parse_dates(text: str):
    out: List[str] = []
    for m in DATE_PAT_FULL.finditer(text):
        y, mm, dd = int(m.group("y")), int(m.group("m")), int(m.group("d"))
        try:
            dt = datetime(y, mm, dd).strftime("%Y-%m-%d")
            if dt not in out: out.append(dt)
        except ValueError: pass
    for m in DATE_PAT_MKOR.finditer(text):
        y = _infer_year(int(m.group("m")), int(m.group("d")))
        try:
            dt = datetime(y, int(m.group("m")), int(m.group("d"))).strftime("%Y-%m-%d")
            if dt not in out: out.append(dt)
        except ValueError: pass
    for m in DATE_PAT_MD.finditer(text):
        s, e = m.span()
        if not _has_date_context(text, s, e): continue
        if _near_category(text, s): continue
        y = _infer_year(int(m.group("m")), int(m.group("d")))
        try:
            dt = datetime(y, int(m.group("m")), int(m.group("d"))).strftime("%Y-%m-%d")
            if dt not in out: out.append(dt)
        except ValueError: pass
    return out

# ↓↓↓ 핵심 수정: 접미 뒤에 문자가 오면 매칭 금지(부분매치 차단)
REGION_PAT = re.compile(r'([가-힣A-Za-z0-9]+?)\s*(역|권|구|동)(?![가-힣A-Za-z0-9])')

def parse_regions_scoped(text: str):
    globals_, by_cat = [], {}
    for m in REGION_PAT.finditer(text):
        token = (m.group(1) + m.group(2)).strip()
        s = m.start()
        if _near_category(text, s, distance=8):
            for cat, keys in CAT_MAP.items():
                left = text[max(0, s-12):s]
                if any(k in left for k in keys):
                    by_cat.setdefault(cat, [])
                    if token not in by_cat[cat]: by_cat[cat].append(token)
                    break
        else:
            if token not in globals_: globals_.append(token)
    return globals_, by_cat

BOUNDARY_PUNC_RE = re.compile(r'[\.!\?;,\n]')
CAT_BOUNDARY_RE  = CAT_BOUNDARY_RE  # reuse

def _window_after_keyword(text: str, start_idx: int, max_len: int = 40) -> str:
    end_limit = min(len(text), start_idx + max_len)
    punc_m = BOUNDARY_PUNC_RE.search(text, pos=start_idx, endpos=end_limit)
    punc_idx = punc_m.start() if punc_m else None
    cat_m = CAT_BOUNDARY_RE.search(text, pos=start_idx, endpos=end_limit)
    cat_idx = cat_m.start() if cat_m else None
    candidates = [i for i in [punc_idx, cat_idx] if i is not None]
    cut = min(candidates) if candidates else end_limit
    return text[start_idx:cut]

def parse_category_budgets(text: str):
    results: List[Dict[str, Any]] = []
    errors:  List[Dict[str, Any]] = []
    for cat, keys in CAT_MAP.items():
        for k in keys:
            for m in re.finditer(re.escape(k), text):
                window = _window_after_keyword(text, m.end(), max_len=40)
                lo, hi, kind = parse_amount_block(window)
                if lo is None and hi is None: continue
                if kind == "single":
                    v = lo; lo = max(0, v*0.9); hi = v*1.1
                floor = MIN_REQ_MANWON.get(cat)
                if floor is not None:
                    too_low = ((hi is not None and hi < floor) or
                               (hi is None and lo is not None and lo < floor) or
                               (lo is not None and hi is not None and hi < floor))
                    if too_low:
                        errors.append({"code":"min_too_low","category":cat})
                        continue
                    if lo is not None and lo < floor: lo = floor
                results.append({"category":cat,
                                "min_manwon": None if lo is None else round(lo),
                                "max_manwon": None if hi is None else round(hi),
                                "matched": k, "kind": kind})
    by_cat: Dict[str, Dict[str, Any]] = {}
    for r in results: by_cat[r["category"]] = r
    return list(by_cat.values()), errors

def detect_wedding_event(text: str, dates: List[str]):
    if any(kw in text for kw in EVENT_WEDDING) and dates:
        return {"type":"wedding","date":dates[0]}
    return None

def parse_text(text: str):
    text_norm = re.sub(r'\s+', ' ', text.strip())
    dates = parse_dates(text_norm)
    global_regions, category_regions = parse_regions_scoped(text_norm)
    budgets, errors = parse_category_budgets(text_norm)
    wedding = detect_wedding_event(text_norm, dates)
    return {
        "dates": dates,
        "regions": global_regions,
        "category_regions": category_regions,
        "budgets": budgets,
        "events": [wedding] if wedding else [],
        "errors": errors
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["parse"])
    ap.add_argument("--text"); ap.add_argument("--file")
    args = ap.parse_args()
    if args.mode == "parse":
        text = open(args.file,"r",encoding="utf-8").read() if args.file else (args.text or "")
        print(json.dumps(parse_text(text), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
