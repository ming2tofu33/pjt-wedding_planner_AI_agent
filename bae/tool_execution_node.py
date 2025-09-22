# 목적: router가 지정한 툴을 실행하고, 결과를 State에 누적
from typing import List
from state_mvp import State
from db_query_tool import db_query_tool

def tool_execution_node(state: State) -> State:
    """
    - 현재 MVP에선 db_query_tool만 사용.
    - router가 tools_to_execute에 'db_query_tool'을 넣어줬다면 실행.
    - 결과는 state.rows에 누적하고 status/reason을 세팅.
    """
    try:
        executed: List[str] = []

        if "db_query_tool" in (state.tools_to_execute or []):
            if not state.vendor_type:
                # 안전 가드: vendor_type이 없으면 실행 불가
                state.status = "empty"
                state.reason = "[tool_exec] vendor_type가 없어 검색을 진행할 수 없습니다."
                return state

            results = db_query_tool(
                vendor_type=state.vendor_type,
                region_keyword=state.region_keyword,
                limit=state.limit or 5,
            )
            state.rows.extend(results)
            executed.append("db_query_tool")

        # 실행 결과에 따른 상태
        if executed and len(state.rows) > 0:
            state.status = "ok"
            state.reason = f"[tool_exec] {', '.join(executed)}: {len(state.rows)}건"
        elif executed and len(state.rows) == 0:
            state.status = "empty"
            state.reason = f"[tool_exec] 결과가 없습니다. (vendor={state.vendor_type}, region={state.region_keyword})"
        else:
            # 실행할 툴이 없었음
            state.status = "empty"
            state.reason = "[tool_exec] 실행할 툴이 없습니다."

        return state

    except Exception as e:
        state.status = "error"
        state.reason = f"[tool_exec] 실패: {e}"
        return state