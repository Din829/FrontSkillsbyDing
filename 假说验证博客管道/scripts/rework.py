"""Append-only repair accounting; the limit comes from the shared policy."""
import json
from datetime import datetime, timezone
from pathlib import Path

POLICY = Path(__file__).resolve().parents[1] / "policy.json"


def policy():
    return json.loads(POLICY.read_text(encoding="utf-8"))


def events(run):
    path = Path(run) / "rework.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").split("\n") if line.strip()] if path.exists() else []


def record(run, event, **fields):
    path = Path(run) / "rework.jsonl"
    with path.open("a", encoding="utf-8") as output:
        output.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(), "event": event, **fields}, ensure_ascii=False) + "\n")


def counts(run):
    items = events(run)
    attempts = [item for item in items if item["event"] == "repair_started"]
    return {"repair_rounds": len(attempts),
            "issue_attempts": {issue: sum(issue in a["issue_ids"] for a in attempts)
                               for issue in {i for a in attempts for i in a["issue_ids"]}},
            "reasons": [{"issue_ids": a["issue_ids"], "reasons": a["reasons"]} for a in attempts]}


def claim_repair(run, issues):
    """Reserve before doing work, so a crash/resume cannot reset the limit."""
    issues = list({issue["id"]: issue for issue in issues}.values())
    used = counts(run)["issue_attempts"]
    limit = policy()["max_repairs_per_issue"]
    eligible = [i for i in issues if used.get(i["id"], 0) < limit]
    exhausted = [i for i in issues if used.get(i["id"], 0) >= limit]
    if exhausted:
        record(run, "disagreement_retained", issue_ids=[i["id"] for i in exhausted], reasons=[i["detail"] for i in exhausted])
    if eligible:
        record(run, "repair_started", issue_ids=[i["id"] for i in eligible], reasons=[i["detail"] for i in eligible])
    return eligible, exhausted
