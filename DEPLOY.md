# 토스 광고비 업데이트 — 배포 가이드

## 전체 구조 (하이브리드)

```
[어디서나] Streamlit Cloud 대시보드
   ├─ 일반 재수집  → 클라우드에서 직접 실행 (토스 로그인 불필요)
   └─ 토스 재수집  → 구글시트 "재수집큐" 탭에 작업 요청 기록
                          ▲
              [사무실 PC] toss_worker.py 가 10초마다 큐 확인
                          → 토스 대시보드 스크래핑 + 예외 비용 보정
                          → 시트 업데이트 → 큐에 결과 기록

[매일 오전 10시] Google Apps Script 트리거 → 어제자 자동 업로드 + 슬랙 알림
```

---

## 1. Streamlit Cloud 배포

### 1-1. GitHub 푸시
이미 `lotteon-toss` 레포에 코드가 있으면 최신 상태로 push.

### 1-2. Streamlit Cloud 앱 생성
1. https://share.streamlit.io 접속 → GitHub 계정 연결
2. **New app** → 레포 `yjhwang-svg/lotteon-toss` 선택
3. **Main file path**: `toss_dashboard.py`
4. **Deploy** 클릭

### 1-3. Secrets 설정 (필수)
앱 설정 → **Secrets** 에 서비스 계정 키를 아래 형식으로 붙여넣기:

```toml
[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "...@....iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
```

> 값은 로컬 SA JSON 파일(`uploading-raw-data-...json`)의 내용을 그대로 옮기면 됩니다.
> `private_key`의 줄바꿈은 `\n` 형태로 유지.

### 1-4. 배포 URL 확정
배포 후 생성된 URL (예: `https://toss-update-bot.streamlit.app`) 을 복사.

---

## 2. Apps Script 슬랙 링크 교체

`toss_apps_script.js` 의 `STREAMLIT_URL` 을 위 배포 URL로 변경 후
구글시트 > 확장 프로그램 > Apps Script 에 붙여넣고 저장.

```js
var STREAMLIT_URL = "https://여기에-실제-배포-URL";
```

---

## 3. 사무실 PC 워커 셋업 (토스 재수집용)

토스 재수집은 **토스에 로그인된 Chrome이 있는 PC**에서만 동작합니다.
항상 켜두는 PC 한 대를 워커로 지정하세요.

### 3-1. 준비물
- Python + 레포 클론 (`git clone ...`)
- `pip install -r requirements.txt`
- browser-harness 설치 (`C:\Users\<사용자>\Developer\browser-harness`)
- Service Account 키 파일 (toss_update_bot.py 의 `SA_FILE` 경로에 위치)
- Chrome 에 **토스 광고 플랫폼 로그인** 유지

### 3-2. 워커 실행
```
run_worker.bat  (더블클릭)
```
또는
```
py toss_worker.py
```

창을 닫으면 워커가 멈춥니다. 항상 켜두려면 Windows 작업 스케줄러에
"로그온 시 실행" 으로 등록하세요.

### 3-3. 동작 확인
대시보드에서 "토스 대시보드 재수집" 클릭 → 워커 콘솔에
`▶ 작업 시작 ...` 로그가 뜨면 정상.

---

## 요약 체크리스트
- [ ] Streamlit Cloud 배포 + Secrets 입력
- [ ] 배포 URL 을 Apps Script `STREAMLIT_URL` 에 반영
- [ ] 사무실 PC 에서 `run_worker.bat` 상시 실행
- [ ] 사무실 PC Chrome 에 토스 로그인 유지
