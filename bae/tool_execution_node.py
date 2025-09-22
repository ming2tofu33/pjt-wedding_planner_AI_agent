# 목적: router가 지정한 툴을 실행하고, 결과를 State에 누적
from typing import List, Dict, Any
from state_mvp import State
from db_query_tool import db_query_tool

def _clamp_limit(n) -> int:
    try:
        i = int(n)
    except Exception:
        i = 5
    return max(1, min(i, 20))

def tool_execution_node(state: State) -> State:
    """
    - 현재 MVP에선 db_query_tool만 사용.
    - router가 tools_to_execute에 'db_query_tool'을 넣어줬다면 실행.
    - 결과는 state.rows에 누적하고 status/reason을 세팅.
    """
    try:
        executed: List[str] = []

        # rows / tools_to_execute 방어적 초기화
        if not isinstance(state.get("rows"), list):
            state["rows"] = []
        if not isinstance(state.get("tools_to_execute"), list):
            state["tools_to_execute"] = []

        if "db_query_tool" in state["tools_to_execute"]:
            if not state.get("vendor_type"):
                # 안전 가드: vendor_type이 없으면 실행 불가
                state["status"] = "empty"
                state["reason"] = "[tool_exec] vendor_type가 없어 검색을 진행할 수 없습니다."
                return state

            limit = _clamp_limit(state.get("limit") or 5)
            results = db_query_tool(
                vendor_type=state["vendor_type"],
                region_keyword=state.get("region_keyword"),
                limit=limit,
            ) or []  # None 방지

            # 결과 타입 보정
            if not isinstance(results, list):
                results = []

            # (선택) 레코드 형 통일 최소 보정
            normed: List[Dict[str, Any]] = []
            for r in results:
                if isinstance(r, dict):
                    normed.append(r)
            results = normed

            state["rows"] = (state.get("rows") or []) + results
            executed.append("db_query_tool")

        # 실행 결과에 따른 상태
        current_rows = state.get("rows", [])
        if executed and len(current_rows) > 0:
            state["status"] = "ok"
            state["reason"] = f"[tool_exec] {', '.join(executed)}: {len(current_rows)}건"
        elif executed and len(current_rows) == 0:
            state["status"] = "empty"
            state["reason"] = f"[tool_exec] 결과가 없습니다. (vendor={state.get('vendor_type')}, region={state.get('region_keyword')})"
        else:
            # 실행할 툴이 없었음 (라우터 설정 이슈)
            state["status"] = "empty"
            state["reason"] = "[tool_exec] 실행할 툴이 없습니다."

        return state

    except Exception as e:
        state["status"] = "error"
        state["reason"] = f"[tool_exec] 실패: {e}"
        return state
