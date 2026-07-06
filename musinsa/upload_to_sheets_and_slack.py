import os
from datetime import datetime
from typing import List

import requests

# 무신사 랭킹 API URL
MUSINSA_API_URL = (
    "https://api.musinsa.com/api2/hm/web/v5/pans/ranking"
    "?storeCode=musinsa"
    "&gf=A"
    "&sectionId=200"
    "&contentsId="
    "&categoryCode=000"
    "&ageBand=AGE_BAND_ALL"
)


def fetch_json() -> dict:
    """무신사 랭킹 API를 호출해서 JSON 응답을 반환한다."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )
    }
    resp = requests.get(MUSINSA_API_URL, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()


def extract_top_100_products(data: dict):
    """API 응답에서 상위 100개 상품을 추출한다."""
    modules = (data.get("data") or {}).get("modules")
    if not isinstance(modules, list):
        return []

    products = []
    for module in modules:
        items = module.get("items")
        if not isinstance(items, list):
            continue

        for item in items:
            info = item.get("info") or {}
            image = item.get("image") or {}

            if (
                isinstance(info, dict)
                and "brandName" in info
                and "productName" in info
                and "rank" in image
            ):
                products.append(
                    {
                        "rank": image.get("rank"),
                        "brandName": info.get("brandName"),
                        "productName": info.get("productName"),
                        "finalPrice": info.get("finalPrice"),
                        "discountRatio": info.get("discountRatio"),
                        "url": (item.get("onClick") or {}).get("url"),
                    }
                )

    products.sort(key=lambda x: x["rank"])
    return products[:100]


API_PROXY_BASE_URL = "https://api-auth.madup-dct.site"
API_KEY_ENV_VAR = "API_PROXY_API_KEY"
SLACK_CHANNEL_ENV_VAR = "SLACK_CHANNEL"

# 기본 API 키 (환경 변수가 없을 때 사용)
DEFAULT_API_KEY = "mk_795c5b723059c5ba99f0c4cc724d932b9d81c94a2bc918cad5190061f9db34cc"

# 기본 슬랙 채널 ID (환경 변수가 없을 때 사용)
DEFAULT_SLACK_CHANNEL = "C08T242LX8A"

SPREADSHEET_ID = "1JFTIXLO1N8Nkig2hqu-py5fRUuGLmk0eAONRjKiffsU"


def get_api_key() -> str:
    api_key = os.getenv(API_KEY_ENV_VAR)
    if not api_key:
        api_key = DEFAULT_API_KEY
    return api_key


def get_slack_channel() -> str:
    channel = os.getenv(SLACK_CHANNEL_ENV_VAR)
    if not channel:
        channel = DEFAULT_SLACK_CHANNEL
    return channel


HEADERS = ["rank", "brandName", "productName", "finalPrice", "discountRatio", "url"]


def build_sheet_rows(products: List[dict]) -> list[list[str]]:
    rows: list[list[str]] = [HEADERS]

    for p in products:
        rows.append(
            [
                str(p.get("rank") or ""),
                str(p.get("brandName") or ""),
                str(p.get("productName") or ""),
                str(p.get("finalPrice") or ""),
                str(p.get("discountRatio") or ""),
                str(p.get("url") or ""),
            ]
        )

    return rows


def upload_to_sheet(rows: list[list[str]]) -> dict:
    api_key = get_api_key()

    payload = {
        "spreadsheet_id": SPREADSHEET_ID,
        # worksheet 를 지정하지 않으면 첫 번째 시트(gid=0)에 기록
        "data": rows,
        "mode": "overwrite",
    }

    resp = requests.post(
        f"{API_PROXY_BASE_URL}/api/sheets/upload",
        headers={
            "X-API-Key": api_key,
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"Sheets 업로드 실패: {data}")
    return data


def send_slack_notification(product_count: int, started_at: datetime) -> dict:
    api_key = get_api_key()
    channel = get_slack_channel()

    sheet_url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit"
    text = (
        f"무신사 랭킹 크롤링 완료 ✅\n"
        f"- 크롤링 시각: {started_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"- 업로드 상품 수: {product_count}개\n"
        f"- 시트 링크: {sheet_url}"
    )

    payload = {
        "channel": channel,
        "text": text,
    }

    resp = requests.post(
        f"{API_PROXY_BASE_URL}/api/slack/send-message",
        headers={
            "X-API-Key": api_key,
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"Slack 전송 실패: {data}")
    return data


def main():
    started_at = datetime.now()

    print("1. 무신사 랭킹 크롤링 중...")
    musinsa_json = fetch_json()
    products = extract_top_100_products(musinsa_json)
    print(f"   → {len(products)}개 상품 수집 완료")

    rows = build_sheet_rows(products)

    print("2. Google Sheets 업로드 중...")
    sheets_result = upload_to_sheet(rows)
    print(f"   → 완료: {sheets_result}")

    print("3. Slack 알림 전송 중...")
    slack_result = send_slack_notification(len(products), started_at)
    print(f"   → 완료: {slack_result}")


if __name__ == "__main__":
    main()


