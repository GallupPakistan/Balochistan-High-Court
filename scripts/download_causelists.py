"""
Balochistan High Court - Cause List PDF Scraper
Downloads cause-list PDFs for all benches/tribunals for a rolling recent
date window (default: last 10 days, to catch any late-published lists).

Usage:
    pip install requests
    python scripts/download_causelists.py
"""

import os
import requests
from datetime import date, timedelta
import time

BASE_URL = "https://bhc.gov.pk/media/causelists"

BENCHES = {
    "1101": "principal_seat_quetta",
    "1102": "sibi_bench",
    "1103": "turbat_bench",
    "1104": "loralai_bench",
    "1105": "khuzdar_bench",
    "1801": "services_tribunal",
    "1802": "customs_tribunal",
    "1803": "election_tribunal",
}

# filename prefixes seen so far; extend this list if you find new ones
PREFIXES = [
    "division_bench",
    "single_bench",
    "division_bench_additional_at_principal_seat_quetta",
    "single_bench_additional_at_principal_seat_quetta",
]

MAX_LIST_NUMBER = 6  # tries list no. 1..6 per prefix per day

# How many days back to (re)check. Kept small for a daily job — everything
# older is already downloaded/skipped. Override with env var if you ever
# need a longer backfill run.
LOOKBACK_DAYS = int(os.environ.get("BHC_LOOKBACK_DAYS", "10"))

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "downloads")

HEADERS = {"User-Agent": "Mozilla/5.0"}


def daterange(start, end):
    for n in range((end - start).days + 1):
        yield start + timedelta(n)


def main():
    end_date = date.today()
    start_date = end_date - timedelta(days=LOOKBACK_DAYS)
    session = requests.Session()
    session.headers.update(HEADERS)

    total_downloaded = 0

    for bench_id, bench_name in BENCHES.items():
        bench_dir = os.path.join(OUTPUT_DIR, f"{bench_name}_{bench_id}")
        os.makedirs(bench_dir, exist_ok=True)

        for d in daterange(start_date, end_date):
            d_str = d.isoformat()
            for prefix in PREFIXES:
                for n in range(1, MAX_LIST_NUMBER + 1):
                    filename = f"{prefix}_{n}_{d_str}.pdf"
                    url = f"{BASE_URL}/{bench_id}/{d_str}/{filename}"
                    save_path = os.path.join(bench_dir, filename)

                    if os.path.exists(save_path):
                        continue  # already downloaded

                    try:
                        r = session.get(url, timeout=15)
                    except requests.RequestException as e:
                        print(f"ERROR {url}: {e}")
                        continue

                    if r.status_code == 200 and r.headers.get("Content-Type", "").lower().startswith("application/pdf"):
                        with open(save_path, "wb") as f:
                            f.write(r.content)
                        total_downloaded += 1
                        print(f"Saved: {save_path}")
                    # else: silently skip (404 or not found) - most attempts will 404, that's expected

                    time.sleep(0.1)  # be polite to the server

    print(f"\nDone. Total PDFs downloaded: {total_downloaded}")


if __name__ == "__main__":
    main()
