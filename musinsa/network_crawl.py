import csv
import json
from datetime import datetime
from pathlib import Path

import requests


API_URL = (
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
    resp = requests.get(API_URL, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()


def extract_top_100_products(data: dict):
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


def save_to_csv(products, started_at: datetime, base_dir: Path | None = None) -> Path:
    if base_dir is None:
        base_dir = Path(".")

    stamp = started_at.strftime("%Y%m%d_%H%M%S")
    filename = base_dir / f"musinsa_ranking_{stamp}.csv"

    fieldnames = [
        "rank",
        "brandName",
        "productName",
        "finalPrice",
        "discountRatio",
        "url",
    ]

    with filename.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in products:
            writer.writerow(row)

    return filename


def main():
    started_at = datetime.now()
    data = fetch_json()
    products = extract_top_100_products(data)

    # 레포 루트에 저장하고 싶으면 두 번 상위로 올린 뒤 resolve
    base_dir = Path(__file__).resolve().parent.parent
    csv_path = save_to_csv(products, started_at, base_dir=base_dir)
    print(f"written: {csv_path}, rows: {len(products)}")


if __name__ == "__main__":
    main()


