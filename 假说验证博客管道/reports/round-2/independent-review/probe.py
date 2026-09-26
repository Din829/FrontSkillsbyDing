"""Independent v2 gate/repair component probes. Synthetic files, real subprocesses, no model."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
GATE = ROOT / "skills/evidence-check/scripts/gate.py"
RECORDS = []


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def ref(root, relative):
    return {"path": relative, "sha256": hashlib.sha256((root / relative).read_bytes()).hexdigest()}


def execute(name, args, expectation):
    process = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
    try:
        answer = json.loads(process.stdout)
    except ValueError:
        answer = None
    record = {"name": name, "command": args, "expectation": expectation,
              "exit_code": process.returncode, "stdout": process.stdout, "stderr": process.stderr,
              "answer": answer, "gate_sha256": hashlib.sha256(GATE.read_bytes()).hexdigest()}
    RECORDS.append(record)
    write(HERE / "results.json", RECORDS)
    print(json.dumps({"name": name, "exit_code": process.returncode,
                      "status": answer.get("status") if isinstance(answer, dict) else None}, ensure_ascii=False))
    return record


def fixture(name, failure=False):
    root = HERE / "fixtures" / name
    root.mkdir(parents=True, exist_ok=False)
    write(root / "run.json", {"run_id": name})
    code = "import json;from pathlib import Path;" + \
           "Path('results/metrics.json').write_text(json.dumps({'run_id':" + repr(name) + \
           ", 'metrics': {'correct': {'value':len(['a','b','c','d','e','f']),'unit':'cases'}}}));" + \
           "print('Synthetic local fixture computation');raise SystemExit(" + str(3 if failure else 0) + ")"
    execute(name + "_capture", [sys.executable, str(GATE), "capture", str(root), "--", sys.executable, "-c", code],
            "Actual local subprocess; exit 1 for intentionally failed process, otherwise 0")
    write(root / "results/ruler.json", {"status": "passed", "note": "Synthetic fixture only, not research calibration"})
    manifest = {"run_id": name, "execution_claim": "succeeded", "execution": ref(root, "results/execution.json"),
                "ruler": ref(root, "results/ruler.json"), "documents": []}
    write(root / "run.json", manifest)
    set_article(root, "BM25 / H1 / v1.2: measured 6 cases.", "6")
    return root


def set_article(root, article, number, *, kind="measurement", level="measured", source_run=None):
    (root / "article.md").write_text(article, encoding="utf-8")
    scan = execute(root.name + "_scan", [sys.executable, str(GATE), "scan", str(root / "article.md")],
                   "Metadata numbers marked, true count remains candidate")
    token = [item for item in scan["answer"] if item["token"] == number][-1]
    source = ref(root, "results/metrics.json")
    source.update(run_id=source_run or root.name, pointer="/metrics/correct", unit="cases")
    claims = {"run_id": root.name, "draft_sha256": ref(root, "article.md")["sha256"],
              "claims": [{"id": "count-result", "text": article, "level": level, "scope": "synthetic local fixture"}],
              "numbers": [{"index": token["index"], "token": number, "kind": kind,
                           "claim_id": "count-result", "unit": "cases", "ref": source}]}
    write(root / "claims.json", claims)
    manifest = read(root / "run.json")
    manifest["documents"] = [{"draft": ref(root, "article.md"), "claims": "claims.json"}]
    write(root / "run.json", manifest)


def check(root, name, expected):
    return execute(name, [sys.executable, str(GATE), "check", str(root), "--strict", "--output", str(root / "gate.json")], expected)


def worker(root, operation):
    return [sys.executable, str(HERE / "component_worker.py"), str(ROOT), str(root), operation]


def main():
    snapshot = HERE / "reviewed-source"
    snapshot.mkdir(exist_ok=False)
    versions = {}
    for relative in ["policy.json", "scripts/pipeline.py", "scripts/model_session.py", "scripts/rework.py", "skills/evidence-check/scripts/gate.py"]:
        original = ROOT / relative
        versions[relative] = hashlib.sha256(original.read_bytes()).hexdigest()
        target = snapshot / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(original.read_bytes())
    write(HERE / "versions.json", versions)

    root = fixture("metadata-and-real-count")
    check(root, "metadata_valid_count", "exit 0, traceable, checked_measurements=1; metadata doesn't force bookkeeping")
    set_article(root, "BM25 / H1 / v1.2: measured 9 cases.", "9")
    first = check(root, "metadata_beside_wrong_count", "exit 2; actual count mismatch fatal despite identifier neighbors")
    set_article(root, "BM25 / H1 / v1.2: measured 8 cases.", "8")
    second = check(root, "changed_wrong_value_same_issue", "exit 2; value_mismatch ID identical to preceding case")
    ids_a = [i["id"] for i in first["answer"]["issues"] if i["code"] == "value_mismatch"]
    ids_b = [i["id"] for i in second["answer"]["issues"] if i["code"] == "value_mismatch"]
    write(HERE / "stable-id.json", {"first": ids_a, "second": ids_b, "same": ids_a == ids_b})
    execute("repair_first_and_second_same_process", worker(root, "repair_twice"), "first eligible 1, second exhausted 1, total rounds 1")
    execute("repair_after_new_process", worker(root, "repair_once"), "eligible 0, exhausted 1, total rounds still 1")

    root = fixture("newline-only")
    metrics = root / "results/metrics.json"
    metrics.write_bytes(metrics.read_bytes() + b"\r\n")
    check(root, "newline_hash_drift", "exit 0, hash_drift warning, actual measurement still checked")

    root = fixture("same-number-other-run")
    source = read(root / "results/metrics.json")
    source["run_id"] = "different-study"
    write(root / "results/metrics.json", source)
    set_article(root, "BM25 measured 6 cases.", "6", source_run="different-study")
    check(root, "same_number_other_run", "exit 2; source_run_mismatch despite same value and updated hash")

    root = fixture("ruler-needs-review")
    write(root / "results/ruler.json", {"status": "needs_review", "observations": "Good and bad labels alone do not settle validity"})
    check(root, "ruler_warning_continues", "exit 0, ruler status warning; no mechanical judgment of scientific validity")

    root = fixture("true-process-failure", failure=True)
    manifest = read(root / "run.json")
    manifest["execution_claim"] = "failed"
    write(root / "run.json", manifest)
    set_article(root, "The failed process produced 6 partial fixture cases; no success conclusion.", "6")
    check(root, "honest_failed_process_report", "exit 0; execution failure is a visible warning, measured partial output allowed")
    manifest = read(root / "run.json")
    manifest["execution_claim"] = "succeeded"
    write(root / "run.json", manifest)
    check(root, "false_success_from_failed_process", "exit 2; false_success fatal based on actual capture exit_code=3")

    root = fixture("identifier-classification-bypass")
    set_article(root, "BM25 measured 99 cases.", "99", kind="identifier")
    check(root, "measurement_hidden_by_legacy_identifier", "At least unclassified_numbers warning: 99 is not an automatically recognized identifier")

    root = fixture("missing-evidence-finish")
    manifest = read(root / "run.json")
    manifest["documents"] = []
    write(root / "run.json", manifest)
    check(root, "missing_document_registration", "exit 0 / incomplete, missing material alone is not fatal")
    execute("finish_with_incomplete_gate", worker(root, "finish_incomplete"), "Do not label unchecked research draft_complete when gate status is incomplete")

    root = fixture("review-needs-input-finish")
    check(root, "valid_gate_before_incomplete_review", "exit 0 / traceable")
    execute("finish_with_review_needs_input", worker(root, "finish_review_needs_input"), "Retain review needs_input; don't label research draft_complete")

    root = HERE / "fixtures/empty-capture-manifest"
    root.mkdir()
    write(root / "run.json", {})
    execute("capture_missing_manifest_fields", [sys.executable, str(GATE), "capture", str(root), "--", sys.executable, "-c", "from pathlib import Path;Path('should-not-run').touch()"],
            "incomplete / no command side effect; CLI exit status documented separately")
    write(HERE / "side-effect-check.json", {"should_not_run_exists": (root / "should-not-run").exists()})

    print("Independent first pass complete; mismatches are reported, no production edits or automatic test-repair loop.")


if __name__ == "__main__":
    main()
