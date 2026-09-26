"""Real CLI continuity check, not a research-topic experiment."""
from pathlib import Path
import json
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model_session import session, write_json

out = ROOT / "reports/round-2/author-resume"
out.mkdir(parents=True, exist_ok=False)
schema = {"type": "object", "properties": {"marker": {"type": "string"}}, "required": ["marker"], "additionalProperties": False}
marker = secrets.token_hex(16)
first = session(f"This is a session continuity test. Remember the marker {marker} and return it. Use no tools or files.", out / "first", schema)
second = session("Return the exact marker I gave you in the previous turn. Use no tools or files.", out / "second", schema,
                 resume_id=first["thread_ids"][0])
answer = json.loads((out / "second/answer.txt").read_text(encoding="utf-8"))
assert answer["marker"] == marker
assert first["thread_ids"] == second["thread_ids"]
assert not first["tool_items"] and not second["tool_items"]
write_json(out / "result.json", {"same_thread": True, "marker_retained_without_resending": True,
           "tools_used": False, "thread_id": first["thread_ids"][0], "scope": "CLI continuity, not research quality"})
print("Author resume: real continuity confirmed")
