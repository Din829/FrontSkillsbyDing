"""Replay the original independent probes exactly once after reported fixes."""
from pathlib import Path
import importlib.util
import json
import shutil

HERE = Path(__file__).resolve().parent
target = HERE / "retest"
target.mkdir(exist_ok=False)
spec = importlib.util.spec_from_file_location("original_probe", HERE / "probe.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
probe.HERE = target
shutil.copy2(HERE / "component_worker.py", target / "component_worker.py")
probe.main()
records = {r["name"]: r for r in probe.RECORDS}
expected = {
    "metadata_valid_count": (0, "traceable", None),
    "metadata_beside_wrong_count": (2, "blocked", "value_mismatch"),
    "changed_wrong_value_same_issue": (2, "blocked", "value_mismatch"),
    "newline_hash_drift": (0, "warnings", "hash_drift"),
    "same_number_other_run": (2, "blocked", "source_run_mismatch"),
    "ruler_warning_continues": (0, "warnings", "ruler_record_note"),
    "honest_failed_process_report": (0, "warnings", "execution_failed_recorded"),
    "false_success_from_failed_process": (2, "blocked", "false_success"),
    "measurement_hidden_by_legacy_identifier": (0, "warnings", "unclassified_numbers"),
    "missing_document_registration": (0, "incomplete", "documents_missing"),
    "finish_with_incomplete_gate": (0, "incomplete", "documents_missing"),
    "valid_gate_before_incomplete_review": (0, "traceable", None),
    "finish_with_review_needs_input": (0, "review_pending", None),
    "capture_missing_manifest_fields": (0, "incomplete", "capture_run_id_missing"),
}
checks = []
for name, (code, status, issue) in expected.items():
    actual = records[name]
    ok = actual["exit_code"] == code and actual["answer"]["status"] == status
    if issue:
        ok = ok and any(i["code"] == issue for i in actual["answer"]["issues"])
    checks.append({"name": name, "matches_original_expectation": ok})
same = json.loads((target / "stable-id.json").read_text())["same"]
first = records["repair_first_and_second_same_process"]["answer"]
again = records["repair_after_new_process"]["answer"]
checks += [
    {"name": "same_issue_id_when_number_changes", "matches_original_expectation": same},
    {"name": "repair_limit_same_process", "matches_original_expectation": first["first_eligible"] == 1 and first["second_eligible"] == 0 and first["second_exhausted"] == 1 and first["counts"]["repair_rounds"] == 1},
    {"name": "repair_limit_new_process", "matches_original_expectation": again["first_eligible"] == 0 and again["first_exhausted"] == 1 and again["counts"]["repair_rounds"] == 1},
    {"name": "no_capture_side_effect_on_incomplete_input", "matches_original_expectation": not (target / "fixtures/empty-capture-manifest/should-not-run").exists()},
]
probe.write(target / "expectations.json", checks)
print(json.dumps({"checked_expectations": len(checks), "matching": sum(c["matches_original_expectation"] for c in checks)}, ensure_ascii=False))
# No repair loop. Keep a mismatch as a result and stop.
raise SystemExit(0 if all(c["matches_original_expectation"] for c in checks) else 1)
