"""Second pass over public_record.json: keep only issues/PRs that are actually about the release.

GitHub search is loose ("openai 3" matches a lot). This pass fetches each hit's
body and keeps it when title or body contains a strict marker. Strict markers
for openai 3.0.0: 'httpx2', 'openai 3.0', 'openai>=3', 'openai<3', 'openai 3.x',
'openai==3', 'openai v3'. Writes public_record_strict.json with, per dependent
repo: the earliest matching issue/PR, its created_at, and its closed_at.

    uv run python scripts/classify_record.py --target openai --release 3.0.0
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

STRICT = re.compile(r"httpx2|openai\s*(?:>=|<|==|~=)\s*3|openai\s+3\.\d|openai\s+v?3(?:\.x|\.0)|"
                    r"openai-python.*3\.0\.0|openai 3 ?\.0\.0|upgrade.*openai.*3", re.I)


def fetch_body(repo: str, number: int) -> str:
    r = subprocess.run(["gh", "api", f"repos/{repo}/issues/{number}", "--jq", ".body // \"\""],
                       capture_output=True, text=True, encoding="utf-8")
    return r.stdout if r.returncode == 0 else ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--release", required=True)
    args = ap.parse_args()
    root = Path(f"data/{args.target}-{args.release}")
    record = json.loads((root / "public_record.json").read_text(encoding="utf-8"))
    release_at = datetime.fromisoformat(json.loads((root / "population.json").read_text(encoding="utf-8"))
                                        ["meta"]["release_uploaded_at"])

    strict: dict[str, dict] = {}
    for repo, entry in record.items():
        hits = [h for h in entry["hits"] if "error" not in h]
        kept = []
        for h in hits:
            text = h["title"]
            if not STRICT.search(text):
                body = fetch_body(repo, h["number"])
                time.sleep(0.8)
                text = h["title"] + "\n" + body
            if STRICT.search(text):
                kept.append(h)
        kept.sort(key=lambda h: h["created_at"])
        first = kept[0] if kept else None
        strict[repo] = {
            "dependents": entry["dependents"],
            "matching": kept,
            "first_report": None if first is None else {
                "url": first["html_url"], "title": first["title"], "is_pr": first["is_pr"],
                "created_at": first["created_at"], "closed_at": first["closed_at"],
                "hours_after_release": round((datetime.fromisoformat(first["created_at"].replace("Z", "+00:00"))
                                              - release_at).total_seconds() / 3600, 1),
                "hours_to_close": None if not first["closed_at"] else round(
                    (datetime.fromisoformat(first["closed_at"].replace("Z", "+00:00"))
                     - datetime.fromisoformat(first["created_at"].replace("Z", "+00:00"))).total_seconds() / 3600, 1),
            },
        }
        if kept:
            print(f"  {repo:<45} {len(kept)} matching; first {first['created_at'][:10]} "
                  f"+{strict[repo]['first_report']['hours_after_release']}h  {first['title'][:70]}")

    out = root / "public_record_strict.json"
    out.write_text(json.dumps(strict, indent=2), encoding="utf-8")
    n = sum(1 for v in strict.values() if v["first_report"])
    print(f"{n}/{len(strict)} repos have a public report about {args.target} {args.release} -> {out}")


if __name__ == "__main__":
    main()
