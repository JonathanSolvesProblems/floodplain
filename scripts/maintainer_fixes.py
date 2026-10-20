"""Record what each broken dependent's maintainer actually shipped, from GitHub, as data.

The site compares Floodplain's verified patch with the real fix. That comparison is only
worth anything if the real fix is fetched from the source rather than typed in, so this
writes data/<target>-<release>/maintainer_fixes.json and the site reads from it.

    uv run python scripts/maintainer_fixes.py --target openai --release 3.0.0
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
from datetime import datetime
from pathlib import Path

# The fix each maintainer shipped, by where it lives. Only the location is written here;
# every value shown on the site (the line, the timestamp, the title) is fetched.
KNOWN = {
    "llm": {"kind": "release", "repo": "simonw/llm", "tag": "0.32.1", "file": "pyproject.toml",
            "match": "openai", "followup": {"tag": "0.33", "match": ["openai", "httpx2"]}},
    "openinference-instrumentation-agno": {"kind": "pr", "repo": "Arize-ai/openinference", "number": 3574},
}


def gh(*args: str) -> str:
    r = subprocess.run(["gh", "api", *args], capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:300])
    return r.stdout


def file_lines(repo: str, tag: str, path: str, needles: list[str]) -> list[str]:
    raw = json.loads(gh(f"repos/{repo}/contents/{path}?ref={tag}"))
    text = base64.b64decode(raw["content"]).decode("utf-8")
    return [ln.strip() for ln in text.splitlines() if any(n in ln for n in needles)]


def release_time(repo: str, tag: str) -> str:
    return json.loads(gh(f"repos/{repo}/releases/tags/{tag}"))["published_at"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--release", required=True)
    args = ap.parse_args()
    root = Path(f"data/{args.target}-{args.release}")
    release_at = datetime.fromisoformat(
        json.loads((root / "population.json").read_text(encoding="utf-8"))["meta"]["release_uploaded_at"])

    out = {}
    for dep, spec in KNOWN.items():
        try:
            if spec["kind"] == "release":
                at = release_time(spec["repo"], spec["tag"])
                rec = {
                    "kind": "release", "repo": spec["repo"], "tag": spec["tag"], "published_at": at,
                    "url": f"https://github.com/{spec['repo']}/releases/tag/{spec['tag']}",
                    "lines": file_lines(spec["repo"], spec["tag"], spec["file"], [spec["match"]]),
                }
                f = spec.get("followup")
                if f:
                    rec["followup"] = {
                        "tag": f["tag"], "published_at": release_time(spec["repo"], f["tag"]),
                        "url": f"https://github.com/{spec['repo']}/releases/tag/{f['tag']}",
                        "lines": file_lines(spec["repo"], f["tag"], spec["file"], f["match"]),
                    }
            else:
                pr = json.loads(gh(f"repos/{spec['repo']}/pulls/{spec['number']}"))
                at = pr.get("merged_at") or pr["created_at"]
                rec = {"kind": "pr", "repo": spec["repo"], "number": spec["number"], "title": pr["title"],
                       "url": pr["html_url"], "published_at": at, "merged": bool(pr.get("merged_at"))}
            when = datetime.fromisoformat(rec["published_at"].replace("Z", "+00:00"))
            rec["hours_after_release"] = round((when - release_at).total_seconds() / 3600, 1)
            out[dep] = rec
            print(f"  {dep:<36} {rec['published_at']}  +{rec['hours_after_release']}h")
        except RuntimeError as e:
            print(f"  {dep:<36} could not fetch: {e}")

    (root / "maintainer_fixes.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"wrote {root / 'maintainer_fixes.json'}")


if __name__ == "__main__":
    main()
