"""File-backed controller checks; no fake model or synthetic business result."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from pipeline import finish, review_task, selected_topic
from rework import claim_repair, counts


class WorkflowChecks(unittest.TestCase):
    def test_one_repair_survives_process_restart_and_changed_detail(self):
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            issue = {"id": "same-source-field", "category": "numeric_mismatch", "detail": "value differs"}
            accepted, _ = claim_repair(run, [issue, issue])
            self.assertEqual(1, len(accepted))
            code = "from rework import claim_repair; import json,sys; x=claim_repair(sys.argv[1],[{'id':'same-source-field','detail':'now a different number'}]); print(json.dumps(x))"
            proc = subprocess.run([sys.executable, "-c", code, str(run)], cwd=ROOT / "scripts", capture_output=True, text=True)
            self.assertEqual(0, proc.returncode, proc.stderr)
            self.assertEqual([], json.loads(proc.stdout)[0])
            self.assertEqual(1, counts(run)["repair_rounds"])
            self.assertEqual(1, counts(run)["issue_attempts"][issue["id"]])

    def test_recommendation_and_optional_human_choice(self):
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            topics = {"candidates": [{"id": "a"}, {"id": "b"}], "recommended_id": "a"}
            self.assertEqual("recommended_no_response", selected_topic(run, topics)["selection"])
            (run / "topic-choice.json").write_text('{"id":"b"}')
            self.assertEqual("b", selected_topic(run, topics)["id"])
            self.assertEqual("a", selected_topic(run, topics, "a")["id"])

    def test_warning_does_not_create_repair_or_block_draft(self):
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            (run / "article.md").write_text("Scoped result")
            state = {"reviews": {"review": {"issues": [{"id": "calibration", "category": "review", "detail": "Need a better control in a future study"}]}}}
            self.assertEqual(0, finish(run, state, {"status": "warnings", "issues": []}))
            self.assertEqual("draft_complete", state["status"])
            self.assertEqual(0, counts(run)["repair_rounds"])

    def test_incomplete_is_reportable_but_not_complete(self):
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            (run / "article.md").write_text("Draft without sources yet")
            state = {"reviews": {}}
            self.assertEqual(0, finish(run, state, {"status": "incomplete", "issues": []}))
            self.assertEqual("incomplete", state["status"])

    def test_unresolved_fatal_saves_report(self):
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            issue = {"id": "bad-number", "category": "numeric_mismatch", "detail": "Number contradicts source"}
            self.assertEqual(2, finish(run, {"reviews": {}}, {"status": "blocked", "issues": [issue]}))
            self.assertTrue((run / "pipeline-report.json").exists())

    def test_pending_review_is_not_claimed_complete(self):
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            (run / "article.md").write_text("Draft")
            state = {"reviews": {"review": {"status": "needs_input", "issues": []}}}
            self.assertEqual(0, finish(run, state, {"status": "traceable", "issues": []}))
            self.assertEqual("review_pending", state["status"])

    def test_unregistered_numbers_reach_reviewer(self):
        gate = {"issues": [{"code": "unclassified_numbers", "detail": "Semantic review candidates: 34:40"},
                           {"code": "hash_drift", "detail": "other"}]}
        self.assertIn("34:40", review_task("review", gate))
        self.assertNotIn("other", review_task("review", gate))
        self.assertNotIn("gate 标出", review_task("review", {"issues": []}))
        self.assertNotIn("34:40", review_task("reproduction", gate))


if __name__ == "__main__":
    unittest.main()
