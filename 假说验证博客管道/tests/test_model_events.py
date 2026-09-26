"""Regression from the real UTF-8 smoke failure, plus independent Unicode controls."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model_session import parse_events


class EventsTest(unittest.TestCase):
    def test_valid_unicode_is_not_a_record_boundary(self):
        rows = [{"type": "item.completed", "text": "a\u0085b\u2028c\u2029d"}, {"type": "turn.completed"}]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "events.jsonl"
            text = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n"
            path.write_text(text, encoding="utf-8")
            with self.assertRaises(json.JSONDecodeError):
                [json.loads(line) for line in text.splitlines()]
            self.assertEqual(rows, parse_events(path))

    def test_actual_failed_smoke_log(self):
        path = ROOT / "archive/round-1/runs/autonomous-smoke-v2/sessions/02-experiment-run/events.jsonl"
        events = parse_events(path)
        self.assertEqual("turn.completed", events[-1]["type"])
        self.assertEqual(1, sum(e["type"] == "thread.started" for e in events))
        commands = [e["item"] for e in events if e["type"] == "item.completed"
                    and e.get("item", {}).get("type") == "command_execution"]
        self.assertTrue(any("python -B scripts/capture_execution.py" in i["command"]
                            and i["exit_code"] == 0 for i in commands))

    def test_malformed_record_is_not_silently_skipped(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "events.jsonl"
            path.write_text('{"type": "turn.completed"}\n{"broken":\n', encoding="utf-8")
            with self.assertRaises(json.JSONDecodeError):
                parse_events(path)


if __name__ == "__main__":
    unittest.main()
