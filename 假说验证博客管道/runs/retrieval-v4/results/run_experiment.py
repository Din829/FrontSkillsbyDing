"""Deterministic body BM25 vs body + fixed metadata boost on a frozen corpus."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
PIPELINE = ROOT.parents[1]
BLOG = PIPELINE.parent


def tokens(text):
    text = text.casefold()
    latin = re.findall(r"[a-z0-9_]+", text)
    east = []
    for span in re.findall(r"[\u3040-\u30ff\u3400-\u9fff]+", text):
        east.extend(span[i:i+2] for i in range(len(span)-1))
        if len(span) == 1:
            east.append(span)
    return latin + east


def index(documents):
    counts = [Counter(tokens(d)) for d in documents]
    df = Counter(term for counts_i in counts for term in counts_i)
    lengths = [sum(c.values()) for c in counts]
    return counts, df, lengths, sum(lengths) / len(lengths)


def bm25(query, idx):
    counts, df, lengths, average = idx
    n = len(counts)
    scores = []
    for counter, length in zip(counts, lengths):
        score = 0.0
        for term in sorted(set(tokens(query))):
            freq = counter[term]
            if freq:
                idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
                score += idf * freq * 2.5 / (freq + 1.5 * (0.25 + 0.75 * length / average))
        scores.append(score)
    return scores


def metrics(ranked, relevant):
    rank = next((i for i, doc in enumerate(ranked, 1) if doc in relevant), None)
    return {"hit1": int(rank == 1), "hit3": int(rank is not None and rank <= 3),
            "mrr": 1 / rank if rank else 0, "first_relevant_rank": rank}


def calibrate():
    cases = [(["a", "b", "c"], {"a"}, (1, 1, 1)),
             (["a", "b", "c"], {"c"}, (0, 1, 1/3)),
             (["a", "b", "c"], {"d"}, (0, 0, 0))]
    records = []
    for ranked, relevant, expected in cases:
        observed = metrics(ranked, relevant)
        actual = tuple(observed[k] for k in ["hit1", "hit3", "mrr"])
        assert actual == expected
        records.append({"ranked": ranked, "relevant": sorted(relevant), "expected": expected, "observed": actual})
    scores = bm25("quasar", index(["quasar telescope", "banana orchard"]))
    assert scores[0] > scores[1] == 0
    assert tokens("検索精度") == ["検索", "索精", "精度"]
    return {"ranking_cases": records, "retriever_scores": scores, "passed": True}


def snapshot():
    corpus = []
    excluded_dirs = {"他のプロジェクトー無視", "temp_asr", "Claude Code", "Gemini Code", ".claude", "前桥teams"}
    for p in sorted(BLOG.rglob("*.md")):
        rel = p.relative_to(BLOG)
        if any(part in {"_pipeline", ".git", "node_modules"} for part in rel.parts) or rel.parts[0] in excluded_dirs:
            continue
        name = p.name.casefold()
        if len(rel.parts) < 2 or name in {"agents.md", "claude.md", "readme.md", "project.md", "outline.md", "大纲.md", "数据验证报告.md", "zenn需求.md"}:
            continue
        if any(x in name for x in ["linkedin", "linkenin", "teams", "信息.md"]):
            continue
        if len(rel.parts) > 2:
            continue
        # This file is an HTML-comment outline, identified by the independent
        # question author before ranking. Keep the complete blog_article.md.
        if rel.as_posix() in {"prompt注入，LLM安全/article.md", "Grok4/Blog-Grok4.md", "Grok4/模型对比_整理版.md"}:
            continue
        text = p.read_text(encoding="utf-8-sig")
        if not text.strip():
            continue
        headings = " ".join(re.findall(r"^#{1,2}\s+(.+)$", text, flags=re.M))
        corpus.append({"path": rel.as_posix(), "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                       "text": text, "metadata": rel.as_posix() + " " + headings})
    return corpus


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--queries", type=Path, default=ROOT / "queries.json")
    parser.add_argument("--corpus", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    corpus = json.loads(args.corpus.read_text(encoding="utf-8")) if args.corpus else snapshot()
    queries = json.loads(args.queries.read_text(encoding="utf-8"))
    write(args.output / "calibration.json", calibrate())
    write(args.output / "corpus.json", corpus)
    write(args.output / "queries.json", queries)
    paths = [d["path"] for d in corpus]
    for q in queries:
        assert q["relevant_paths"] and set(q["relevant_paths"]) <= set(paths), q
    body = index([d["text"] for d in corpus])
    meta = index([d["metadata"] for d in corpus])
    rows = []
    for query in queries:
        body_scores = bm25(query["query"], body)
        meta_scores = bm25(query["query"], meta)
        result = {"id": query["id"], "query": query["query"], "kind": query["kind"],
                  "relevant_paths": query["relevant_paths"]}
        for condition, scores in [("body", body_scores), ("body_metadata", [b+2*m for b,m in zip(body_scores, meta_scores)])]:
            order = sorted(range(len(paths)), key=lambda i: (-scores[i], paths[i]))
            ranking = [{"path": paths[i], "score": scores[i]} for i in order]
            result[condition] = {**metrics([r["path"] for r in ranking], set(query["relevant_paths"])), "ranking": ranking}
        rows.append(result)
    summary = {c: {k: sum(r[c][k] for r in rows) / len(rows) for k in ["hit1", "hit3", "mrr"]}
               for c in ["body", "body_metadata"]}
    write(args.output / "result.json", {"documents": len(corpus), "questions": len(queries),
                                      "metadata_weight": 2, "summary": summary, "rows": rows})
    print(json.dumps({"documents": len(corpus), "questions": len(queries), "summary": summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
