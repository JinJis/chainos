"""Predict scheduler. In production this is the 24/7 job that ingests global news,
parses it (LOW tier), links entities, and refreshes the per-node momentum cache.

Here it periodically triggers the Engine's Predict run for every published theme,
keeping the Terminal's Ghost-Node overlay warm. Run: `python -m app.scheduler`."""
from __future__ import annotations

import os
import time

import httpx

ENGINE_URL = os.environ.get("ENGINE_URL", "http://127.0.0.1:8000")
INTERVAL_SECONDS = int(os.environ.get("PREDICT_INTERVAL", "60"))


def tick(client: httpx.Client) -> None:
    themes = client.get(f"{ENGINE_URL}/terminal/themes").json()
    for theme in themes:
        res = client.post(f"{ENGINE_URL}/predict/{theme['id']}/run").json()
        print(
            f"[predict] {theme['name']}: scored {res.get('news_count', 0)} news → "
            f"{len(res.get('nodes', {}))} nodes with momentum"
        )


def main() -> None:
    print(f"Chainos predict scheduler → {ENGINE_URL} every {INTERVAL_SECONDS}s")
    with httpx.Client(timeout=60) as client:
        while True:
            try:
                tick(client)
            except Exception as exc:  # noqa: BLE001 — keep the loop alive
                print(f"[predict] error: {exc}")
            time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
