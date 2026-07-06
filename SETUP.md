# 토스 대시보드 재수집 — 워커 PC 세팅 가이드

이 패키지로 새 PC를 "토스 재수집 워커"로 만들 수 있습니다.
**GitHub 저장소는 필요 없습니다.** 오늘까지의 버그 픽스 + 안전장치가 모두 반영돼 있습니다.

> 보안: 이 패키지에는 **서비스계정 키가 들어있지 않습니다.** 키 파일은 따로 받아서
> (아래 5단계) 환경변수로 연결합니다. → 패키지가 유출돼도 키는 안전합니다.

---

## 0. 구조 (왜 워커 PC가 필요한가)

```
[클라우드] 대시보드 "토스 대시보드 재수집" 클릭
   └─ 구글시트 "재수집큐"에 작업만 등록하고 대기
                     ▲
[워커 PC] 워커가 큐를 확인 → 이 PC의 Chrome으로 토스 스크래핑 → 시트 업데이트
```

워커 PC는 **항상 켜져 있고 + Chrome이 토스에 로그인**돼 있어야 합니다.

### ★ 중요: 워커는 한 곳만 "정상"이면 됩니다
큐는 여러 PC가 공유하고, **먼저 잡는 워커가 처리**합니다. 그래서 **세팅이 불완전한(고장난) 워커가
섞이면 그게 작업을 가로채 실패**시킵니다. 이 버전에는 안전장치가 있어, **스크래핑이 불가능한 워커는
작업을 잡지 않고 정상 워커에 양보**합니다. 단 그 안전장치는 이 최신 코드를 쓰는 워커에만 적용됩니다
→ **워커 돌리는 모든 사람이 이 최신 패키지를 써야** 합니다. 옛 버전 워커는 반드시 종료/업데이트하세요.

---

## 1. 압축 풀기
원하는 위치에 풀기 (경로 자유). 예) `C:\toss-worker\`
```
lotteon-toss-portable\
├── app\               (워커 코드 + 런처)
└── browser-harness\   (스크래핑 엔진)
```

## 2. Python & uv 설치 (한 번, 관리자 권한 불필요)
PowerShell 에서:
```powershell
winget install --id Python.Python.3.14 --scope user -e --accept-package-agreements --accept-source-agreements
winget install --id astral-sh.uv -e --accept-package-agreements --accept-source-agreements
```
설치 후 PowerShell 창을 **새로** 여세요. (uv 공식 문서: https://docs.astral.sh/uv/)

## 3. 워커 라이브러리 설치 — app 폴더에서
```powershell
"$env:LOCALAPPDATA\Programs\Python\Python314\python.exe" -m pip install -r requirements.txt
```

## 4. browser-harness 준비 — browser-harness 폴더에서
```powershell
uv sync
```
> 폴더 복사 + `uv sync` 면 충분합니다(별도 "정식 설치" 불필요). uv 가 설치돼 있어야 합니다.

## 5. 서비스계정 키 연결 (env 방식)
1. 키 파일 `uploading-raw-data-...json` 을 이 PC 어딘가에 복사 (예: `C:\toss-worker\sa_key.json`)
2. 경로를 환경변수로 등록:
```powershell
setx TOSS_SA_FILE "C:\toss-worker\sa_key.json"
```

## 6. browser-harness 경로 지정 (선택)
패키지 구조 그대로면 자동 인식되지만, 명시하려면:
```powershell
setx BH_PROJECT "C:\toss-worker\lotteon-toss-portable\browser-harness"
```
> setx 로 바꾼 값은 **새 PowerShell 창부터** 적용됩니다.

## 7. Chrome 원격 디버깅 + 토스 로그인 (한 번)
평소 Chrome에서:
1. 주소창: `chrome://inspect/#remote-debugging` → **"Allow remote debugging for this browser instance"** 체크
2. 토스 광고 플랫폼(ads-platform.toss.im) 로그인 유지
> 처음 스크래핑 시 "Allow remote debugging?" 팝업 → Allow 클릭.

## 8. 워커 자동 실행 등록 (택1)
- **권장(관리자 권한 불필요):** app 폴더에서
  ```powershell
  "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe" install_autostart.py
  ```
- 또는(관리자 권한 필요, 작업 스케줄러): `register_worker_local.ps1` 을 관리자 PowerShell로 실행.
- 수동으로 켜기: `run_worker_local.bat` 더블클릭(검은 창=실행 중).

로그: app 폴더의 `worker.log`. 정상이면 `✅ 사전점검 통과` 가 찍힙니다.

---

## 9. 사용 (매번)
1. Chrome 켜고 토스 로그인 확인
2. 대시보드에서 "토스 대시보드 재수집" 클릭
   → https://lotteon-toss-update.streamlit.app/  (에러 화면이 남으면 `?r=1` 없는 기본 주소로)

---

## 10. 기존(옛) 워커 PC 정리 — 새 워커 정상 확인 후
옛 PC에서 워커를 끄고 자동실행 제거(안 그러면 그게 작업을 가로챕니다):
```powershell
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'toss_worker|_worker_service|_launch_worker' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Get-ScheduledTask -TaskName "TossWorker" -ErrorAction SilentlyContinue | Unregister-ScheduledTask -Confirm:$false
```
그리고 `Win+R` → `shell:startup` → 토스/worker 관련 파일(.lnk/.vbs) 삭제.

---

## 문제 해결
| 증상 | 해결 |
|---|---|
| "워커 응답 시간 초과" | 정상 워커가 안 켜짐 → 워커 실행/자동등록 확인 |
| "캠페인 데이터가 없습니다" | Chrome 토스 로그인 풀림 → 재로그인 |
| "[WinError 2]" 가 계속 뜸 | **옛 버전 워커가 다른 PC에서 작업을 가로채는 중** → 그 PC 워커 종료(10번) |
| worker.log에 `사전점검 실패` | uv 미설치 / `uv sync` 안 함 → 2·4단계 확인 (이 워커는 작업 안 잡고 대기) |

## 보안
서비스계정 키(`sa_key.json`)는 이 패키지에 없습니다. 별도로 안전하게 전달받아 5단계로 연결하세요.
공개 저장소(GitHub 등)에 키를 올리지 마세요.
