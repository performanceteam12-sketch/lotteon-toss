"""토스 광고비 업데이트 대시보드 (Streamlit)

실행:
    streamlit run toss_dashboard.py
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="토스 광고비 업데이트",
    page_icon="💙",
    layout="centered",
)

st.markdown("""
<style>
  @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

  html, body, *, *::before, *::after,
  [class*="css"], input, button, select, textarea, label, p, span, div,
  .stMarkdown, .stText, .stDateInput, .stButton,
  [data-testid], [data-baseweb] {
    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif !important;
  }

  .toss-header {
    background: #0064FF;
    border-radius: 16px;
    padding: 28px 32px 24px;
    margin-bottom: 28px;
    color: white;
  }
  .toss-header h1 { font-size: 22px; font-weight: 700; margin: 0 0 4px; }
  .toss-header p  { font-size: 14px; opacity: .75; margin: 0; }

  .toss-card {
    background: white;
    border: 1px solid #F2F4F6;
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 16px;
    box-shadow: 0 2px 8px rgba(0,0,0,.04);
  }
  .toss-card-title {
    font-size: 13px; font-weight: 600; color: #6B7684;
    text-transform: uppercase; letter-spacing: .05em;
    margin-bottom: 14px;
  }

  .log-box {
    background: #F8F9FA;
    border: 1px solid #E9ECEF;
    border-radius: 12px;
    padding: 16px;
    font-size: 13px;
    line-height: 1.7;
    font-family: 'Consolas', monospace !important;
    max-height: 320px;
    overflow-y: auto;
    white-space: pre-wrap;
  }

  .result-row {
    display: flex; justify-content: space-between; align-items: center;
    padding: 10px 0; border-bottom: 1px solid #F2F4F6; font-size: 14px;
  }
  .result-row:last-child { border-bottom: none; }
  .result-channel { color: #4E5968; }
  .result-cost { font-weight: 700; color: #0064FF; }

  /* 버튼 공통 기본 */
  div.stButton > button {
    border: none !important;
    border-radius: 12px !important;
    padding: 18px 24px !important;
    font-size: 16px !important;
    font-weight: 700 !important;
    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif !important;
    width: 100% !important;
    min-height: 56px !important;
    line-height: 1.4 !important;
    transition: background .15s, opacity .15s !important;
    color: white !important;
  }

  /* 첫 번째 컬럼 = 일반 재수집 — 파란색 */
  div[data-testid="column"]:nth-of-type(1) div.stButton > button {
    background: #0064FF !important;
  }
  div[data-testid="column"]:nth-of-type(1) div.stButton > button:hover {
    background: #0052CC !important;
  }

  /* 두 번째 컬럼 = 토스 대시보드 재수집 — 다크 */
  div[data-testid="column"]:nth-of-type(2) div.stButton > button {
    background: #191F28 !important;
  }
  div[data-testid="column"]:nth-of-type(2) div.stButton > button:hover {
    background: #2E3A4A !important;
  }

  div.stButton > button:disabled {
    color: white !important;
    cursor: not-allowed !important;
    opacity: 0.5 !important;
  }

  .block-container { padding-top: 2rem; max-width: 680px; }
  footer { display: none; }
  #MainMenu { display: none; }
</style>
""", unsafe_allow_html=True)

# ── 상수 ──────────────────────────────────────────────────────────────────────
_HERE = Path(__file__).parent
SPREADSHEET_ID = "18Gzpi_yeYQXbjqChlhm9EHT7z0Gi-65D0NCX7iC3SJ4"
TARGET_SHEET   = "토스업로드"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit?gid=1288015996#gid=1288015996"
SLACK_WEBHOOK_URL = "https://hooks.slack.com/triggers/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"


def send_slack(text: str) -> None:
    """슬랙 워크플로우 웹훅으로 메시지 전송 (실패해도 무시)."""
    import urllib.request
    import json as _j
    try:
        req = urllib.request.Request(
            SLACK_WEBHOOK_URL,
            data=_j.dumps({"text": text}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass

# ── 세션 스테이트 ─────────────────────────────────────────────────────────────
for key in ["logs", "result", "error", "running"]:
    if key not in st.session_state:
        st.session_state[key] = [] if key == "logs" else (False if key == "running" else None)

# 결과 표시는 ?r=1 쿼리파라미터에 묶는다.
# → 슬랙의 일반 링크(파라미터 없음)로 열면 항상 초기 입력 화면으로 시작.
_show_results = "r" in st.query_params
if not st.session_state.running:
    # 결과/로그는 ?r=1 일 때만 유지 (슬랙 결과 링크용).
    if not _show_results:
        st.session_state.result = None
        st.session_state.logs   = []
    # 에러는 방금 실패한 실행 직후 딱 한 번만 보여주고,
    # 이후 새로고침·재방문(?r=1 유지) 시엔 자동으로 지운다. (옛 에러 눌러붙음 방지)
    if st.session_state.get("_error_fresh"):
        st.session_state._error_fresh = False   # 이번 실행에서 소비 → 에러 유지
    else:
        st.session_state.error = None

# ── 인증 부트스트랩: Streamlit secrets → 환경변수 ─────────────────────────────
import os
import json as _json

try:
    if "gcp_service_account" in st.secrets:
        os.environ["GCP_SA_JSON"] = _json.dumps(dict(st.secrets["gcp_service_account"]))
except Exception:
    pass  # secrets 미설정 환경에서도 부팅되도록

# ── import ────────────────────────────────────────────────────────────────────
sys.path.insert(0, str(_HERE))
from toss_update_bot import _client, run_pipeline, SPREADSHEET_ID as _SID
from toss_queue import enqueue, get_job

POLL_TIMEOUT  = 600  # 토스 작업 최대 대기 (초)
POLL_INTERVAL = 5    # 큐 확인 주기 (초)


def run_general(start: date, end: date) -> dict:
    """일반 재수집 — 클라우드/로컬 어디서나 직접 실행."""
    logs = []
    result = run_pipeline(start, end, use_toss=False, log=logs.append)
    result["logs"] = logs
    return result


def run_toss_via_queue(start: date, end: date) -> dict:
    """토스 재수집 — 큐에 작업 등록 후 워커 완료를 폴링."""
    import time
    logs = []
    client = _client()
    sh = client.open_by_key(SPREADSHEET_ID)

    s_str, e_str = start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
    job_id = enqueue(sh, s_str, e_str, mode="toss")
    logs.append(f"📤 작업 요청 등록 (ID: {job_id})")
    logs.append("⏳ 사무실 워커가 토스 대시보드를 수집 중입니다...")

    waited = 0
    while waited < POLL_TIMEOUT:
        time.sleep(POLL_INTERVAL)
        waited += POLL_INTERVAL
        job = get_job(sh, job_id)
        if not job:
            continue
        if job["status"] == "done":
            logs.append(f"✅ {job['message']}")
            return {"logs": logs, "sojaebang": [], "deleted": 0,
                    "dates": [s_str] if s_str == e_str else [s_str, e_str],
                    "used_toss": True, "queued": True}
        if job["status"] == "error":
            raise RuntimeError(f"워커 오류: {job['message']}")

    raise RuntimeError(
        "워커 응답 시간 초과. 사무실 PC에서 워커(toss_worker.py)가 실행 중인지 확인해주세요."
    )


# ── UI ────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="toss-header">
  <h1>💙 토스 광고비 업데이트</h1>
  <p>날짜를 선택하고 업데이트하면 클릭 수 기반으로 광고비를 자동 계산합니다</p>
</div>
""", unsafe_allow_html=True)

# 날짜 선택
st.markdown(
    '<p style="font-size:18px;font-weight:700;margin:8px 0 16px;">'
    '📅 업데이트 기간 설정</p>',
    unsafe_allow_html=True
)

yesterday = date.today() - timedelta(days=1)
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("시작 날짜", value=yesterday, max_value=date.today(), key="start")
with col2:
    end_date = st.date_input("종료 날짜", value=yesterday, max_value=date.today(), key="end")

if start_date > end_date:
    st.error("시작 날짜가 종료 날짜보다 늦습니다.")
    st.stop()

days_count = (end_date - start_date).days + 1
st.markdown(
    f'<p style="font-size:13px;opacity:.65;margin-top:4px;margin-bottom:24px;">'
    f'선택 기간: <b style="color:#5B8DEF">{days_count}일</b> ({start_date} ~ {end_date})</p>',
    unsafe_allow_html=True
)

# 버튼 영역
st.markdown(
    '<p style="font-size:18px;font-weight:700;margin:8px 0 16px;">'
    '🔄 재수집 방식 선택</p>',
    unsafe_allow_html=True
)

col_a, col_b = st.columns(2)
with col_a:
    btn_normal = st.button(
        "일반 재수집",
        disabled=st.session_state.running,
        help="클릭 기반 구간 비용으로 재업로드 (토스 로그인 불필요)",
        use_container_width=True,
    )
with col_b:
    btn_toss = st.button(
        "토스 대시보드 재수집",
        disabled=st.session_state.running,
        help="토스 대시보드 스크래핑 후 집행완료 예외 비용 적용 (Chrome 로그인 필요)",
        use_container_width=True,
    )

st.markdown(
    '<p style="font-size:12px;opacity:.6;margin-top:8px;margin-bottom:16px;line-height:1.9;">'
    '💡 <b>일반</b>: 클릭 &lt; 10,000 → 클릭×10원 / 이상 → 만 단위×10만원<br>'
    '💡 <b>토스</b>: 집행완료 + 집행비용 ≠ 예상비용인 경우 실제 집행비용으로 보정</p>',
    unsafe_allow_html=True
)

# 버튼 클릭 처리
use_toss = None
if btn_normal:
    use_toss = False
elif btn_toss:
    use_toss = True

if use_toss is not None and not st.session_state.running:
    st.session_state.running = True
    st.session_state.logs    = []
    st.session_state.result  = None
    st.session_state.error   = None
    st.session_state._error_fresh = False

    spinner_msg = "토스 대시보드 수집 요청 중..." if use_toss else "재수집 중..."
    try:
        with st.spinner(spinner_msg):
            if use_toss:
                result = run_toss_via_queue(start_date, end_date)
            else:
                result = run_general(start_date, end_date)
        st.session_state.result = result
        st.session_state.logs   = result["logs"]

        # 슬랙 완료 알림
        dts = result["dates"]
        label = dts[0] if len(dts) == 1 else f"{dts[0]} ~ {dts[-1]}"
        mode  = "토스 대시보드 재수집" if result["used_toss"] else "일반 재수집"
        soje  = len(result["sojaebang"])
        detail = result["logs"][-1] if result.get("queued") else f"소재행 {soje}개, 삭제 {result['deleted']}개"
        send_slack(f"🔁 [토스봇] {mode} 완료 — {label}\n{detail}")
    except Exception as e:
        st.session_state.error = str(e)
        st.session_state._error_fresh = True   # 이 실행 직후 한 번만 표시
    finally:
        st.session_state.running = False

    st.query_params["r"] = "1"  # 결과 표시 활성화 (새로고침/재방문 시엔 사라짐)
    st.rerun()

# 로그
if st.session_state.logs:
    log_text = "\n".join(st.session_state.logs)
    st.markdown(
        f'<div class="toss-card"><div class="toss-card-title">📋 실행 로그</div>'
        f'<div class="log-box">{log_text}</div></div>',
        unsafe_allow_html=True
    )

# 에러
if st.session_state.error:
    st.markdown(
        f'<div class="toss-card" style="border-color:#FFCDD2;">'
        f'<div class="toss-card-title">❌ 오류 발생</div>'
        f'<p style="color:#D32F2F;font-size:14px;margin:0;">{st.session_state.error}</p>'
        f'</div>',
        unsafe_allow_html=True
    )

# 결과
if st.session_state.result:
    r = st.session_state.result
    sojaebang = r["sojaebang"]
    queued = r.get("queued", False)
    mode_label = "토스 대시보드 재수집" if r["used_toss"] else "일반 재수집"

    if queued:
        # 토스(큐) 작업 — 워커가 처리, 상세 행은 시트에서 확인
        st.markdown(
            f'<div class="toss-card">'
            f'<div class="toss-card-title">✅ {mode_label} 완료</div>'
            f'<p style="font-size:14px;color:#4E5968;margin:0;">'
            f'사무실 워커가 토스 대시보드를 수집하고 시트를 업데이트했습니다.<br>'
            f'상세 결과는 아래 버튼으로 시트에서 확인하세요.</p>'
            f'</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f'<div class="toss-card">'
            f'<div class="toss-card-title">✅ {mode_label} 완료</div>'
            f'<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:16px;">'
            f'  <div style="flex:1;background:#E8F3FF;border-radius:12px;padding:16px;text-align:center;">'
            f'    <div style="font-size:24px;font-weight:800;color:#0064FF">{len(sojaebang)}</div>'
            f'    <div style="font-size:12px;color:#6B7684;margin-top:2px;">소재행</div>'
            f'  </div>'
            f'  <div style="flex:1;background:#F3FFF3;border-radius:12px;padding:16px;text-align:center;">'
            f'    <div style="font-size:24px;font-weight:800;color:#00B761">{r["deleted"]}</div>'
            f'    <div style="font-size:12px;color:#6B7684;margin-top:2px;">삭제된 행</div>'
            f'  </div>'
            f'  <div style="flex:1;background:#FFF8E1;border-radius:12px;padding:16px;text-align:center;">'
            f'    <div style="font-size:24px;font-weight:800;color:#F59E0B">{len(r["dates"])}</div>'
            f'    <div style="font-size:12px;color:#6B7684;margin-top:2px;">업데이트 일수</div>'
            f'  </div>'
            f'</div></div>',
            unsafe_allow_html=True
        )

    if sojaebang:
        rows_html = ""
        for row in sojaebang:
            d_str   = row[0]
            channel = row[4]
            clicks  = f"{int(row[6]):,}" if str(row[6]).isdigit() else str(row[6])
            cost    = f"{int(row[7]):,}원" if str(row[7]).isdigit() else str(row[7])
            rows_html += (
                f'<div class="result-row">'
                f'  <span style="color:#B0B8C1;font-size:12px;width:88px">{d_str}</span>'
                f'  <span class="result-channel" style="flex:1;padding:0 8px">{channel}</span>'
                f'  <span style="color:#6B7684;font-size:13px;width:70px;text-align:right">{clicks} 클릭</span>'
                f'  <span class="result-cost" style="width:90px;text-align:right">{cost}</span>'
                f'</div>'
            )
        st.markdown(
            f'<div style="border:1px solid #F2F4F6;border-radius:12px;padding:4px 16px;margin-bottom:16px;">{rows_html}</div>',
            unsafe_allow_html=True
        )

    st.markdown(
        f'<div style="text-align:center;margin-top:8px;">'
        f'<a href="{SHEET_URL}" target="_blank" style="'
        f'display:inline-block;background:#0064FF;color:white;text-decoration:none;'
        f'border-radius:12px;padding:12px 28px;font-size:15px;font-weight:700;">'
        f'📊 시트에서 확인하기</a></div>',
        unsafe_allow_html=True
    )
