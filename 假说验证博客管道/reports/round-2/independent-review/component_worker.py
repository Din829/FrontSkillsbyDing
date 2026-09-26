"""Call real repair/finish components in fresh Python processes; not a model mock."""
from pathlib import Path
import json
import sys

root, fixture, operation = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
sys.path.insert(0, str(root / "scripts"))
from rework import claim_repair, counts
from pipeline import finish

gate = json.loads((fixture / "gate.json").read_text(encoding="utf-8"))
if operation.startswith("repair_"):
    issues = [i for i in gate["issues"] if i["severity"] == "fatal"]
    first = claim_repair(fixture, issues)
    second = claim_repair(fixture, issues) if operation == "repair_twice" else None
    print(json.dumps({"first_eligible": len(first[0]), "first_exhausted": len(first[1]),
                      "second_eligible": len(second[0]) if second else None,
                      "second_exhausted": len(second[1]) if second else None,
                      "counts": counts(fixture)}, ensure_ascii=False))
else:
    state = {"reviews": {}, "author_thread": "synthetic-component-fixture-not-a-real-model-thread"}
    if operation == "finish_review_needs_input":
        state["reviews"]["review"] = {"status": "needs_input", "issues": [], "summary": "Cannot complete semantic review without the missing source context"}
    finish(fixture, state, gate)
