import json
from pathlib import Path

answer = json.loads(Path(
    "results/study/sessions/c02_generic_0/answer.txt"
).read_text(encoding="utf-8"))
reference = json.loads(Path(
    "results/snapshots/reference_answers.json"
).read_text(encoding="utf-8"))["c02"]

extras = sorted(set(answer["issues"]) - set(reference["allowed_issues"]))
print(extras)
