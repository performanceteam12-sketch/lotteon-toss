"""토스 디스플레이 광고 봇을 매일 자동으로 실행하는 백그라운드 스케줄러.

Windows Task Scheduler가 이 PC에서 원인 불명으로 조용히 실행되지 않아,
기존 toss_worker.py와 동일한 방식(로그온 시 자동 시작 + 폴링 루프)으로 대체했다.

동작: 매 60초마다 확인, 현재 시각이 08:20(KST) 이후이고 오늘 아직 실행 안 했으면
전일자로 toss_display_ads_bot을 실행한다. PC가 꺼져있다 켜지면, 켜진 시점에
바로 그날 처리를 시도한다(놓친 실행을 자동으로 따라잡음). 실패 시 30분 후 재시도.
"""

import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import toss_display_ads_bot as bot

KST = ZoneInfo("Asia/Seoul")
RUN_AFTER_HOUR = 8
RUN_AFTER_MINUTE = 20
POLL_INTERVAL = 60
RETRY_INTERVAL_AFTER_FAILURE = 1800

_HERE = Path(__file__).resolve().parent
_MARKER = _HERE / "_toss_display_ads_last_run.txt"


def _last_run_date() -> str:
    try:
        return _MARKER.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def _mark_done(date_str: str):
    _MARKER.write_text(date_str, encoding="utf-8")


def _run_once():
    from datetime import timedelta
    target_date = (datetime.now(KST) - timedelta(days=1)).strftime("%Y-%m-%d")
    today_str = datetime.now(KST).strftime("%Y-%m-%d")

    print(f"[스케줄러] {today_str} 실행 시작 (대상 날짜: {target_date})")
    try:
        data = bot.scrape_toss_display(target_date)
        bot.update_sheet(target_date, data)
        bot.send_slack(
            f"✅ [토스DA봇] {target_date} 업로드 완료\n"
            f"노출 {data['imps']:,} / 클릭 {data['clicks']:,} / 비용 {data['cost']:,}원"
        )
        _mark_done(today_str)
        print(f"[스케줄러] {today_str} 완료")
        return True
    except Exception as e:
        print(f"[스케줄러] {today_str} 실패: {e}")
        bot.send_slack(
            f"❌ [토스DA봇] {target_date} 실패\n{e}\n"
            f"PC/크롬/토스 로그인 상태를 확인해주세요. 30분 후 자동 재시도합니다."
        )
        return False


def main():
    print("[스케줄러] 토스 디스플레이 광고 자동 스케줄러 시작")
    while True:
        now = datetime.now(KST)
        today_str = now.strftime("%Y-%m-%d")
        after_run_time = (now.hour, now.minute) >= (RUN_AFTER_HOUR, RUN_AFTER_MINUTE)

        # nonauto-media가 재실행됐을 때 남긴 큐 요청 처리
        # (수기매체 자동화 재실행 페이지로 특정 날짜를 다시 돌리면, 그 날짜 토스 데이터도 여기서 같이 갱신됨)
        try:
            n = bot.process_queue()
            if n:
                print(f"[스케줄러] 큐 요청 {n}건 처리")
        except Exception as e:
            print(f"[스케줄러] 큐 확인 실패: {e}")

        if after_run_time and _last_run_date() != today_str:
            ok = _run_once()
            time.sleep(POLL_INTERVAL if ok else RETRY_INTERVAL_AFTER_FAILURE)
        else:
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
