"""로그온 시 워커가 자동 실행되도록 시작프로그램(Startup) 폴더에 등록. (관리자 권한 불필요)

실행:
    python install_autostart.py

동작:
    - 시작프로그램 폴더에 TossWorker.vbs 를 만들어(이 폴더 경로를 절대경로로 박아) 등록
    - 지금 바로 워커도 한 번 실행

해제:
    시작프로그램 폴더의 TossWorker.vbs 삭제
    (열기: 실행창(Win+R) 에 shell:startup)
"""

import os
import subprocess
from pathlib import Path

APP = Path(__file__).resolve().parent
PYW = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python314\pythonw.exe")
SERVICE = APP / "_worker_service.py"
STARTUP_DIR = Path(os.path.expandvars(
    r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"))
TARGET = STARTUP_DIR / "TossWorker.vbs"

if not Path(PYW).is_file():
    print(f"[경고] pythonw.exe 를 찾지 못함: {PYW}")
    print("       Python 3.14 를 현재 사용자용으로 설치했는지 확인하세요.")

vbs = (
    'Set sh = CreateObject("WScript.Shell")\r\n'
    f'sh.CurrentDirectory = "{APP}"\r\n'
    f'sh.Run """{PYW}"" ""{SERVICE}""", 0, False\r\n'
)
STARTUP_DIR.mkdir(parents=True, exist_ok=True)
TARGET.write_text(vbs, encoding="utf-8")
print(f"[OK] 자동 실행 등록: {TARGET}")

subprocess.Popen(["wscript.exe", str(TARGET)])
print(f"[OK] 워커를 지금 시작했습니다. 로그: {APP / 'worker.log'}")
