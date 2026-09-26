"""Round-two policy behavior: real process fixtures, no model/network calls or mocks."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/evidence-check/scripts/gate.py"
spec = importlib.util.spec_from_file_location("round2_gate", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def ref(root, name):
    return {"path": name, "sha256": hashlib.sha256((root / name).read_bytes()).hexdigest()}


def invoke(*args):
    process = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True, encoding="utf-8")
    assert not process.stderr, process.stderr
    return process.returncode, json.loads(process.stdout)


def baseline(root):
    root.mkdir(parents=True)
    write(root / "run.json", {"run_id": "round2-fixture"})
    script = "import json; from pathlib import Path; truth=['a','b','c','d']; answers=['a','b','x','y']; correct=sum(a==b for a,b in zip(truth,answers)); Path('results/metrics.json').write_text(json.dumps({'run_id':'round2-fixture','metrics':{'correct':{'value':correct,'unit':'cases'},'total':{'value':len(truth),'unit':'cases'}}})); print(correct, len(truth))"
    code, _ = invoke("capture", root, "--", sys.executable, "-c", script)
    assert code == 0
    write(root / "results/ruler.json", {"status": "passed", "note": "No fixed good/bad schema; reviewer judges method"})
    text = "BM25 H1 v1.2 https://example.test/v3?id=4\n2026-09-26\n测得 2 件，正确率 50%。\n"
    (root / "article.md").write_text(text, encoding="utf-8")
    source = ref(root, "results/metrics.json")
    correct = dict(source, run_id="round2-fixture", pointer="/metrics/correct", unit="cases")
    total = dict(source, run_id="round2-fixture", pointer="/metrics/total", unit="cases")
    tokens = [t for t in gate.scan(text) if t["start"] >= text.index("测得")]
    claims = {"run_id": "round2-fixture", "draft_sha256": ref(root, "article.md")["sha256"], "claims": [{"id": "observed", "text": "测得 2 件，正确率 50%。", "level": "measured"}], "numbers": [
        {"index": tokens[0]["index"], "token": "2", "kind": "measurement", "claim_id": "observed", "unit": "cases", "ref": correct},
        {"index": tokens[1]["index"], "token": "50", "kind": "measurement", "claim_id": "observed", "unit": "percent", "calculation": {"op": "percent", "inputs": [correct, total]}}
    ]}
    write(root / "claims.json", claims)
    write(root / "run.json", {"run_id": "round2-fixture", "outcome": "refuted", "execution_claim": "succeeded", "execution": ref(root, "results/execution.json"), "ruler": ref(root, "results/ruler.json"), "documents": [{"draft": ref(root, "article.md"), "claims": "claims.json"}]})


def mutate(root, filename, fn):
    value = read(root / filename)
    fn(value)
    write(root / filename, value)


def mutation(root, name):
    if name == "source_reformatted":
        (root / "results/metrics.json").write_text(json.dumps(read(root / "results/metrics.json"), indent=4), encoding="utf-8")
    elif name == "other_run_same_number":
        mutate(root, "results/metrics.json", lambda d: d.__setitem__("run_id", "other-run"))
    elif name in {"changed_source_value", "changed_source_value_again"}:
        mutate(root, "results/metrics.json", lambda d: d["metrics"]["correct"].__setitem__("value", 3 if name == "changed_source_value" else 4))
    elif name == "source_unit_conflict":
        mutate(root, "results/metrics.json", lambda d: d["metrics"]["correct"].__setitem__("unit", "seconds"))
    elif name == "wrong_existing_pointer":
        mutate(root, "claims.json", lambda d: d["numbers"][0]["ref"].__setitem__("pointer", "/metrics/total"))
    elif name == "missing_pointer":
        mutate(root, "claims.json", lambda d: d["numbers"][0]["ref"].__setitem__("pointer", "/metrics/absent"))
    elif name == "wrong_calculation":
        mutate(root, "claims.json", lambda d: d["numbers"][1]["calculation"].__setitem__("op", "ratio"))
    elif name == "missing_source":
        (root / "results/metrics.json").rename(root / "results/metrics-unavailable.json")
    elif name == "ruler_failed":
        mutate(root, "results/ruler.json", lambda d: d.__setitem__("status", "failed"))
    elif name == "ruler_bad_cases":
        mutate(root, "results/ruler.json", lambda d: d.__setitem__("cases", [{"label": "bad", "expected": False, "observed": True}]))
        mutate(root, "run.json", lambda d: d.__setitem__("ruler", ref(root, "results/ruler.json")))
    elif name == "ruler_missing":
        mutate(root, "run.json", lambda d: d.pop("ruler"))
    elif name == "unregistered_number":
        mutate(root, "claims.json", lambda d: d["numbers"].pop())
    elif name == "legacy_classification_no_reason":
        mutate(root, "claims.json", lambda d: d["numbers"].append({"index": 0, "token": "25", "kind": "identifier"}))
    elif name == "manual_identifier_hides_measurement":
        text = "BM25 measured 99 cases."
        (root / "article.md").write_text(text, encoding="utf-8")
        mutate(root, "results/metrics.json", lambda d: d["metrics"]["correct"].__setitem__("value", 6))
        mutate(root, "run.json", lambda d: d["documents"][0].__setitem__("draft", ref(root, "article.md")))
        write(root / "claims.json", {"run_id": "round2-fixture", "draft_sha256": ref(root, "article.md")["sha256"], "claims": [{"id": "observed", "text": text, "level": "measured"}], "numbers": [{"index": 1, "token": "99", "kind": "identifier", "claim_id": "observed", "unit": "cases", "ref": dict(ref(root, "results/metrics.json"), run_id="round2-fixture", pointer="/metrics/correct", unit="cases")}]})
    elif name == "missing_claims":
        (root / "claims.json").rename(root / "claims-unavailable.json")
    elif name == "missing_execution":
        mutate(root, "run.json", lambda d: d.pop("execution"))
    elif name == "empty_documents":
        mutate(root, "run.json", lambda d: d.__setitem__("documents", []))
    elif name in {"empty_manifest", "null_manifest", "array_manifest"}:
        write(root / "run.json", {"empty_manifest": {}, "null_manifest": None, "array_manifest": ["x"]}[name])
    elif name == "path_escape":
        mutate(root, "claims.json", lambda d: d["numbers"][0]["ref"].__setitem__("path", "../outside.json"))
    elif name == "report_after_budget":
        mutate(root, "run.json", lambda d: d.__setitem__("budget", {"status": "exceeded"}))
    elif name in {"false_success", "honest_failure"}:
        (root / "results").rename(root / "previous-results")
        code, result = invoke("capture", root, "--", sys.executable, "-c", "import sys; print('failed honestly'); sys.exit(7)")
        assert code == 1 and result["exit_code"] == 7
        shutil.copy2(root / "previous-results/metrics.json", root / "results/metrics.json")
        shutil.copy2(root / "previous-results/ruler.json", root / "results/ruler.json")
        mutate(root, "run.json", lambda d: d.__setitem__("execution", ref(root, "results/execution.json")))
        if name == "honest_failure":
            mutate(root, "run.json", lambda d: d.__setitem__("execution_claim", "failed"))
            (root / "article.md").write_text("实验执行失败，未产生有效结果。", encoding="utf-8")
            mutate(root, "run.json", lambda d: d["documents"][0].__setitem__("draft", ref(root, "article.md")))
            write(root / "claims.json", {"run_id": "round2-fixture", "draft_sha256": ref(root, "article.md")["sha256"], "claims": [{"id": "failure", "text": "实验执行失败，未产生有效结果。", "level": "read"}], "numbers": []})


def main():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    trial = ROOT / "tests/round2-gate-artifacts" / stamp
    baseline(trial / "baseline")
    expected = {
        "baseline": "traceable", "source_reformatted": "warnings", "other_run_same_number": "blocked",
        "changed_source_value": "blocked", "changed_source_value_again": "blocked", "source_unit_conflict": "blocked",
        "wrong_existing_pointer": "blocked", "missing_pointer": "incomplete", "wrong_calculation": "blocked",
        "missing_source": "incomplete", "ruler_failed": "warnings", "ruler_bad_cases": "traceable", "ruler_missing": "warnings",
        "unregistered_number": "warnings", "legacy_classification_no_reason": "traceable", "manual_identifier_hides_measurement": "warnings", "missing_claims": "incomplete",
        "missing_execution": "incomplete", "empty_documents": "incomplete", "empty_manifest": "incomplete",
        "null_manifest": "incomplete", "array_manifest": "incomplete", "path_escape": "blocked", "report_after_budget": "traceable",
        "false_success": "blocked", "honest_failure": "warnings",
    }
    results, reports = [], {}
    for name, status in expected.items():
        directory = trial / name
        if name != "baseline":
            shutil.copytree(trial / "baseline", directory)
            mutation(directory, name)
        exit_code, report = invoke("check", directory, "--strict")
        write(directory / "check.json", report)
        expected_exit = 2 if status == "blocked" else 0
        passed = report["status"] == status and exit_code == expected_exit
        if name == "manual_identifier_hides_measurement":
            passed = passed and report["checked_measurements"] == 0 and any(i["code"] == "unclassified_numbers" and i["severity"] == "warning" and "99" in i["detail"] for i in report["issues"])
        results.append({"case": name, "expected_status": status, "status": report["status"], "exit_code": exit_code, "passed": passed, "issues": report["issues"]})
        reports[name] = report
    ids = lambda name: {i["id"] for i in reports[name]["issues"] if i["code"] == "value_mismatch"}
    results.append({"case": "stable_issue_id_across_changed_numeric_values", "passed": bool(ids("changed_source_value")) and ids("changed_source_value") == ids("changed_source_value_again")})
    scan_path = trial / "baseline/article.md"
    _, all_tokens = invoke("scan", scan_path)
    _, candidates = invoke("scan", scan_path, "--candidates")
    results.append({"case": "automatic_metadata_skips_preserve_indices", "passed": [t["token"] for t in candidates] == ["2", "50"] and [t["index"] for t in candidates] == [t["index"] for t in all_tokens if not t["ignore_reason"]] and len(all_tokens) > len(candidates)})
    budget = trial / "capture_budget"
    budget.mkdir()
    write(budget / "run.json", {"run_id": "budget", "budget": {"status": "exceeded"}})
    code, report = invoke("capture", budget, "--", sys.executable, "-c", "from pathlib import Path; Path('executed.txt').write_text('should not run')")
    write(budget / "capture.json", report)
    results.append({"case": "capture_budget_blocks_actual_side_effect", "passed": code == 2 and not (budget / "executed.txt").exists() and not (budget / "results").exists()})
    for existing in ("review-behavior", "retrieval-v4"):
        directory = ROOT / "runs" / existing
        if (directory / "run.json").exists():
            code, report = invoke("check", directory, "--strict")
            write(trial / (existing + "-historical-check.json"), report)
            results.append({"case": "historical_claims_" + existing, "passed": code == 0 and report["status"] != "blocked", "status": report["status"], "checked_measurements": report["checked_measurements"]})
    report = {"gate_sha256": gate.sha(SCRIPT), "policy_sha256": gate.sha(ROOT / "policy.json"), "created_at": stamp, "artifact_dir": str(trial), "passed": sum(r["passed"] for r in results), "total": len(results), "cases": results}
    write(trial / "report.json", report)
    write(ROOT / "tests/round2-gate-latest.json", report)
    print(json.dumps({"passed": report["passed"], "total": report["total"], "failures": [r for r in results if not r["passed"]], "artifact_dir": str(trial)}, ensure_ascii=False, indent=2))
    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
