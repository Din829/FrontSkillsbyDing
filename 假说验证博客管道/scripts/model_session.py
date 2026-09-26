"""Start or resume a GPT Codex session, preserving the actual execution record.

No API keys are read or copied. Uses the user's existing Codex authentication.
The CLI version is pinned because the installed older CLI failed the live probe.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

RUNTIME_PATH = Path(__file__).resolve().parents[1] / "runtime.json"


def write_json(path: Path, data: object) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def parse_events(path: Path) -> list[dict]:
    # JSONL separates records with LF. Unicode NEL/line separators inside valid
    # JSON strings are data; str.splitlines() incorrectly splits those too.
    return [json.loads(line) for line in path.read_text(encoding="utf-8").split("\n") if line.strip()]


def session(prompt: str, directory: Path, schema: dict | None = None,
            *, workspace: Path | None = None, allow_write: bool = False,
            resume_id: str | None = None) -> dict:
    directory.mkdir(parents=True, exist_ok=False)
    runtime = json.loads(RUNTIME_PATH.read_text(encoding="utf-8"))
    if not runtime["model"].startswith(("gpt-", "codex-")):
        raise ValueError("This backend is for GPT/Codex; Gemini requires its own authorized adapter")
    write_json(directory / "runtime.json", runtime)
    (directory / "prompt.txt").write_text(prompt, encoding="utf-8")
    npm = shutil.which("npm.cmd" if __import__("os").name == "nt" else "npm")
    if npm is None:
        raise RuntimeError("npm is required for the pinned Codex CLI")
    command = [npm, "exec", "--yes", f"--package={runtime['cli_package']}", "--", "codex",
               "--ask-for-approval", "never",
               "-s", "workspace-write" if allow_write else "read-only",
               "-C", str((workspace or directory).resolve()), "exec"]
    if resume_id:
        command += ["resume"]
    command += ["--skip-git-repo-check", "--json", "--model", runtime["model"],
                "-o", str((directory / "answer.txt").resolve())]
    if schema is not None:
        write_json(directory / "schema.json", schema)
        command += ["--output-schema", str((directory / "schema.json").resolve())]
    command += ([resume_id] if resume_id else []) + ["-"]
    start = time.monotonic()
    with (directory / "events.jsonl").open("w", encoding="utf-8") as out, \
         (directory / "stderr.txt").open("w", encoding="utf-8") as err:
        result = subprocess.run(command, input=prompt, text=True, encoding="utf-8",
                                stdout=out, stderr=err)
    meta = {"command": command, "exit_code": result.returncode,
            "duration_seconds": time.monotonic() - start, "event_parse_status": "pending"}
    write_json(directory / "process.json", meta)
    events = parse_events(directory / "events.jsonl")
    completed = [e for e in events if e.get("type") == "turn.completed"]
    tool_items = [e["item"] for e in events if e.get("type") == "item.completed"
                  and e.get("item", {}).get("type") not in ("agent_message", "reasoning")]
    meta.update({
        "command": command, "cli_package": runtime["cli_package"], "model_requested": runtime["model"],
        "runtime_sha256": hashlib.sha256(RUNTIME_PATH.read_bytes()).hexdigest(),
        "event_parse_status": "completed",
        "turn_completed": bool(completed),
        "thread_ids": [e["thread_id"] for e in events if e.get("type") == "thread.started"],
        "resume_from": resume_id,
        "usage": [e.get("usage", {}) for e in completed],
        "tool_items": tool_items,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "monetary_cost": None,
        "cost_note": "Existing account authentication; currency cost not reported by CLI",
    })
    write_json(directory / "process.json", meta)
    if result.returncode != 0 or not completed or not (directory / "answer.txt").exists():
        raise RuntimeError(f"Model session failed; inspect {directory}")
    if resume_id and meta["thread_ids"] != [resume_id]:
        raise RuntimeError(f"CLI did not resume the requested author thread; inspect {directory}")
    return meta


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--schema", type=Path)
    parser.add_argument("--resume-id")
    args = parser.parse_args()
    meta = session(args.prompt.read_text(encoding="utf-8"), args.output,
                   json.loads(args.schema.read_text(encoding="utf-8")) if args.schema else None,
                   resume_id=args.resume_id)
    print(json.dumps(meta, ensure_ascii=False))
