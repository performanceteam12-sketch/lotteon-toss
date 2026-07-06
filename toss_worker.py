"""토스 재수집 로컬 워커.

토스 로그인된 Chrome이 있는 PC에서 상시 실행한다.
구글시트 큐를 주기적으로 확인하여 pending 작업을 스크래핑·업데이트한다.

핵심 안전장치(preflight):
    워커는 작업을 잡기 전에 "실제로 스크래핑이 가능한 상태인가"를 스스로 점검한다.
    (uv 실행 가능 + browser-harness 실행 가능) 점검에 실패하면 **작업을 잡지 않고**
    정상 워커에게 양보한다. → 불완전 세팅(예: uv 미설치) 워커가 큐를 가로채
    WinError 2 로 실패시키는 것을 방지한다. 세팅이 완료되면 자동으로 복귀한다.

실행:
    python toss_worker.py

필요 조건:
    - 이 PC의 Chrome에 토스 광고 플랫폼 로그인
    - Python 라이브러리 설치 + uv 설치 + browser-harness (uv sync)
    - 서비스계정 키 (GCP_SA_JSON 환경변수 또는 toss_update_bot.SA_FILE)
"""

import os
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime

from toss_update_bot import _client, run_pipeline, SPREADSHEET_ID, _uv_exe, BH_PROJECT
from toss_queue import find_pending, update_job

POLL_INTERVAL = 10           # 초 — 큐 확인 주기
HEALTHCHECK_INTERVAL = 300   # 초 — 사전 점검 재실행 주기(5분). 세팅 완료 시 자동 복귀용.

# Windows에서 subprocess 자식 프로세스의 콘솔 창(검은 창)이 깜빡이지 않도록 숨김.
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def preflight() -> tuple[bool, str]:
    """이 워커가 실제로 토스 스크래핑을 수행할 수 있는지 사전 점검.

    실패하면 워커는 작업을 잡지 않는다(정상 워커에 양보). 불완전 세팅 워커가
    큐를 오염시키는 것을 막는 안전장치.
    """
    uv = _uv_exe()
    # 1) uv 실행 파일 자체가 없으면 스크래핑 불가
    if uv == "uv" and shutil.which("uv") is None:
        return False, "uv 실행 파일 없음 (uv 미설치)"
    # 2) browser-harness 프로젝트 폴더 확인
    if not os.path.isdir(BH_PROJECT):
        return False, f"browser-harness 폴더 없음: {BH_PROJECT}"
    # 3) uv 로 browser-harness 가 실제로 실행되는지 (venv/의존성까지 검증). Chrome엔 붙지 않음.
    try:
        r = subprocess.run(
            [uv, "run", "--project", BH_PROJECT, "browser-harness", "--version"],
            capture_output=True, text=True, timeout=90, creationflags=_NO_WINDOW,
        )
    except FileNotFoundError:
        return False, "uv 실행 불가 (경로 오류)"
    except Exception as e:
        return False, f"점검 중 오류: {e}"
    if r.returncode != 0:
        tail = (r.stderr.strip().splitlines() or [""])[-1]
        return False, f"browser-harness 실행 실패: {tail}"
    return True, "OK"


def process_job(client, sh, job: dict):
    row = job["row"]
    jid = job["job_id"]
    start = job["start"]
    end = job["end"]

    log(f"▶ 작업 시작 {jid} ({start} ~ {end})")
    update_job(sh, row, "running", "워커 실행 중...")

    logs = []
    def collect(m):
        logs.append(m)
        log(f"   {m}")

    try:
        # start/end는 문자열 → date 변환
        from datetime import datetime as dt
        s = dt.strptime(start, "%Y-%m-%d").date()
        e = dt.strptime(end, "%Y-%m-%d").date()
        result = run_pipeline(s, e, use_toss=True, client=client, log=collect)
        msg = f"완료: 소재행 {len(result['sojaebang'])}개, 삭제 {result['deleted']}개"
        update_job(sh, row, "done", msg)
        log(f"✔ 작업 완료 {jid} — {msg}")
    except Exception as exc:
        err = f"{exc}\n{traceback.format_exc()}"
        update_job(sh, row, "error", str(exc))
        log(f"✖ 작업 실패 {jid}: {exc}")


def main():
    log("토스 워커 시작. (Ctrl+C로 종료)")
    client = _client()
    sh = client.open_by_key(SPREADSHEET_ID)

    healthy = False
    last_check = None
    while True:
        try:
            now = time.monotonic()
            if last_check is None or (now - last_check) >= HEALTHCHECK_INTERVAL:
                ok, reason = preflight()
                if ok and not healthy:
                    log("✅ 사전점검 통과 — 작업 처리 가능")
                elif not ok:
                    log(f"⛔ 사전점검 실패({reason}) — 작업을 잡지 않고 대기. "
                        f"세팅(uv 설치/uv sync)이 끝나면 자동 복귀합니다.")
                healthy = ok
                last_check = now

            if healthy:
                pending = find_pending(sh, mode="toss")
                for job in pending:
                    process_job(client, sh, job)
            # 사전점검 실패 시 find_pending 을 호출하지 않음 → 작업을 잡지 않는다.
        except Exception as exc:
            log(f"⚠ 폴링 오류: {exc}")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
