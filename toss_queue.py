"""재수집 작업 큐 (구글시트 기반).

Streamlit Cloud 대시보드가 작업을 enqueue하고,
로컬 워커(toss_worker.py)가 polling하여 실행한다.

큐 시트 컬럼:
    A: job_id        — 작업 ID (타임스탬프 기반)
    B: start_date    — 시작 날짜 (YYYY-MM-DD)
    C: end_date      — 종료 날짜 (YYYY-MM-DD)
    D: mode          — "toss" (토스 대시보드 재수집)
    E: status        — pending / running / done / error
    F: message       — 결과 메시지 또는 에러
    G: created_at    — 생성 시각
    H: updated_at    — 갱신 시각
"""

from __future__ import annotations

from datetime import datetime

import gspread

QUEUE_SHEET = "재수집큐"
QUEUE_HEADER = ["job_id", "start_date", "end_date", "mode",
                "status", "message", "created_at", "updated_at"]


def ensure_queue_sheet(sh) -> gspread.Worksheet:
    """큐 시트가 없으면 생성하고 헤더를 채운다."""
    try:
        ws = sh.worksheet(QUEUE_SHEET)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=QUEUE_SHEET, rows=200, cols=len(QUEUE_HEADER))
        ws.update("A1", [QUEUE_HEADER])
    return ws


def enqueue(sh, start: str, end: str, mode: str = "toss") -> str:
    """작업을 큐에 추가하고 job_id를 반환."""
    ws = ensure_queue_sheet(sh)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    job_id = datetime.now().strftime("%Y%m%d%H%M%S")
    ws.append_row(
        [job_id, start, end, mode, "pending", "", now, now],
        value_input_option="USER_ENTERED",
    )
    return job_id


def get_job(sh, job_id: str) -> dict | None:
    """job_id로 작업 상태를 조회."""
    ws = ensure_queue_sheet(sh)
    rows = ws.get_all_values()
    for i, row in enumerate(rows[1:], start=2):
        if row and row[0] == job_id:
            return {
                "row": i,
                "job_id": row[0],
                "start": row[1],
                "end": row[2],
                "mode": row[3],
                "status": row[4],
                "message": row[5] if len(row) > 5 else "",
            }
    return None


def find_pending(sh, mode: str = "toss") -> list[dict]:
    """pending 상태의 작업 목록 반환 (워커용)."""
    ws = ensure_queue_sheet(sh)
    rows = ws.get_all_values()
    out = []
    for i, row in enumerate(rows[1:], start=2):
        if len(row) >= 5 and row[3] == mode and row[4] == "pending":
            out.append({
                "row": i,
                "job_id": row[0],
                "start": row[1],
                "end": row[2],
                "mode": row[3],
                "status": row[4],
            })
    return out


def update_job(sh, row: int, status: str, message: str = "") -> None:
    """작업 상태 갱신 (E:status, F:message, H:updated_at). created_at(G)은 보존."""
    ws = ensure_queue_sheet(sh)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ws.update(f"E{row}:F{row}", [[status, message[:5000]]],
              value_input_option="USER_ENTERED")
    ws.update(f"H{row}", [[now]], value_input_option="USER_ENTERED")
