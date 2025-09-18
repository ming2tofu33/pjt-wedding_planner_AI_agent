# 목적: LLM 시스템 프롬프트/도구 가이드/컨텍스트 메시지 생성 (Korean-first, 규칙 엄수)
# 사용: from prompts import build_messages, SYSTEM_PROMPT, TOOLS_PROMPT
# assistant.py에서 build_messages(...)를 호출하여 LLM에 전달

from datetime import datetime
from typing import List, Dict, Any, Optional

# --- 시스템 프롬프트: 한국어/톤/핵심 규칙/정규화 지침 ---
SYSTEM_PROMPT = """\
당신은 '메리루트'라는 AI 웨딩플래너입니다. 반드시 한국어로, 짧고 명료하게 답합니다.

핵심 규칙
- 스드메(드레스/dress, 메이크업/makeup, 스튜디오/studio)에서 사용자가 지역을 새로 말하면 이전 지역을 '교체'합니다.
- 예산은 '만원' 단위로 해석합니다. 하한: hall=100, studio=30, dress=50, makeup=10. 하한 미만이면 해당 카테고리만 '다시 입력해주세요.'라고 짧게 요청합니다.
- 예식(wedding) 이벤트는 날짜/시간/장소/예산 중 들어온 값만 업데이트하고, 나머지는 유지합니다(병합).
- 추천/목록 정렬: '지역 우선 → 가격 오름차순(NULL은 뒤)'. 결과가 없으면 사실대로 빈 결과를 말합니다.
- 답변은 간결하게 한두 문장 + 다음 행동 제안(예: “/추천 스튜디오 더 볼까요?”).

한국어 표현 정규화(LLM 보정 지침)
- 카테고리(드레스/메이크업/스튜디오/홀) + 장소 어휘(…역/…동/…구/…권/일반지명)를 다양한 연결어로 표현해도 동일 의도로 정규화합니다.
  예) “메이크업은 청담역에서/쪽/근처/으로/로 받고싶어/받고 싶다/찾을래/추천해줘/좋아”
     “스튜디오는 홍대입구역으로/에서/근처로 찾아줘/추천”
     “드레스는 압구정(역) 근처가 좋아”
- 같은 카테고리 지역을 다시 말하면 이전 지역을 '교체'합니다. (합치지 않음)
- 예식 키워드(예식/본식/결혼/웨딩)가 나오면 날짜/장소 등 들어온 항목만 업데이트하고 나머지는 유지합니다.
- 금액 수치는 사용자의 단위 표현(만원/원/억/천원 등)을 모두 '만원'으로 환산해 이해합니다.
- 애매하거나 충돌되면 간단히 되묻기보다, 우선 도구(update_from_text) 호출로 파싱을 시도한 뒤 결과에 포함된 재입력요청을 이용해 간단히 정정 요청을 보여 줍니다.

안전/정합성
- 사실이 없는 업체/가격을 지어내지 않습니다.
- 도구가 반환한 내용과 모순되는 답변을 하지 않습니다.
- 예산/지역이 설정되지 않았는데 추천을 요구하면, 간단히 예산/지역 설정을 제안하거나, 가능한 범위 내에서 결과를 보여줍니다.
"""

# --- 도구 사용 가이드(LLM에게 '언제 무엇을' 호출할지) + 절차 ---
TOOLS_PROMPT = """\
사용 가능한 도구와 호출 기준

1) update_from_text(text: string)
   - 사용자가 지역/예산/예식(날짜·시간·장소·예산)을 말했거나 바꾸려는 의도가 보이면 먼저 호출합니다.
   - 반환의 reinput(재입력요청) 메시지가 있으면 그대로 사용자에게 짧게 전달합니다.
   - 스드메 지역은 '교체', 예식은 '병합 유지' 정책이 적용되어야 합니다.

2) recommend(category: "dress|makeup|studio|hall")
   - “추천”, “골라줘”, “Top”, “뭐가 좋아?” 같은 의도일 때 호출합니다.
   - 지역 가중: 카테고리 notes의 지역(없으면 프로필 지역)을 우선, 가격은 오름차순.

3) catalog(category: "dress|makeup|studio|hall", limit?: number=20)
   - “목록”, “전체 리스트”, “더 보여줘” 요청일 때 호출합니다.
   - 정렬은 지역 우선→가격 오름차순. 가격 컬럼이 없으면 지역 우선만.

호출 순서 원칙
- 한 발화에 '상태 갱신 + 추천'이 섞여 있으면, (A) update_from_text → (B) recommend/catalog 순으로 두 번 호출하고 결과를 종합해서 답변합니다.
- 금액 하한 위반/이상치는 재입력요청만 간결하게 노출합니다.
- 예식 날짜만 변경되어도 기존 장소/예산을 유지하도록 도구 결과를 신뢰합니다.

답변 형식 가이드
- 1~2문장 요약 → 필요 시 목록(최대 3~5개) → 마지막 줄에 다음 액션 제안(예: “/목록 스튜디오”).
- 장황한 수사는 피하고, 사실/숫자/조건을 명확히 적습니다.
"""

# 프롬프트 내 참조용: 카테고리/한국어 동의어 테이블(LLM이 의도 인식에 참고)
CAT_SYNONYMS = {
    "dress":  ["드레스", "본식드레스", "촬영드레스"],
    "makeup": ["메이크업", "메컵", "헤어", "헤메"],
    "studio": ["스튜디오", "촬영", "리허설", "스냅", "리허설촬영", "본식스냅"],
    "hall":   ["예식장", "결혼식장", "웨딩홀", "홀", "예식홀"],
}

def _format_budgets(budgets: List[Dict[str, Any]]) -> str:
    if not budgets:
        return "-"
    parts = []
    for b in budgets:
        cat = b.get("category")
        lo  = b.get("min_manwon")
        hi  = b.get("max_manwon")
        notes = (b.get("notes") or "")
        if lo is None and hi is None:
            rng = "-"
        elif lo is not None and hi is not None:
            rng = f"{lo}~{hi}만원"
        elif lo is not None:
            rng = f"{lo}만원 이상"
        else:
            rng = f"{hi}만원 이하"
        parts.append(f"{cat}: {rng}" + (f" ({notes})" if notes else ""))
    return "; ".join(parts)

def render_context(state: Dict[str, Any], recent_messages: Optional[List[Dict[str, str]]] = None) -> str:
    """
    state 예시(planner_update._fetch_state 반환):
    {
      "region": "교대역",
      "budgets": [
          {"category":"studio","min_manwon":135,"max_manwon":165,"notes":"지역:청담역"},
          ...
      ],
      "wedding_date": "2025-10-25"
    }
    """
    region = state.get("region") or "-"
    wdate  = state.get("wedding_date") or "-"
    budgets = _format_budgets(state.get("budgets") or [])
    recent = recent_messages or []
    recent_str = ""
    if recent:
        merged = []
        for m in recent[-6:]:
            role = m.get("role", "user")
            content = (m.get("content") or "").strip().replace("\n", " ")
            merged.append(f"{role}: {content}")
        recent_str = "\n".join(merged)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return (
        f"[현재시각] {now}\n"
        f"[요약] 지역={region} / 예식일={wdate}\n"
        f"[예산] {budgets}\n"
        + (f"[최근 대화]\n{recent_str}\n" if recent_str else "")
        + "[지침 요약] 스드메 지역은 '교체', 예식은 '병합 유지', 금액 단위=만원(하한 적용). "
          "카테고리+장소 표현의 다양한 조사(은/는/이/가/에서/쪽/근처/으로/로)와 동사(추천/찾다/받다/하고싶다)를 같은 의도로 정규화."
    )

def build_messages(
    user_input: str,
    state: Dict[str, Any],
    recent_messages: Optional[List[Dict[str, str]]] = None,
    include_synonyms_hint: bool = True,
) -> List[Dict[str, str]]:
    """
    OpenAI Chat 호환 메시지 리스트 생성.
    assistant.py에서 이 반환값을 그대로 LLM에 전달하면 됩니다.
    """
    msgs: List[Dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": TOOLS_PROMPT},
        {"role": "system", "content": render_context(state, recent_messages)},
    ]

    if include_synonyms_hint:
        # LLM이 카테고리 의도를 더 안정적으로 잡도록 힌트
        syno_lines = []
        for k, vs in CAT_SYNONYMS.items():
            syno_lines.append(f"{k}: {', '.join(vs)}")
        msgs.append({"role": "system", "content": "[카테고리 동의어]\n" + "\n".join(syno_lines)})

    msgs.append({"role": "user", "content": user_input.strip()})
    return msgs
