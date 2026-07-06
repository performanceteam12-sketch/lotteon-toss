"""백그라운드(창 없음) 워커 진입점 — 로그온 자동 실행용.

stdout/stderr 를 이 폴더의 worker.log 로 돌려 창 없이도 상태를 확인할 수 있게 한다.
_launch_worker 를 import 하면 환경 설정(GCP_SA_JSON / BH_PROJECT / uv PATH)이 실행된다.
"""

import sys
from pathlib import Path

_LOG = Path(__file__).resolve().parent / "worker.log"
_f = open(_LOG, "a", encoding="utf-8", buffering=1)
sys.stdout = _f
sys.stderr = _f

import _launch_worker  # noqa: F401  (환경 설정 실행)
import toss_worker

if __name__ == "__main__":
    toss_worker.main()
