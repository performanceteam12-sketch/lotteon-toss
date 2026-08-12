"""토스 디스플레이 광고(ads-platform.toss.im) 일별 노출/클릭/비용 수집 봇.

로컬 PC의 이미 로그인된 크롬(browser-harness로 CDP 접속)을 이용해
'리포트' 도구에서 지정한 날짜 하루치 데이터를 CSV로 받아 합산한 뒤,
'수기매체업로드' 시트에 [날짜, "토스Pioneer Club", "DA", "없음", "없음", 노출, 클릭, 비용] 행으로 반영한다.

주의: nonauto-media(GitHub Actions, 매일 08:00 KST)가 같은 시트의 같은 날짜 행을
전부 지우고 자기 몫(RTB/버즈빌/BSA)만 다시 쓰는 방식이라, 이 봇은 그보다 나중에
실행되어야 한다(예: 매일 08:20 KST). 반대로 nonauto-media 쪽을 그 날짜로 수동
재실행하면 이 봇이 넣은 행이 같이 지워지므로, 그 경우 이 봇도 다시 실행해야 한다.

사용법:
    py toss_display_ads_bot.py                     # 어제
    py toss_display_ads_bot.py --date 2026-08-10    # 특정 날짜
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SA_FILE = (
    r"C:\Users\MADUP\주식회사매드업 Dropbox\광고사업부\4. 광고주"
    r"\카카오스타일\★ 지그재그\리포트\(이전)\2. 파이썬"
    r"\uploading-raw-data-to-gspread-a76f45bcfd36.json"
)
SPREADSHEET_ID = "18Gzpi_yeYQXbjqChlhm9EHT7z0Gi-65D0NCX7iC3SJ4"
TARGET_SHEET = "수기매체업로드"
CAMPAIGN_LABEL = "토스Pioneer Club"
MEDIA = "DA"
REPORT_URL = "https://ads-platform.toss.im/reports/3606"
SLACK_WEBHOOK_URL = "https://hooks.slack.com/triggers/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"


def send_slack(text: str) -> None:
    """슬랙 웹훅으로 메시지 전송 (기존 토스봇과 같은 채널, 실패해도 무시)."""
    import urllib.request
    try:
        req = urllib.request.Request(
            SLACK_WEBHOOK_URL,
            data=json.dumps({"text": text}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass

BH_PROJECT = os.environ.get("BH_PROJECT") or str(
    Path(__file__).resolve().parent.parent / "browser-harness"
)
_HERE = Path(__file__).parent
_SCRAPE_SCRIPT = _HERE / "_toss_display_scrape.py"
_SCRAPE_RESULT = _HERE / "_toss_display_scrape_result.json"
DOWNLOADS_DIR = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Downloads"

_SCRAPE_CODE = '''\
import json, time

TARGET_DAY = {day}   # 1~31 (int)
RESULT_PATH = r"{result_path}"
REPORT_URL = "{report_url}"

result = {{"ok": False}}

tabs = list_tabs(include_chrome=False)
toss_tab = next((t for t in tabs if "ads-platform.toss.im" in t["url"]), None)

if not toss_tab:
    new_tab(REPORT_URL)
else:
    switch_tab(toss_tab["targetId"])
    goto_url(REPORT_URL)

wait_for_load(timeout=20)
wait_for_element(".pcb4-1d9fzqx8", timeout=20)
time.sleep(1)

# goto_url이 가끔 리포트 페이지가 아니라 계정 홈으로 튕기는 경우가 있어,
# 실제로 리포트 페이지에 도착했는지 확인하고 아니면 재시도한다.
for _ in range(3):
    current_url = js("return location.href")
    if "/reports/" in current_url:
        break
    goto_url(REPORT_URL)
    wait_for_load(timeout=20)
    wait_for_element(".pcb4-1d9fzqx8", timeout=20)
    time.sleep(1)
else:
    result["error"] = "리포트 페이지 도착 실패 (계정 홈으로 반복 리다이렉트됨): " + js("return location.href")
    try:
        capture_screenshot(r"{here}\\_toss_display_ads_error.png")
    except Exception:
        pass

if "error" in result:
    trigger_rect = None
else:
    # 날짜 범위 트리거 클릭 (react-calendar 기반 팝업 열기)
    trigger_rect = js("""
    const el = document.querySelector('.pcb4-1d9fzqx8');
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return [Math.round(r.x + r.width/2), Math.round(r.y + r.height/2)];
    """)

if "error" in result:
    pass
elif not trigger_rect:
    result["error"] = "date range trigger not found"
    try:
        capture_screenshot(r"{here}\\_toss_display_ads_error.png")
    except Exception:
        pass
else:
    click_at_xy(trigger_rect[0], trigger_rect[1])
    time.sleep(1)

    tile_center = None
    for _ in range(3):
        tile_center = js("""
        const tiles = Array.from(document.querySelectorAll('.react-calendar__tile'));
        const target = tiles.find(t => {{
            const abbr = t.querySelector('abbr');
            return abbr && abbr.textContent.trim() === '""" + str(TARGET_DAY) + """' && !t.className.includes('neighboringMonth');
        }});
        if (!target) return null;
        const r = target.getBoundingClientRect();
        return [Math.round(r.x + r.width/2), Math.round(r.y + r.height/2)];
        """)
        if tile_center:
            break
        prev_clicked = js("""
        const btn = document.querySelector('.react-calendar__navigation__prev-button');
        if (btn) {{ btn.click(); return true; }}
        return false;
        """)
        time.sleep(0.5)
        if not prev_clicked:
            break

    if not tile_center:
        result["error"] = "target day tile not found after month navigation attempts"
        try:
            capture_screenshot(r"{here}\\_toss_display_ads_error.png")
        except Exception:
            pass
    else:
        click_at_xy(tile_center[0], tile_center[1])
        time.sleep(0.3)
        click_at_xy(tile_center[0], tile_center[1])
        time.sleep(0.5)

        confirm_rect = js("""
        const btns = Array.from(document.querySelectorAll('button'));
        const btn = btns.find(b => b.textContent.trim() === '확인');
        if (!btn) return null;
        const r = btn.getBoundingClientRect();
        return [Math.round(r.x + r.width/2), Math.round(r.y + r.height/2)];
        """)
        if confirm_rect:
            click_at_xy(confirm_rect[0], confirm_rect[1])
            time.sleep(2)

        date_range_text = js("""
        const el = document.querySelector('.pcb4-1d9fzqx0');
        return el ? el.textContent.trim() : null;
        """)
        result["date_range_text"] = date_range_text

        clicked = js("""
        const btn = document.querySelector('button[aria-label="CSV 다운로드"]');
        if (btn) {{ btn.click(); return true; }}
        return false;
        """)
        result["csv_clicked"] = clicked
        time.sleep(2)
        result["ok"] = bool(clicked)

with open(RESULT_PATH, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
'''


def _client() -> gspread.Client:
    sa_json = os.environ.get("GCP_SA_JSON")
    if sa_json:
        info = json.loads(sa_json)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        sa_file = os.environ.get("TOSS_SA_FILE") or SA_FILE
        creds = Credentials.from_service_account_file(sa_file, scopes=SCOPES)
    return gspread.authorize(creds)


def _uv_exe() -> str:
    import shutil
    found = shutil.which("uv")
    if found:
        return found
    fallback = os.path.expandvars(
        r"%LOCALAPPDATA%\Microsoft\WinGet\Packages"
        r"\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe\uv.exe"
    )
    return fallback if os.path.isfile(fallback) else "uv"


def _run_browser_step(target_day: int) -> dict:
    code = _SCRAPE_CODE.format(
        day=target_day,
        result_path=str(_SCRAPE_RESULT).replace("\\", "\\\\"),
        report_url=REPORT_URL,
        here=str(_HERE).replace("\\", "\\\\"),
    )
    _SCRAPE_SCRIPT.write_text(code, encoding="utf-8")

    if _SCRAPE_RESULT.exists():
        _SCRAPE_RESULT.unlink()

    print("[토스DA봇] 브라우저 조작 중 (날짜 선택 + CSV 다운로드 클릭)...")
    subprocess.run(
        [_uv_exe(), "run", "--project", BH_PROJECT, "browser-harness"],
        input=f"exec(open('{_SCRAPE_SCRIPT.name}', encoding='utf-8').read())\n",
        text=True, encoding="utf-8", errors="replace",
        cwd=str(_HERE), creationflags=_NO_WINDOW,
    )

    if not _SCRAPE_RESULT.exists():
        raise RuntimeError("브라우저 조작 결과 파일이 생성되지 않았습니다.")

    data = json.loads(_SCRAPE_RESULT.read_text(encoding="utf-8"))
    if not data.get("ok"):
        raise RuntimeError(f"브라우저 조작 실패: {data}")
    print(f"[토스DA봇] 날짜 선택 결과: {data.get('date_range_text')}")
    return data


def _wait_for_new_csv(since_ts: float, timeout: float = 20.0) -> Path:
    deadline = time.time() + timeout
    while time.time() < deadline:
        candidates = [
            p for p in DOWNLOADS_DIR.glob("*.csv")
            if p.stat().st_mtime > since_ts
        ]
        if candidates:
            return max(candidates, key=lambda p: p.stat().st_mtime)
        time.sleep(0.5)
    raise RuntimeError("다운로드된 CSV 파일을 찾지 못했습니다 (타임아웃).")


def _parse_and_sum(csv_path: Path, target_date: str) -> dict:
    text = csv_path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    imps = clicks = cost = 0
    rows_matched = 0
    for row in reader:
        row_date = row.get("이벤트 발생 날짜", "").strip()
        if row_date != target_date:
            continue
        rows_matched += 1
        imps += int(float(row.get("노출 수", 0) or 0))
        clicks += int(float(row.get("클릭 수", 0) or 0))
        cost += int(float(row.get("집행 비용 (VAT 제외) (₩)", 0) or 0))
    print(f"[토스DA봇] CSV {rows_matched}행 합산 → imps={imps}, clicks={clicks}, cost={cost}")
    if rows_matched == 0:
        raise RuntimeError(f"CSV에 {target_date} 날짜 데이터가 없습니다: {csv_path}")
    return {"imps": imps, "clicks": clicks, "cost": cost}


def scrape_toss_display(target_date: str) -> dict:
    day = int(target_date.split("-")[2])
    since_ts = time.time()
    _run_browser_step(day)
    csv_path = _wait_for_new_csv(since_ts)
    print(f"[토스DA봇] 다운로드 파일: {csv_path}")
    return _parse_and_sum(csv_path, target_date)


def update_sheet(target_date: str, data: dict):
    client = _client()
    sh = client.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet(TARGET_SHEET)

    all_values = ws.get_all_values()
    rows_to_delete = [
        idx + 1
        for idx, row in enumerate(all_values)
        if len(row) >= 2 and row[0].strip() == target_date and row[1].strip() == CAMPAIGN_LABEL
    ]
    for row_idx in reversed(rows_to_delete):
        ws.delete_rows(row_idx)
    if rows_to_delete:
        print(f"[토스DA봇] 기존 {CAMPAIGN_LABEL} 행 {len(rows_to_delete)}개 삭제 (날짜: {target_date})")

    new_row = [target_date, CAMPAIGN_LABEL, MEDIA, "없음", "없음",
               data["imps"], data["clicks"], data["cost"]]
    ws.append_row(new_row, value_input_option="USER_ENTERED")
    print(f"[토스DA봇] 행 추가 완료: {new_row}")


QUEUE_SHEET = "토스DA큐"


def process_queue() -> int:
    """
    nonauto-media(GitHub Actions)가 남겨둔 '토스DA큐' 탭의 pending 요청을 처리한다.
    수기매체 자동화가 특정 날짜로 재실행됐을 때, 그 날짜 토스 데이터도 같이
    갱신되도록 연결하는 다리 역할. 처리한 요청 수를 반환한다.
    """
    client = _client()
    sh = client.open_by_key(SPREADSHEET_ID)
    try:
        ws = sh.worksheet(QUEUE_SHEET)
    except gspread.WorksheetNotFound:
        return 0

    rows = ws.get_all_values()
    processed = 0
    for idx, row in enumerate(rows):
        if idx == 0 or len(row) < 2:
            continue
        target_date, status = row[0].strip(), row[1].strip()
        if status != "pending" or not target_date:
            continue

        print(f"[토스DA봇] 큐 요청 처리: {target_date}")
        try:
            data = scrape_toss_display(target_date)
            update_sheet(target_date, data)
            ws.update_cell(idx + 1, 2, "done")
            send_slack(
                f"✅ [토스DA봇] {target_date} 업로드 완료 (nonauto-media 재실행 연동)\n"
                f"노출 {data['imps']:,} / 클릭 {data['clicks']:,} / 비용 {data['cost']:,}원"
            )
        except Exception as e:
            ws.update_cell(idx + 1, 2, "error")
            send_slack(f"❌ [토스DA봇] 큐 요청 실패 ({target_date})\n{e}")
        processed += 1
    return processed


def main():
    parser = argparse.ArgumentParser(description="토스 디스플레이 광고 일별 수집 봇")
    parser.add_argument("--date", type=str, help="YYYY-MM-DD (기본: 어제)")
    args = parser.parse_args()

    target_date = args.date or (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"[토스DA봇] 대상 날짜: {target_date}")

    try:
        data = scrape_toss_display(target_date)
        update_sheet(target_date, data)
        print("[토스DA봇] 완료")
        send_slack(
            f"✅ [토스DA봇] {target_date} 업로드 완료\n"
            f"노출 {data['imps']:,} / 클릭 {data['clicks']:,} / 비용 {data['cost']:,}원"
        )
    except Exception as e:
        print(f"[토스DA봇] 실패: {e}")
        send_slack(
            f"❌ [토스DA봇] {target_date} 실패\n{e}\n"
            f"PC가 꺼져있거나, 크롬 원격 디버깅/토스 로그인이 끊겼을 수 있습니다. "
            f"확인 후 `py toss_display_ads_bot.py --date {target_date}` 로 수동 재실행해주세요."
        )
        sys.exit(1)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
