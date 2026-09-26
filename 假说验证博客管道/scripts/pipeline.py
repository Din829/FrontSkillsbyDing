"""One persistent author, independent review, optional reproduction, bounded repair."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from model_session import session, write_json
from rework import claim_repair, counts, policy, record

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "skills/evidence-check/scripts/gate.py"
ISSUE = {"type": "object", "additionalProperties": False, "properties": {
    "id": {"type": "string"}, "category": {"type": "string"}, "detail": {"type": "string"}},
    "required": ["id", "category", "detail"]}
REPLY = {"type": "object", "additionalProperties": False, "properties": {
    "status": {"type": "string", "enum": ["completed", "needs_input"]},
    "summary": {"type": "string"}, "issues": {"type": "array", "items": ISSUE},
    "execution_claim": {"type": "string", "enum": ["succeeded", "failed", "not_run", "unknown"]}},
    "required": ["status", "summary", "issues", "execution_claim"]}
TOPIC = {"type": "object", "additionalProperties": False, "properties": {
    "candidates": {"type": "array", "items": {"type": "object", "additionalProperties": False,
        "properties": {k: {"type": "string"} for k in ["id", "question", "source", "reader_value"]},
        "required": ["id", "question", "source", "reader_value"]}},
    "recommended_id": {"type": "string"}, "reason": {"type": "string"}},
    "required": ["candidates", "recommended_id", "reason"]}


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def check(run):
    process = subprocess.run([sys.executable, str(GATE), "check", str(run), "--output", str(run / "gate.json")],
                             capture_output=True, text=True, encoding="utf-8")
    if process.returncode != 0:
        raise RuntimeError(f"Gate could not run: {process.stderr}")
    return json.loads(process.stdout)


def selected_topic(run, topics, override=None):
    choice_file = run / "topic-choice.json"
    choice = override or (read(choice_file)["id"] if choice_file.exists() else topics["recommended_id"])
    candidates = {item["id"]: item for item in topics["candidates"]}
    if choice not in candidates:
        raise ValueError("Topic choice does not refer to a supplied candidate")
    return {**candidates[choice], "selection": "human" if override or choice_file.exists() else "recommended_no_response"}


def review_task(role, gate):
    if role != "review":
        return "在本研究目录下的新子目录只按说明复现，保留原始数据，不覆盖作者运行。"
    task = "按审查skill先独立看原始材料，再对照作者结论。普通判断问题只记录；给同一问题稳定ID。"
    candidates = [i["detail"] for i in gate["issues"] if i.get("code") == "unclassified_numbers"]
    if candidates:
        # gate 只能机械识别已登记的实测数字；未登记的交给审查者看一眼，不另设关卡。
        task += ("gate 标出了未登记为实测结果的数字（格式为 序号:数值）：" + "；".join(candidates)
                 + "。请确认其中有没有被当作实测结果陈述、却找不到来源的；有则按 numeric_mismatch 记录。")
    return task


def finish(run, state, gate):
    fatal = policy()["fatal_categories"]
    review_issues = [i for value in state.get("reviews", {}).values() for i in value["issues"]]
    issues = gate["issues"] + review_issues
    unresolved = [i for i in issues if i["category"] in fatal]
    complete = (run / "article.md").exists() and gate["status"] != "incomplete"
    state["status"] = "needs_decision" if unresolved else ("draft_complete" if complete else "incomplete")
    if not unresolved and any(r.get("status") == "needs_input" for r in state.get("reviews", {}).values()):
        state["status"] = "review_pending"
    report = {"status": state["status"], "gate_status": gate["status"], "issues": issues,
              "rework": counts(run), "author_thread": state.get("author_thread"),
              "note": "Warnings remain visible; no publication is performed"}
    write_json(run / "pipeline-report.json", report)
    write_json(run / "pipeline-state.json", state)
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return 2 if unresolved else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--brief", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--through", choices=["topic", "author", "review", "draft"], default="draft")
    parser.add_argument("--topic-choice")
    parser.add_argument("--reproduce", action="store_true")
    args = parser.parse_args()
    run = args.run.resolve()
    if not run.is_relative_to(ROOT / "runs") or run == ROOT / "runs":
        parser.error("Use a named research directory under this pipeline's runs/")
    if args.verify:
        result = check(run)
        print(json.dumps(result, ensure_ascii=False))
        return 2 if result["status"] == "blocked" else 0
    if args.resume:
        state = read(run / "pipeline-state.json")
        if state.get("version") != 2:
            parser.error("Historical runs use their archived runner; this entry resumes version 2")
    else:
        if args.brief is None:
            parser.error("A sourced --brief is required")
        brief = args.brief.read_text(encoding="utf-8")
        run.mkdir(parents=True, exist_ok=False)
        (run / "brief.md").write_text(brief, encoding="utf-8")
        write_json(run / "run.json", {"run_id": run.name, "budget": {"status": "within"}})
        state = {"version": 2, "attempts": [], "author_thread": None, "reviews": {}, "status": "running"}
    brief_hash = hashlib.sha256((run / "brief.md").read_bytes()).hexdigest()
    if state.get("brief_sha256") not in (None, brief_hash):
        record(run, "input_changed", reason="Brief changed; same author reconsiders it, existing repair counts stay")
        state.pop("topics", None)
        state.pop("author_done", None)
        state["reviews"] = {}
    state["brief_sha256"] = brief_hash
    write_json(run / "pipeline-state.json", state)

    def call(role, task, skills, *, same_author=False, schema=REPLY, resume_id=None):
        manifest = read(run / "run.json")
        if manifest.get("budget", {}).get("status") == "exceeded":
            raise PermissionError("Authorization does not permit another model call; retain the report")
        instructions = "\n".join(str(ROOT / "skills" / name / "SKILL.md") for name in skills)
        prompt = (f"执行本研究的 {role} 职责。工作目录为 {run}。先读 brief.md、{ROOT / 'policy.json'}，"
                  f"再按需读这些自包含技能：\n{instructions}\n本次任务：{task}\n"
                  "机器格式见本管道 skills/evidence-check/references/contract.md。只写本研究目录。"
                  "会话日志与pipeline-state.json由编排器维护，不是研究输入，也不要读取或改写它们。"
                  "返工事件由编排器记录；同一问题的ID沿用已有ID，不要靠改名重置次数。")
        folder = run / "sessions" / f"{len(state['attempts']):02d}-{role}"
        state["attempts"].append({"role": role, "path": folder.relative_to(run).as_posix(), "status": "running"})
        write_json(run / "pipeline-state.json", state)
        try:
            meta = session(prompt, folder, schema, workspace=run, allow_write=True,
                           resume_id=state["author_thread"] if same_author else resume_id)
            answer = read(folder / "answer.txt")
        except Exception as error:
            process_file = folder / "process.json"
            if same_author and state["author_thread"] is None and process_file.exists():
                recorded_threads = read(process_file).get("thread_ids", [])
                if recorded_threads:
                    state["author_thread"] = recorded_threads[0]
            state["attempts"][-1].update(status="interrupted", reason=str(error))
            state["status"] = "needs_attention"
            write_json(run / "pipeline-state.json", state)
            raise
        if same_author:
            state["author_thread"] = meta["thread_ids"][0]
        state["attempts"][-1].update(status="completed", thread_id=meta["thread_ids"][0])
        write_json(run / "pipeline-state.json", state)
        return answer, meta["thread_ids"][0]

    if "topics" not in state:
        state["topics"], _ = call("topic", "只提出有真实来源的候选并推荐，不开始正式实验。没有真实工作问题时不编造团队经历。",
                                 ["topic-hypothesis", "content-research"], same_author=True, schema=TOPIC)
        write_json(run / "topic-options.json", state["topics"])
        write_json(run / "pipeline-state.json", state)
        print(json.dumps(state["topics"], ensure_ascii=False), flush=True)
    if args.through == "topic":
        return 0
    if not state["topics"]["candidates"]:
        state["status"] = "needs_input"
        write_json(run / "pipeline-state.json", state)
        return 0
    chosen = selected_topic(run, state["topics"], args.topic_choice)
    previous = state.get("selected_topic")
    if previous and previous["id"] != chosen["id"]:
        record(run, "input_changed", reason="Human changed the topic; same author revisits it without resetting repair counts")
        state["author_done"] = False
        state["reviews"] = {}
    state["selected_topic"] = chosen
    write_json(run / "selected-topic.json", chosen)
    if not state.get("author_done"):
        answer, _ = call("author", f"按选定问题完成设计、真实任务校准和天花板预检、实际实验、文章与实测数字台账。"
                         f"选择为：{json.dumps(chosen, ensure_ascii=False)}。审查另有人负责。",
                         ["experiment-design", "experiment-run", "content-write", "evidence-check"], same_author=True)
        manifest = read(run / "run.json")
        manifest["execution_claim"] = answer["execution_claim"]
        write_json(run / "run.json", manifest)
        state["author_done"] = answer["status"] == "completed"
        state["status"] = answer["status"]
        write_json(run / "pipeline-state.json", state)
        if not state["author_done"] or args.through == "author":
            return 0
    gate = check(run)
    for role in ["review"] + (["reproduction"] if args.reproduce else []):
        if role not in state["reviews"]:
            answer, thread = call(role, review_task(role, gate), ["experiment-review"])
            state["reviews"][role] = {**answer, "thread_id": thread}
            write_json(run / "pipeline-state.json", state)
    gate = check(run)
    if args.through == "review":
        return finish(run, state, gate)
    fatal_categories = policy()["fatal_categories"]
    issues = gate["issues"] + [i for r in state["reviews"].values() for i in r["issues"]]
    # No automatic while/retry loop. A later explicit resume keeps the repair ledger.
    repairable = [i for i in issues if i["category"] in fatal_categories and i["category"] != "authorization"]
    eligible, _ = claim_repair(run, repairable)
    if eligible:
        answer, _ = call("repair", "只处理这些已预留次数的问题，不修改授权，不为消除其他提示返工："
                         + json.dumps(eligible, ensure_ascii=False), ["content-write", "evidence-check"], same_author=True)
        record(run, "repair_finished", issue_ids=[i["id"] for i in eligible], summary=answer["summary"])
        if answer["execution_claim"] != "unknown":
            manifest = read(run / "run.json")
            manifest["execution_claim"] = answer["execution_claim"]
            write_json(run / "run.json", manifest)
        gate = check(run)
        for role, previous in list(state["reviews"].items()):
            if any(i["category"] in fatal_categories for i in previous["issues"]):
                revised, thread = call(role + "-verify", "只复核上次指出的问题是否解决，未解决沿用原ID；不要求消除普通提示。",
                                       ["experiment-review"], resume_id=previous["thread_id"])
                state["reviews"][role] = {**revised, "thread_id": thread}
    return finish(run, state, gate)


if __name__ == "__main__":
    raise SystemExit(main())
