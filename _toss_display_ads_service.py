"""백그라운드(창 없음) 토스 디스플레이 광고 스케줄러 진입점 — 로그온 자동 실행용.

stdout/stderr를 이 폴더의 toss_display_ads.log로 돌려 창 없이도 상태를 확인할 수 있게 한다.
"""

import sys
from pathlib import Path

_LOG = Path(__file__).resolve().parent / "toss_display_ads.log"
_f = open(_LOG, "a", encoding="utf-8", buffering=1)
sys.stdout = _f
sys.stderr = _f

import toss_display_ads_scheduler

if __name__ == "__main__":
    toss_display_ads_scheduler.main()
