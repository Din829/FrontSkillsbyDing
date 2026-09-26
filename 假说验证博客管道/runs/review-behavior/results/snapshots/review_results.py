"""Read-only independent accounting plus explicitly post-hoc semantic adjudication."""
from collections import Counter
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STUDY = ROOT / "runs/review-behavior/results/study"
EXPERIMENT = ROOT / "experiments/review_behavior"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    cases = {case["id"]: case["material"] for case in read(EXPERIMENT / "cases.json")}
    references = read(EXPERIMENT / "reference_answers.json")
    scores = read(STUDY / "scores.json")
    source_rows = {(r["id"], r["condition"], r["repeat"]): r for r in scores["rows"]}
    snapshot = read(STUDY / "design_snapshot.json")
    rules = (STUDY / "rule_snapshot.md").read_text(encoding="utf-8")
    expected_names = {f"{case}_{condition}_{repeat}" for case in cases for condition in ("generic", "skills") for repeat in range(2)}
    folders = sorted(d for d in (STUDY / "sessions").iterdir() if d.is_dir())
    assert {d.name for d in folders} == expected_names
    records, prompts, commands, schemas, thread_ids, event_counts = [], {}, set(), set(), [], Counter()
    for folder in folders:
        case, condition, repetition = folder.name.split("_")
        repeat = int(repetition)
        answer = read(folder / "answer.txt")
        process = read(folder / "process.json")
        prompt = (folder / "prompt.txt").read_text(encoding="utf-8")
        events = [json.loads(line) for line in (folder / "events.jsonl").read_text(encoding="utf-8").splitlines() if line]
        thread = [event["thread_id"] for event in events if event["type"] == "thread.started"]
        completed = [event for event in events if event["type"] == "turn.completed"]
        items = [event["item"] for event in events if "item" in event]
        tools = [item["type"] for item in items if item["type"] not in ("reasoning", "agent_message")]
        messages = [item["text"] for item in items if item["type"] == "agent_message"]
        event_counts.update(event["type"] for event in events)
        assert len(thread) == 1 and len(completed) == 1 and not tools
        assert process["thread_ids"] == thread and process["turn_completed"] and process["exit_code"] == 0 and not process["tool_items"]
        assert json.loads(messages[-1]) == answer
        assert process["prompt_sha256"] == hashlib.sha256(prompt.encode()).hexdigest()
        assert json.loads(prompt.split("\n待审查材料：\n", 1)[1]) == cases[case]
        thread_ids.extend(thread)
        schemas.add(sha(folder / "schema.json"))
        command = list(process["command"])
        for flag in ("-C", "-o", "--output-schema"):
            command[command.index(flag) + 1] = "<session-local-path>"
        commands.add(tuple(command))
        prompts[(case, condition, repeat)] = prompt
        expected = references[case]
        decision_ok = answer["decision"] == expected["decision"]
        verdict_ok = answer["verdict"] == expected["verdict"]
        required_found = expected["required_issue"] in answer["issues"] if expected["required_issue"] != "none" else not answer["issues"]
        extras = sorted(set(answer["issues"]) - set(expected["allowed_issues"]))
        primary = decision_ok and required_found and not extras
        original = source_rows[(case, condition, repeat)]
        assert original["answer"] == answer
        assert original["decision_ok"] == decision_ok and original["verdict_ok"] == verdict_ok
        assert original["primary_pass"] == primary and original["all_pass"] == (primary and verdict_ok)
        assert original["unexpected_issues"] == extras
        # These decisions were made after reading ALL answers, not inferred from labels.
        accepted_extra = {"c02_generic_0": "noise_or_selection: eight tries with best-of selection is explicitly in the material", "c09_generic_1": "scope_overreach: vendor support claim is transferred to untested current environment", "c09_skills_0": "scope_overreach: vendor support claim is transferred to untested current environment", "c09_skills_1": "scope_overreach: vendor support claim is transferred to untested current environment"}
        assert primary or folder.name in accepted_extra
        records.append({"session": folder.name, "case": case, "condition": condition, "repeat": repeat,
                        "thread_id": thread[0], "exit_code": process["exit_code"], "tool_item_count": len(tools),
                        "decision_ok": decision_ok, "required_issue_found": bool(required_found), "verdict_ok": verdict_ok,
                        "original_primary_pass": bool(primary), "original_unexpected_issues": extras,
                        "posthoc_semantic_acceptable": True,
                        "adjudication": accepted_extra.get(folder.name, "Reason and next action match supplied scenario; no material reasoning error found"),
                        "answer": answer, "duration_seconds": process["duration_seconds"], "usage": process["usage"],
                        "hashes": {name: sha(folder / name) for name in ("answer.txt", "process.json", "prompt.txt", "schema.json", "events.jsonl")}})
    assert len(set(thread_ids)) == 48 and len(commands) == 1 and len(schemas) == 1
    prompt_pairs = []
    for case in cases:
        for repeat in range(2):
            generic = prompts[(case, "generic", repeat)]
            skills = prompts[(case, "skills", repeat)]
            prefix, material = generic.split("\n待审查材料：\n", 1)
            expected = prefix + "\n适用工作规范：\n" + rules + "\n待审查材料：\n" + material
            assert skills == expected
            assert prompts[(case, "generic", 0)] == prompts[(case, "generic", 1)]
            assert prompts[(case, "skills", 0)] == prompts[(case, "skills", 1)]
            prompt_pairs.append({"case": case, "repeat": repeat, "only_rule_addition": True})
    assert snapshot["case_sha256"] == sha(EXPERIMENT / "cases.json")
    assert snapshot["reference_sha256"] == sha(EXPERIMENT / "reference_answers.json")
    assert snapshot["rule_sha256"] == hashlib.sha256(rules.encode()).hexdigest()
    groups = {}
    for condition in ("generic", "skills"):
        group = [r for r in records if r["condition"] == condition]
        groups[condition] = {"n": len(group), "original_primary_pass": sum(r["original_primary_pass"] for r in group),
                             "decision_correct": sum(r["decision_ok"] for r in group), "required_issue_found": sum(r["required_issue_found"] for r in group),
                             "verdict_correct": sum(r["verdict_ok"] for r in group),
                             "posthoc_semantic_acceptable": sum(r["posthoc_semantic_acceptable"] for r in group),
                             "input_tokens": sum(u["input_tokens"] for r in group for u in r["usage"]),
                             "output_tokens": sum(u["output_tokens"] for r in group for u in r["usage"])}
    summary = {"review_kind": "independent but non-blind post-hoc semantic review; reviewer was alerted to c02/c09 label disputes",
               "source_scores_sha256": sha(STUDY / "scores.json"), "original_summary": scores["summary"], "groups": groups,
               "integrity": {"sessions": len(records), "unique_thread_ids": len(set(thread_ids)), "successful_processes": len(records),
                             "tool_items_in_raw_events": 0, "normalized_command_variants": len(commands), "schema_variants": len(schemas),
                             "prompt_pairs_only_rule_addition": len(prompt_pairs), "snapshot_hashes_match": True, "raw_answers_equal_scored_answers": True,
                             "event_type_counts": dict(event_counts), "effective_model_id_recorded": False, "complete_system_context_frozen": False},
               "conclusion": "No added benefit observed on these straightforward closed-material cases; all four automatic failures are reasonable extra labels, not demonstrated reasoning failures. Post-hoc acceptance is not a preregistered score or a production reliability estimate.",
               "limits": ["Only twelve authored scenarios, two repeats per condition", "Generic condition already contains substantive evidence guidance and all issue labels", "Material assertions are assumed true: no real attachment verification", "Model selection inherited from CLI configuration rather than explicitly pinned in recorded command", "One non-blind independent semantic reviewer; no inter-rater agreement measured"],
               "sessions": records}
    (HERE / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"groups": groups, "integrity": summary["integrity"], "output": str(HERE / "summary.json")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
