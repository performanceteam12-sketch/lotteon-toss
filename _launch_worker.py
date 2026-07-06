"""로컬 워커 실행 런처 (환경 설정 후 워커 실행).

환경변수(setx 로 지정한 값)를 **존중**한다. 즉:
  - TOSS_SA_FILE / GCP_SA_JSON 이 이미 있으면 그대로 사용(키를 패키지 밖에 두는 방식).
  - BH_PROJECT 가 이미 있으면 그대로 사용.
아무것도 지정 안 했을 때만, 이 폴더의 sa_key.json(있으면) / 형제 browser-harness 를 폴백으로 쓴다.
run_worker_local.bat / _worker_service.py 가 이 파일을 쓴다.
"""

import os
from pathlib import Path

_HERE = Path(__file__).resolve().parent

# 1) 서비스계정 키: env(GCP_SA_JSON/TOSS_SA_FILE)가 없을 때만 번들 sa_key.json 폴백
if not os.environ.get("GCP_SA_JSON") and not os.environ.get("TOSS_SA_FILE"):
    _KEY = _HERE / "sa_key.json"
    if _KEY.is_file():
        os.environ["GCP_SA_JSON"] = _KEY.read_text(encoding="utf-8")

# 2) browser-harness 경로: env(BH_PROJECT)가 없을 때만 형제 폴더 폴백
if not os.environ.get("BH_PROJECT"):
    _BH = _HERE.parent / "browser-harness"
    if _BH.is_dir():
        os.environ["BH_PROJECT"] = str(_BH)

# 3) uv 설치 경로(winget 기본 위치)를 PATH 앞에 보장 → subprocess의 bare `uv` 대비
_UV_DIR = os.path.expandvars(
    r"%LOCALAPPDATA%\Microsoft\WinGet\Packages"
    r"\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe"
)
if os.path.isdir(_UV_DIR) and _UV_DIR not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _UV_DIR + os.pathsep + os.environ.get("PATH", "")

import toss_worker

if __name__ == "__main__":
    toss_worker.main()
