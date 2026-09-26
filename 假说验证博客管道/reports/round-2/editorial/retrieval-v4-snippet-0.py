import json
from pathlib import Path

rows = json.loads(
    Path("results/experiment/result.json").read_text(encoding="utf-8")
)["rows"]

for mode in ("body", "body_metadata"):
    first = sum(row[mode]["hit1"] for row in rows)
    within = sum(row[mode]["hit3"] for row in rows)
    print(f"{mode}: first={first}/{len(rows)}, top3={within}/{len(rows)}")
