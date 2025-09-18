# 목적: 한국어 한 문장에서 날짜/시간/장소/예산/카테고리 지역을 파싱하여 구조화
# 공개 함수:
#   - parse_text(text) -> {dates, regions, category_regions, budgets, events, errors}

import re, math
from typing import Dict, Any, List, Optional, Tuple

# 카테고리 동의어
CAT_MAP = {
    "dress":  ["드레스", "본식드레스", "촬영드레스"],
    "makeup": ["메이크업", "메컵", "헤어", "헤메"],
    "studio": ["스튜디오", "촬영", "리허설", "스냅", "리허설촬영", "본식스냅"],
    "hall":   ["예식장", "결혼식장", "웨딩홀", "홀", "예식홀"],
}
EVENT_WEDDING = ["본식", "예식", "결혼식", "웨딩", "결혼"]

# 장소 조사/부사 꼬리 제거
_LOC_TAIL = r"(에서|으로|로|에|쪽|근처)$"
def _clean_loc(s: Optional[str]) -> Optional[str]:
    if not s: return s
    return re.sub(rf"\s*{_LOC_TAIL}", "", s.strip()).strip()

# --- 카테고리 토큰 찾기
def _find_category_tokens(text: str) -> Dict[str, bool]:
    low = text.lower()
    found = {k: False for k in CAT_MAP.keys()}
    for k, syns in CAT_MAP.items():
        if k in low:
            found[k] = True
            continue
        for s in syns:
            if s in text:
                found[k] = True
                break
    return found

# --- 지역 후보 추출(“…역/…동/…구/…권”)
REGEX_REGION = re.compile(r"([가-힣A-Za-z0-9]{2,}(?:역|동|구|권))")
def _extract_regions(text: str) -> List[str]:
    regs = []
    for m in REGEX_REGION.finditer(text):
        val = _clean_loc(m.group(1))
        if val and val not in regs:
            regs.append(val)
    return regs

# --- 카테고리별 지역(주요 경로: 카테고리 ~ 20자 이내에 지역 후보)
def _extract_category_regions_primary(text: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for cat, syns in CAT_MAP.items():
        patt = rf"(?:{cat}|" + "|".join(map(re.escape, syns)) + r")(?:(?!\n).){{0,20}}?([가-힣A-Za-z0-9]{{2,}}(?:역|동|구|권))"
        m = re.search(patt, text, flags=re.IGNORECASE)
        if m:
            out[cat] = _clean_loc(m.group(1))
    return out

# --- 숫자/단위 파싱(만원 환산)
def _parse_amount_span(token: str) -> Tuple[Optional[int], Optional[int]]:
    t = token.replace(",", "").strip()
    m = re.match(r"(\d+(?:\.\d+)?)[\s~\-–—]+(\d+(?:\.\d+)?)", t)
    if m:
        a = float(m.group(1)); b = float(m.group(2))
        lo, hi = sorted([a, b])
        return int(round(lo)), int(round(hi))
    m = re.match(r"(\d+(?:\.\d+)?)\s*(이하|이상|이내|초과)", t)
    if m:
        v = float(m.group(1)); u = m.group(2)
        if u in ("이하", "이내"): return (None, int(v // 1))
        else: return (int((v + 0.9999) // 1), None)
    m = re.match(r"(\d+(?:\.\d+)?)$", t)
    if m:
        v = float(m.group(1))
        return (int(round(v)), int(round(v)))
    return (None, None)

def _expand_single_value(cat: str, lo: Optional[int], hi: Optional[int]) -> Tuple[Optional[int], Optional[int]]:
    if lo is not None and hi is not None and lo == hi:
        v = lo
        low = int(v * 0.9 // 1)
        high = int((v * 1.1 + 0.9999) // 1)
        return (low, high)
    return (lo, hi)

def _extract_budgets(text: str) -> List[Dict[str, Any]]:
    budgets: List[Dict[str, Any]] = []
    found = _find_category_tokens(text)
    for cat, present in found.items():
        if not present: continue
        patt = rf"(?:{cat}|" + "|".join(map(re.escape, CAT_MAP[cat])) + r")(?:(?!\n).){{0,20}}?(\d+(?:[.,]\d+)?(?:\s*(?:이하|이상|이내|초과))?|(?:\d+(?:[.,]\d+)?[\s~\-–—]+\d+(?:[.,]\d+)?))"
        m = re.search(patt, text, flags=re.IGNORECASE)
        if not m: 
            continue
        lo, hi = _parse_amount_span(m.group(1))
        lo, hi = _expand_single_value(cat, lo, hi)
        budgets.append({"category": cat, "min_manwon": lo, "max_manwon": hi})
    return budgets

# --- 이벤트(예식) 추출: 날짜/시간/장소 일부만 와도 수집
REGEX_MMDD = re.compile(r"(\d{1,2})\s*[./월]\s*(\d{1,2})\s*(?:일)?")
REGEX_TIME = re.compile(r"(?:오전|오후)?\s*(\d{1,2})(?::(\d{2}))?\s*시?(?:\s*(\d{2})분)?")
# 보조: 조사 포함 일반 지명 캡처 (교대에서/청담에 등)
REGEX_LOC_WITH_PARTICLE = re.compile(r"([가-힣A-Za-z0-9]{2,})\s*(?:에서|으로|로|에|쪽|근처)")

_STOP_WORDS = {"바꿔줘","바꿔","바꾸","해주세요","해줘","추천","목록","더","이하","이상","결혼식","예식","본식","웨딩","날짜","시간"}

def _extract_event(text: str) -> Optional[Dict[str, Any]]:
    if not any(k in text for k in EVENT_WEDDING):
        return None
    date_s: Optional[str] = None
    m = REGEX_MMDD.search(text)
    if m:
        mm, dd = int(m.group(1)), int(m.group(2))
        date_s = f"{mm}/{dd}"
    time_s: Optional[str] = None
    mt = REGEX_TIME.search(text)
    if mt:
        hh = int(mt.group(1))
        mm = int(mt.group(2) or 0)
        time_s = f"{hh:02d}:{mm:02d}"
    # 1순위: 접미어 지역
    regs = _extract_regions(text)
    loc = regs[0] if regs else None
    # 2순위: 조사 붙은 일반 지명 (교대에서 → 교대)
    if not loc:
        m2 = REGEX_LOC_WITH_PARTICLE.search(text)
        if m2:
            cand = _clean_loc(m2.group(1))
            if cand and cand not in _STOP_WORDS:
                # 동사/요청어 말단 방지: 흔한 종결(다/요/줘/해)로 끝나면 버림
                if not re.search(r"(다|요|줘|해|합니다|할거야)$", cand):
                    loc = cand
    if not (date_s or time_s or loc):
        return None
    return {"type": "wedding", "date": date_s, "time": time_s, "location": loc, "budget_manwon": None}

# --- 메인
def parse_text(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    out: Dict[str, Any] = {
        "dates": [], "regions": [], "category_regions": {},
        "budgets": [], "events": [], "errors": []
    }
    if not text:
        return out

    # 일반 지역 후보
    regs = _extract_regions(text)
    out["regions"] = regs

    # 카테고리별 지역 (주요 경로)
    cat_regs = _extract_category_regions_primary(text)

    # Fallback: 카테고리를 언급했고 일반 지역 후보가 있으며, 해당 카테고리에 아직 지역이 없으면 첫 후보를 매핑
    found = _find_category_tokens(text)
    for cat, present in found.items():
        if present and cat not in cat_regs and regs:
            cat_regs[cat] = regs[0]

    out["category_regions"] = cat_regs

    # 예산
    out["budgets"] = _extract_budgets(text)

    # 이벤트(예식)
    ev = _extract_event(text)
    if ev:
        if ev.get("location"):
            ev["location"] = _clean_loc(ev["location"])
        out["events"].append(ev)

    return out
