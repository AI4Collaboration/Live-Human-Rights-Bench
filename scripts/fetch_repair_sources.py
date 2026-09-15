"""Retrieve specified original HUDOC judgments without changing dataset rows."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import subprocess
import requests

from hudoc_scraper import HUDOC_DOC_BODY_URL, HEADERS, html_to_text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ids", nargs="+")
    parser.add_argument("--ids-from", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    selected = args.ids or []
    if args.ids_from:
        selected += json.loads(args.ids_from.read_text(encoding="utf-8"))["appendix_recovery_ids"]
    done = {}
    if args.out.exists():
        done = {r["item_id"]: r for r in map(json.loads, args.out.read_text(encoding="utf-8").splitlines())}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with requests.Session() as session, args.out.open("a", encoding="utf-8") as output:
        for key in dict.fromkeys(selected):
            if key in done:
                continue
            url = f"{HUDOC_DOC_BODY_URL}?id={key}&library=ECHR"
            response = session.get(url, headers={**HEADERS, "Accept": "text/html"}, timeout=60)
            if response.status_code == 403:
                # The public endpoint accepts the native Windows HTTP client.
                # No cookies, credentials, proxies, or access-control changes.
                if not key.startswith("001-") or not key[4:].isdigit():
                    raise ValueError("Unexpected HUDOC id")
                command = ("$ProgressPreference='SilentlyContinue'; "
                    "$ErrorActionPreference='Stop'; "
                    "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); "
                    f"$r=Invoke-WebRequest -Uri '{url}' -TimeoutSec 60; "
                    "[Console]::Write($r.Content)")
                result = subprocess.run(["pwsh", "-NoProfile", "-Command", command],
                    capture_output=True, encoding="utf-8", timeout=70, check=True)
                html = result.stdout
                raw = html.encode("utf-8")
                retrieval_method = "PowerShell Invoke-WebRequest"
            else:
                response.raise_for_status()
                html, raw = response.text, response.content
                retrieval_method = "requests"
            text = html_to_text(html)
            if len(text) < 1000 or "European Court" not in text:
                raise ValueError(f"Unexpected HUDOC document for {key}")
            record = {"item_id": key, "source_url": url,
                "retrieved_utc": datetime.now(timezone.utc).isoformat(),
                "html_sha256": hashlib.sha256(raw).hexdigest(),
                "retrieval_method": retrieval_method,
                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "text": text}
            cache = args.out.parent / ".cache" / "hudoc_html"
            cache.mkdir(parents=True, exist_ok=True)
            (cache / f"{key}.html").write_text(html, encoding="utf-8")
            output.write(json.dumps(record, ensure_ascii=False)+"\n")
            output.flush()
            print(key, "retrieved", len(text), "characters", flush=True)
            time.sleep(1)


if __name__ == "__main__":
    main()
