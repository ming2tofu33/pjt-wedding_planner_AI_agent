# 목적: 기존 사용자의 메모(JSON)를 로드하고, 없으면 초기 메모를 생성해 State에 주입
import json
import uuid 
from datetime import datetime
from typing import Optional

from state_mvp import (
    State,
    create_empty_user_memo,
    get_memo_file_path,
)

def _ensure_user_id(state: State) -> str:
    """
    user_id가 없으면 UUID 기반 임시 ID를 생성.
    - 프로덕션에선 로그인/쿠키/디바이스ID 등으로 대체 가능.
    """
    if state.user_id:
        return state.user_id
    generated = f"user-{uuid.uuid4().hex}"
    state.user_id = generated
    return generated

def _load_json(path: str) -> Optional[dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception:
        # 손상/권한 등의 이유로 실패 시 None 반환 → 새로 생성
        return None

def _save_json(path: str, data: dict) -> bool:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

def memo_check_node(state: State) -> State:
    """
    기존 사용자의 메모를 확인하고 컨텍스트를 로드합니다.
    - user_id가 없으면 UUID로 생성
    - 메모 파일이 있으면 로드, 없거나 손상이면 새 메모 생성
    - state.user_memo / memo_file_path / memo_load_success 세팅
    - 편의상 conversation_summary를 state.conversation_summary로 반영
    """
    try:
        uid = _ensure_user_id(state)
        memo_path = get_memo_file_path(uid)
        state.memo_file_path = memo_path

        memo = _load_json(memo_path)
        created_new = False

        if not memo:
            memo = create_empty_user_memo(uid)
            created_new = True
            # 바로 저장까지(폴더는 get_memo_file_path에서 보장됨)
            _save_json(memo_path, memo)

        # 상태에 주입
        state.user_memo = memo  # type: ignore[assignment]
        state.memo_load_success = True
        state.memo_needs_update = False  # 방금 로드했으므로 초기엔 False

        # 대화 요약본 편의 반영
        state.conversation_summary = (memo.get("conversation_summary")
                                      if isinstance(memo, dict) else None)

        # 상태/로그용 텍스트(선택)
        created_or_loaded = "created" if created_new else "loaded"
        state.status = "ok"
        state.reason = None
        state.response_content = f"[memo_check] {created_or_loaded} memo for user_id={uid}"

        return state

    except Exception as e:
        # 치명적이어도 다운시키지 않고 빈 메모로 복구
        if not state.user_id:
            state.user_id = f"user-{uuid.uuid4().hex}"  
        uid = state.user_id
        memo_path = get_memo_file_path(uid)
        state.memo_file_path = memo_path

        fallback = create_empty_user_memo(uid)
        state.user_memo = fallback  # type: ignore[assignment]
        state.memo_load_success = False
        state.memo_needs_update = True  # 복구 저장 필요

        state.status = "error"
        state.reason = f"memo_check_node 실패: {e}"
        return state
