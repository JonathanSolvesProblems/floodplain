"""Print resolution gaps in a population file."""

import json
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "data/openai-3.0.0/population.json"
p = json.load(open(path, encoding="utf-8"))
ex = p["exposed"]

for name in ("llm",):
    hit = next((e for e in ex if e["dependent"]["name"] == name), None)
    print(f"{name} ->", hit["source"] if hit else "absent")

print("--- repo but no tag:")
for e in ex:
    s = e["source"]
    if s and not s["tag"]:
        d = e["dependent"]
        print(f"  {d['name']:<40} {d['version']:<12} {s['owner']}/{s['repo']}")

print("--- no github url:")
print("  " + ", ".join(e["dependent"]["name"] for e in ex if e["source"] is None))
