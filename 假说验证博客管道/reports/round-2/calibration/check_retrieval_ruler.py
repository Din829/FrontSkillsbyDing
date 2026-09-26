"""Calibrate the existing ranking ruler on its frozen article/question set.

This is a retrospective ruler check, not a new real-work experiment.
All outputs go beside this script; frozen inputs remain unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import random
import statistics
from pathlib import Path

METRICS = ("hit1", "hit3", "mrr")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def mean_scores(rows):
    return {name: statistics.mean(row[name] for row in rows) for name in METRICS}


def review_ceiling(root):
    base = root / "runs/review-behavior/results"
    cases_path = base / "snapshots/cases.json"
    refs_path = base / "snapshots/reference_answers.json"
    scores_path = base / "study/scores.json"
    cases, refs, scores = read(cases_path), read(refs_path), read(scores_path)
    evidence = [cases_path, refs_path, scores_path]
    rows = []
    for saved in scores["rows"]:
        folder = base / "study/sessions" / f"{saved['id']}_{saved['condition']}_{saved['repeat']}"
        answer_path, process_path = folder / "answer.txt", folder / "process.json"
        answer, process = read(answer_path), read(process_path)
        expected = refs[saved["id"]]
        decision = answer["decision"] == expected["decision"]
        required = (expected["required_issue"] in answer["issues"]
                    if expected["required_issue"] != "none" else not answer["issues"])
        extra = sorted(set(answer["issues"]) - set(expected["allowed_issues"]))
        primary = bool(decision and required and not extra)
        assert answer == saved["answer"]
        assert primary == saved["primary_pass"]
        evidence.extend((answer_path, process_path))
        rows.append({"id": saved["id"], "condition": saved["condition"], "repeat": saved["repeat"],
                     "original_primary_pass": primary, "decision_correct": decision,
                     "required_issue_found": bool(required), "extra_issues": extra,
                     "exit_code": process["exit_code"], "answer": answer})
    groups = {}
    for condition in ("generic", "skills"):
        group = [row for row in rows if row["condition"] == condition]
        groups[condition] = {
            "n": len(group), "original_primary_pass": sum(r["original_primary_pass"] for r in group),
            "decision_correct": sum(r["decision_correct"] for r in group),
            "required_issue_found": sum(r["required_issue_found"] for r in group),
            "remaining_original_score_slots": sum(not r["original_primary_pass"] for r in group)}
    return {"scope": "Read-only recomputation; original labels and scores are not changed.",
            "cases": cases, "groups": groups, "rows": rows,
            "sources": [{"path": str(p.relative_to(root)), "sha256": sha(p)} for p in evidence]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pipeline-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--random-draws", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20260926)
    args = parser.parse_args()
    root = args.pipeline_root.resolve()
    base = root / "runs/retrieval-v4/results/experiment"
    source_paths = [base / name for name in ("corpus.json", "queries.json", "result.json")]
    module_path = root / "runs/retrieval-v4/results/run_experiment.py"
    before = {str(p.relative_to(root)): sha(p) for p in source_paths + [module_path]}
    corpus, queries, saved = map(read, source_paths)
    documents = [doc["path"] for doc in corpus]
    ids = {path: number for number, path in enumerate(documents)}
    saved_rows = {row["id"]: row for row in saved["rows"]}
    spec = importlib.util.spec_from_file_location("frozen_retrieval_ruler", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def score(ranking, relevant):
        measured = module.metrics(ranking, relevant)
        # Independent rank lookup checks actual per-query results, not a PASS flag.
        rank = min(ranking.index(path) + 1 for path in relevant)
        independent = {"hit1": int(rank == 1), "hit3": int(rank <= 3),
                       "mrr": 1 / rank, "first_relevant_rank": rank}
        assert measured == independent
        return {**measured, "ranking_document_indices": [ids[path] for path in ranking]}

    rows = []
    for query in queries:
        relevant = set(query["relevant_paths"])
        assert relevant and relevant <= set(documents), query["id"]
        oracle = sorted(documents, key=lambda path: (path not in relevant, path))
        bad = sorted(documents, key=lambda path: (path in relevant, path))
        row = {"id": query["id"], "query": query["query"], "relevant_paths": sorted(relevant),
               "oracle": score(oracle, relevant), "known_bad": score(bad, relevant)}
        for condition in ("body", "body_metadata"):
            ranking = [item["path"] for item in saved_rows[query["id"]][condition]["ranking"]]
            assert len(ranking) == len(documents) and set(ranking) == set(documents)
            row[condition] = score(ranking, relevant)
            for metric in METRICS:
                assert row[condition][metric] == saved_rows[query["id"]][condition][metric]
        rows.append(row)
    summary = {condition: mean_scores([row[condition] for row in rows])
               for condition in ("oracle", "known_bad", "body", "body_metadata")}
    # Exact floating accumulation may differ; compare original per-query numbers above.
    rng = random.Random(args.seed)
    random_runs = []
    for draw in range(args.random_draws):
        random_rows = []
        for query in queries:
            ranking = documents.copy()
            rng.shuffle(ranking)
            random_rows.append({"id": query["id"], **score(ranking, set(query["relevant_paths"]))})
        random_runs.append({"draw": draw, "summary": mean_scores(random_rows), "rows": random_rows})
    distribution = {}
    for metric in METRICS:
        values = [run["summary"][metric] for run in random_runs]
        distribution[metric] = {"mean": statistics.mean(values), "stdev": statistics.stdev(values),
                                "min": min(values), "median": statistics.median(values), "max": max(values)}
    remaining = {condition: {
        "hit1_misses": sum(1 - row[condition]["hit1"] for row in rows),
        "hit3_misses": sum(1 - row[condition]["hit3"] for row in rows),
        "mrr_to_oracle": 1 - summary[condition]["mrr"]}
        for condition in ("body", "body_metadata")}
    result = {"scope": "Retrospective ranking-ruler calibration on frozen real articles and constructed queries; not a real-work trial.",
              "documents": documents, "questions": len(queries), "seed": args.seed,
              "random_draws": args.random_draws, "source_sha256": before,
              "summary": summary, "remaining_to_oracle": remaining,
              "random_distribution": distribution, "rows": rows, "random_runs": random_runs}
    output = Path(__file__).resolve().parent
    write(output / "retrieval-ruler.json", result)
    review = review_ceiling(root)
    write(output / "review-ceiling.json", review)
    assert before == {str(p.relative_to(root)): sha(p) for p in source_paths + [module_path]}
    print(json.dumps({"summary": summary, "random_distribution": distribution,
                      "remaining_to_oracle": remaining, "review_groups": review["groups"],
                      "source_inputs_unchanged": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
