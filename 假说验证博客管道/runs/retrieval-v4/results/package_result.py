"""Package the frozen retrieval study; preserve raw execution and experiment files."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PIPELINE = HERE.parents[1]
RUN = PIPELINE / "runs" / "retrieval-v4"
RUN_ID = "retrieval-v4"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ref(path):
    return {"path": path, "sha256": sha(RUN / path)}


def copy_evidence(source, target):
    destination = RUN / target
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def main():
    raw_paths = list((RUN / "results" / "experiment").iterdir()) + [RUN / "results" / n for n in ("execution.json", "stdout.log", "stderr.log")]
    raw_hashes = {str(p): sha(p) for p in raw_paths}
    result = read(RUN / "results/experiment/result.json")
    execution = read(RUN / "results/execution.json")
    calibration = read(RUN / "results/experiment/calibration.json")
    assert execution["run_id"] == RUN_ID and execution["exit_code"] == 0
    sources = {
        "design": (HERE / "DESIGN.md", "results/design.md"),
        "algorithm": (HERE / "run_experiment.py", "results/run_experiment.py"),
        "package": (Path(__file__), "results/package_result.py"),
        "query_notes": (HERE / "queries_notes.md", "results/query_notes.md"),
        "initial": (PIPELINE / "runs/retrieval/results/experiment/result.json", "results/history/initial_result.json"),
        "initial_review": (PIPELINE / "audit/retrieval_reproduction/REVIEW.md", "results/history/initial_review.md"),
        "reproduction": (PIPELINE / "audit/retrieval_reproduction/final/verification.json", "results/reproduction/verification.json"),
        "reproduction_review": (PIPELINE / "audit/retrieval_reproduction/final/REVIEW.md", "results/reproduction/REVIEW.md"),
        "reproduction_process": (PIPELINE / "audit/retrieval_reproduction/final/process.json", "results/reproduction/process.json"),
        "reproduction_stdout": (PIPELINE / "audit/retrieval_reproduction/final/stdout.log", "results/reproduction/stdout.log"),
        "reproduction_stderr": (PIPELINE / "audit/retrieval_reproduction/final/stderr.log", "results/reproduction/stderr.log"),
        "zenn": (PIPELINE / "research/zenn/FINDINGS.md", "results/content_research/FINDINGS.md"),
        "zenn_statistics": (PIPELINE / "research/zenn/statistics.json", "results/content_research/statistics.json"),
    }
    for source, target in sources.values():
        copy_evidence(source, target)
    initial = read(RUN / sources["initial"][1])
    verification = read(RUN / sources["reproduction"][1])
    assert all(v["byte_equal"] for v in verification["artifact_comparison"].values())

    metrics = {}

    def metric(key, value, unit, path, locator, derivation):
        metrics[key] = {"value": value, "unit": unit, "provenance": {
            **ref(path), "locator": locator, "derivation": derivation}}

    final_path = "results/experiment/result.json"
    metric("documents", result["documents"], "documents", final_path, "/documents", "frozen corpus document count")
    metric("questions", len(result["rows"]), "questions", final_path, "/rows", "length of all question rows")
    metric("weight", result["metadata_weight"], "weight", final_path, "/metadata_weight", "preselected field score multiplier")
    for condition in ["body", "body_metadata"]:
        for kind in [None, "topic", "detail"]:
            rows = [r for r in result["rows"] if kind is None or r["kind"].startswith(kind + "_")]
            prefix = condition if kind is None else condition + "_" + kind
            for target in ["hit1", "hit3"]:
                metric(prefix + "_" + target, sum(r[condition][target] for r in rows), "questions", final_path,
                       "/rows", f"sum {condition}.{target}; kind={kind or 'all'}; include every row")
            if kind is None:
                metric(prefix + "_mrr", sum(r[condition]["mrr"] for r in rows) / len(rows), "ratio", final_path,
                       "/rows", f"mean {condition}.mrr across all questions")
            else:
                metric(kind + "_questions", len(rows), "questions", final_path, "/rows", f"count kind prefix {kind}")
    for question in ["q26", "q12", "q08", "q24"]:
        row = next(r for r in result["rows"] if r["id"] == question)
        for condition in ["body", "body_metadata"]:
            metric(question + "_" + condition + "_rank", row[condition]["first_relevant_rank"], "rank", final_path,
                   "/rows", f"row id={question}; {condition}.first_relevant_rank")
    for condition in ["body", "body_metadata"]:
        metric("initial_" + condition + "_hit3", sum(r[condition]["hit3"] for r in initial["rows"]), "questions",
               sources["initial"][1], "/rows", f"historical run retrieval, sum {condition}.hit3; not the final corpus")
    metric("exit_code", execution["exit_code"], "exit_code", "results/execution.json", "/exit_code", "captured process result")
    metric("equal_artifacts", sum(v["byte_equal"] for v in verification["artifact_comparison"].values()), "files",
           sources["reproduction"][1], "/artifact_comparison", "count byte_equal true across independently rerun artifacts")
    write(RUN / "results/metrics.json", {"run_id": RUN_ID, "metrics": metrics,
          "source": ref(final_path), "generator": ref("results/package_result.py"),
          "scope": "Named final-study and explicitly historical metrics; no same-value lookup"})

    ruler_cases = []
    for i, case in enumerate(calibration["ranking_cases"]):
        assert case["observed"] == case["expected"]
        ruler_cases.append({"label": "bad" if not any(case["expected"]) else "good",
                            "expected": case["expected"], "observed": case["observed"],
                            "source_case_index": i, "evidence": ref("results/experiment/calibration.json")})
    assert calibration["passed"] and calibration["retriever_scores"][0] > calibration["retriever_scores"][1] == 0
    write(RUN / "results/ruler_check.json", {"run_id": RUN_ID, "ruler_id": "frozen-document-ranking-v1",
          "status": "passed", "alignment": "前三命中直接衡量这批问题能否在前三结果找到已标相关文档；不衡量答案生成、读者时间或生产泛化。",
          "cases": ruler_cases, "retriever_control": {"observed": calibration["retriever_scores"],
          "evidence": ref("results/experiment/calibration.json")},
          "limits": "Calibration covers ranking arithmetic and elementary token matching; human relevance completeness remains a reviewed assumption."})

    gate_path = PIPELINE / "skills/evidence-check/scripts/gate.py"
    spec = importlib.util.spec_from_file_location("retrieval_evidence_gate", gate_path)
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    documents = []

    class Document:
        def __init__(self, filename):
            self.filename = filename
            self.parts = []
            self.claims = []
            self.bindings = []

        def add(self, template, level="read", evidence=("design",), scope="本次冻结语料、人工题集及保存的研究记录"):
            offset = sum(len(p) for p in self.parts)
            text = ""
            last = 0
            pending = []
            for match in re.finditer(r"\{\{([a-z0-9_]+)\}\}", template):
                text += template[last:match.start()]
                key = match.group(1)
                value = str(metrics[key]["value"])
                pending.append((offset + len(text), key))
                text += value
                last = match.end()
            text += template[last:]
            cid = f"c{len(self.claims)+1}"
            paths = [sources[k][1] if k in sources else k for k in evidence]
            if pending:
                paths += ["results/metrics.json"]
            self.claims.append({"id": cid, "text": text, "level": level, "scope": scope,
                                "evidence": [ref(p) for p in dict.fromkeys(paths)]})
            for start, key in pending:
                self.bindings.append({"start": start, "key": key, "claim_id": cid})
            self.parts.append(text + "\n\n")

        def save(self):
            text = "".join(self.parts)
            path = RUN / self.filename
            path.write_text(text, encoding="utf-8")
            by_start = {b["start"]: b for b in self.bindings}
            numbers = []
            for item in gate.scan(text):
                base = {"index": item["index"], "token": item["token"]}
                if item["start"] in by_start:
                    binding = by_start[item["start"]]
                    key = binding["key"]
                    numbers.append({**base, "kind": "measurement", "claim_id": binding["claim_id"],
                                    "unit": metrics[key]["unit"], "ref": {**ref("results/metrics.json"),
                                    "run_id": RUN_ID, "pointer": "/metrics/" + key, "unit": metrics[key]["unit"]}})
                else:
                    # Only predeclared format/name literals qualify; an unbound measurement is an error.
                    containing = next((label for label in ["BM25", "H1", "H2", "retrieval-v4", "--workers=1"]
                                       if any(m.start() <= item["start"] and item["end"] <= m.end()
                                              for m in re.finditer(re.escape(label), text))), None)
                    if containing is None:
                        raise ValueError(f"Unbound numeric occurrence in {self.filename}: {item}")
                    numbers.append({**base, "kind": "identifier", "reason": "固定名称或文档版本中的数字：" + containing})
            claims_name = "claims.json" if self.filename == "article.md" else self.filename.removesuffix(".md") + ".claims.json"
            write(RUN / claims_name, {"run_id": RUN_ID, "draft_sha256": sha(path), "claims": self.claims, "numbers": numbers})
            documents.append({"draft": {"path": self.filename, "sha256": sha(path)}, "claims": claims_name})

    article = Document("article.md")
    article.add("# 記事検索で見出しを重視したら、順位は上がっても見つかる質問は増えなかった", "inferred", (final_path,))
    article.add("社内ブログが増えると、書く前に『この話は前にも調べたはず』という資料探しが発生します。記事の見出しを検索で重視すれば、必要な情報を見つけやすくなる。そう考えるのは自然ですが、今回の検証では、順位が上がることと、答えのある記事を見つけられる質問が増えることは別でした。", "inferred", ("design", final_path))
    article.add("手元の技術記事 {{documents}} 本と、別の AI エージェントが本文を読んで作った {{questions}} 問で比べました。先頭で関連記事が見つかる質問は {{body_hit1}} 問から {{body_metadata_hit1}} 問へ増えました。一方、主な判定基準にしていた『上位三件に入るか』は、どちらも {{body_hit3}} 問でした。", "measured", (final_path, "query_notes", "reproduction"))
    article.add("この違いは、検索を少し直したときに『よくなった』をどう判断するかに関わります。先に結果だけ伝えると、今回の変更には並び順を改善する手応えがありました。ただし、当初の『上位三件で見つかる質問が増える』という仮説は支持されていません。", "inferred", (final_path, "design"))
    article.add("## 比べたのは単語の一致を使う小さな検索です")
    article.add("使ったのは、質問と記事に現れる語の一致から点数をつける簡略な BM25 検索です。英数字は単語として扱い、日本語や中国語の連続文字は主に隣り合う文字の組へ分けます。埋め込み、クエリ翻訳、モデルによる再ランキングは使っていません。Agent が何度も検索し直す仕組みの評価でもありません。", "read", ("algorithm",))
    article.add("比較した条件は、本文だけのスコアと、そこへパス・H1/H2 見出しのスコアを {{weight}} 倍して加える方式です。元の本文には見出しも残っています。比較相手からタイトルを削って弱くしたのではなく、同じ文字列を別のフィールドとして強調する変更です。", "read", ("algorithm", "design"))
    article.add("質問は、技術の全体像を探すものと本文の細部を探すものを、それぞれ {{topic_questions}} 問用意しました。日本語・中国語・英語を含みます。作問担当には検索の実装や順位を見せず、どの記事で答えられるかと、根拠の一節を先に記録しました。とはいえ、実際の利用ログから無作為に選んだ質問ではありません。", "read", ("query_notes", "results/experiment/queries.json"))
    article.add("評価するのは回答文のうまさではなく、関連記事の位置です。先頭にあるか、上位三件にあるかを数えます。複数の記事が回答に使える質問では、どれかが見つかれば命中としました。順位から数字を出す部分は、正解が先頭にある場合、三番目にある場合、存在しない場合の既知データで確かめています。", "read", ("algorithm", "results/experiment/calibration.json"))
    article.add("## 並び順が変わっても、上位で見つかる質問は増えませんでした", "inferred", (final_path,))
    article.add("| 判定 | 本文のみ | 見出し・パスを加重 |\n|---|---:|---:|\n| 先頭で関連記事が見つかる | {{body_hit1}} / {{questions}} 問 | {{body_metadata_hit1}} / {{questions}} 問 |\n| 上位三件で関連記事が見つかる | {{body_hit3}} / {{questions}} 問 | {{body_metadata_hit3}} / {{questions}} 問 |", "measured", (final_path, "reproduction"))
    article.add("具体例は、無害に見える断片を後で結合する『Split Injection』を英語で尋ねた質問です。対応する日本語の記事は、本文だけでも {{q26_body_rank}} 位にあり、加重すると {{q26_body_metadata_rank}} 位になりました。読む候補を上から選ぶなら便利そうです。ただ、もともと上位三件には入っていたので、『見つからなかった資料を新しく拾えた』とは数えられません。", "measured", (final_path, "results/experiment/corpus.json"))
    article.add("逆に、Claude Code のカスタムサブエージェントを作るコマンドを英語で尋ねた質問は、{{q12_body_rank}} 位から {{q12_body_metadata_rank}} 位まで上がりました。それでも上位三件には届きません。点数や順位が動いたことだけで、利用者の探し物が解決したとは言えない例です。", "measured", (final_path, "results/experiment/queries.json"))
    article.add("題材別に見ても、テーマを探す問題の先頭命中は {{body_topic_hit1}} 問から {{body_metadata_topic_hit1}} 問、細部を探す問題は {{body_detail_hit1}} 問から {{body_metadata_detail_hit1}} 問へ増えています。ただし各群の上位三件命中は変わりませんでした。これを『見出しは細部検索にも常に効く』と一般化するには、問題の数も種類も足りません。", "measured", (final_path, "reproduction"))
    article.add("## 途中で、測る対象の間違いが見つかりました", "read", ("initial_review",))
    article.add("最初の実行には、完成した本文に混じって、コメント内の執筆指示を中心とする構成案が入っていました。ファイル名が article.md だったため、名前だけの除外では取り除けていなかったものです。独立した再実行と原文の確認で見つかり、空ファイルや比較用の参考メモも含めて、事前に決めた『技術記事の本文』という範囲へ整理しました。", "read", ("design", "initial_review", "reproduction_review"))
    article.add("整理前の上位三件命中は、本文のみ {{initial_body_hit3}} 問、加重あり {{initial_body_metadata_hit3}} 問でした。最終版では本文のみも {{body_hit3}} 問になり、主指標の差が消えました。質問や重みは変更せず、初回の結果も保存しています。都合の悪い問題を落とした再評価ではありません。", "read", ("initial", final_path, "design", "query_notes"))
    article.add("この差を、特定の構成案だけの影響と断定はできません。候補が減ることに加え、BM25 では語がどれくらい珍しいかを決める文書集合全体の統計も変わります。ここで確かめられたのは、入力を何と定義するかが結果に効いた、というところまでです。", "inferred", ("algorithm", "initial", final_path, "design"))
    article.add("最終版は固定した記事の写しと同じ質問を使い、新しいディレクトリで再実行しました。結果・記事・質問・評価計算の確認記録は、作者側の保存物とバイト単位で一致しています。計算が再現できることは確認しましたが、それだけで質問の選び方まで正しいと証明されたわけではありません。", "measured", ("reproduction", "reproduction_process"))
    article.add("## 見出しの重みでは埋まらない穴もあります", "inferred", (final_path,))
    article.add("中国語で『言語サーバーとエディタの通信プロトコルは何か』と尋ねた問題には、日本語の LSP 記事に答えがありました。それでも上位には出ませんでした。日本語で『予約したという発言と、実際に予約された状態の違い』を尋ね、中国語の評価ガイドを探す問題も同様です。", "measured", (final_path, "results/experiment/queries.json", "results/experiment/corpus.json"))
    article.add("ここには、言い換えや言語の違いを単純な文字列一致だけで扱う限界がありそうです。タイトルを強調するだけでは、質問に使われた語と本文の語が離れている問題を解決できませんでした。翻訳や意味検索を加えるべきかは、別の比較で確かめる必要があります。今回の結果から RAG の要否や Agent 検索全体の優劣は判断できません。", "inferred", (final_path, "algorithm", "reproduction_review"))
    article.add("## 自分の検索で試すなら", "inferred", ("design",))
    article.add("まず、何を改善したいのかを分けておくと判断しやすくなります。候補の先頭へ関連記事を置きたいのか、今まで見つからなかった質問を救いたいのか。前者なら先頭命中、後者なら実際に見てもらう範囲での命中を見る必要があります。今回、利用者が探す時間そのものは測っていません。", "inferred", ("design", final_path))
    article.add("そして、本文・構成案・メモのどれを検索対象にするかを先に決め、質問と根拠を残してから比べます。結果が動いたら、代表的な質問で元の文章を開き、本当に欲しかった情報があるかを確かめます。この小さな確認が、数字だけを見た結論の取り違えを防いでくれます。", "inferred", ("initial_review", "reproduction_review"))
    article.add("今回の見出し加重は、この問題集では関連記事を前へ出す助けになりました。ただし、上位三件で関連記事を見つけられる質問は増えていません。『検索がよくなった』を一つの数字で済ませず、どの困りごとが変わったのかまで見る。そのための小さな検証でした。", "inferred", (final_path, "design"))
    article.save()

    report = Document("REPORT.md")
    report.add("# 检索研究交付报告", "read", (final_path,))
    report.add("课题：博客积累后，选题和写作需要找回以往资料。检验给正文 BM25 额外加上路径及 H1/H2 章节标题分数，能否增加前三位找到正确文档的问题数量。", "read", ("design", "algorithm"))
    report.add("结论：最终 {{documents}} 篇正文、{{questions}} 题中，前三命中都是 {{body_hit3}} 题。预先提出的提升假说不获支持；首位命中 {{body_hit1}} → {{body_metadata_hit1}} 题是次指标上的改善，不能替换原主指标。", "measured", (final_path, "reproduction", "design"))
    report.add("为什么这么做：两组用同一正文、分词、参数、题集和排序规则，候选只增加字段加权；正文基线原本就含标题。题目由独立代理读文章后编制，未看算法或排名。这样减少按结果挑题和故意削弱对照的风险，但便利样本仍不代表真实流量。", "read", ("design", "query_notes", "reproduction_review"))
    report.add("| 读者关心的问题 | 本次观察 |\n|---|---|\n| 找到更多原来找不到的资料了吗 | 前三命中 {{body_hit3}} / {{questions}} → {{body_metadata_hit3}} / {{questions}}，没有增加 |\n| 相关资料是否排到首位 | 首位命中 {{body_hit1}} / {{questions}} → {{body_metadata_hit1}} / {{questions}}，有改善 |\n| 主题和细节是否相同 | 主题首位 {{body_topic_hit1}} → {{body_metadata_topic_hit1}}；细节首位 {{body_detail_hit1}} → {{body_metadata_detail_hit1}} |", "measured", (final_path, "reproduction"))
    report.add("独立复现：{{equal_artifacts}} 个产物与作者记录字节完全一致。原始执行退出码 {{exit_code}}，有真实标准输出和错误输出；校准覆盖已知首位、第三位和缺失排序。机械溯源与可重复计算不等于方法能推广到其他数据。", "measured", ("reproduction", "results/execution.json", "results/experiment/calibration.json"))
    report.add("重要修正：初版混入提纲和空文件，另有实验回答笔记与价格资料表不符合正文定义。纠正输入后，正文基线的前三命中从 {{initial_body_hit3}} 变为 {{body_hit3}}，原先的主指标差异消失。原版本保留，未改冻结问题或按得分调重。", "read", ("design", "initial", final_path, "initial_review"))
    report.add("预期效果：可把该策略作为本地资料检索的候选排序改动；不能承诺节省多少时间、改善所有跨语言查询或增加发布点赞。若进入生产，应另用实际查询和读者筛选时间验证。", "inferred", (final_path, "reproduction_review"))
    report.add("参考了哪里：内容表达参考本轮 Zenn 样本研究，采用具体问题、真实对照和读者收益，不套数字标题公式。研究与编辑判断都保留在 results/content_research 与 editorial.md；本轮没有发布后的互动数据。", "read", ("zenn",))
    report.add("没破坏的逻辑：现有博客、检索算法和原始实验记录未由本交付脚本改写；只派生指标、证据台账及草稿。仍需人工决定发布身份、公司公开范围和最终渠道。技术结论的独立审查已完成。", "read", ("package", "reproduction_review"))
    report.save()

    hypothesis = Document("hypothesis.md")
    hypothesis.add("# 假说卡")
    hypothesis.add("原问题：过去的技术博客能否更容易被检索找回？具体主张是在固定题集上，正文 BM25 加路径与 H1/H2 章节标题分数，比正文基线有更多前三命中。", "read", ("design",))
    hypothesis.add("目标读者是维护内部技术知识库的工程师；价值在于区分排序改善和新增找回，避免把不同收益混为一谈。题目来自本地真实文章，并非为热门标题预设成功。", "inferred", ("design", final_path))
    hypothesis.add("证伪条件：候选前三命中不高于基线，就不支持这批数据上的提升假说。支持要求该数增加；持平或下降记录不支持；校准失效、执行失败或输入不完整则证据不足。", "read", ("design",))
    hypothesis.add("资源：真实检索计算仅用本地 CPU；本轮用户允许充分资源，但计划为有限实验和独立复现，不无限调参直到变好。没有访问额外付费检索服务。编题、审查和写作使用 AI，完整会话账单未在本 run 单独获得，不报告为零成本。", "read", ("design", "algorithm", "results/execution.json"))
    hypothesis.add("最终判断：主假说不支持；首位排名改善是次指标发现，可用于提出后续读者筛选成本假说。", "inferred", (final_path, "design"))
    hypothesis.save()

    plan = Document("experiment-plan.md")
    plan.add("# 实验方案与冻结记录")
    plan.add("本文件由保存的设计整理，不冒充实验前新写的预注册。原始设计及修订记录在 results/design.md；最终输入和输出在 results/experiment。", "read", ("design",))
    plan.add("实验单位为问题；共 {{questions}} 题，主题和细节各 {{topic_questions}} 题。同一问题在相同 {{documents}} 篇正文中分别检索。正确文档可多选，任一命中计成功。", "read", (final_path, "results/experiment/queries.json"))
    plan.add("干预为正文分数加 {{weight}} 倍路径及 H1/H2 标题分数。两组保留同一完整正文和参数；不根据题目调权重。主要指标是前三命中，首位命中与 MRR 是辅助观察。", "read", ("design", "algorithm", final_path))
    plan.add("尺子先以已知首位、第三位、缺失排序核对命中和倒数排名，再检查明确命中词的小语料对照。原校准结果在 results/experiment/calibration.json，派生索引在 results/ruler_check.json。", "read", ("results/experiment/calibration.json", "algorithm"))
    plan.add("算法固定且确定，不把机械重复当作更多独立样本。独立复现使用同一输入快照，在新目录重跑；逐字段及字节比较结果。人为编题与词面跨语言能力是主要边界。", "read", ("design", "reproduction", "query_notes"))
    plan.add("输入审查发现提纲和空文件时，按原范围纠正并保留旧版本；不改题集。达到明确的运行完成与复现检查条件后停止，本轮不追加权重搜索或生产查询测试。", "read", ("design", "reproduction_review"))
    plan.save()

    execution_doc = Document("execution.md")
    execution_doc.add("# 执行摘要", "read", ("results/execution.json",))
    execution_doc.add("主实验由真实 capture 运行，退出码为 {{exit_code}}。实际命令、开始结束时间以及 stdout/stderr 散列在 results/execution.json；该记录未被包装过程重写。", "measured", ("results/execution.json", "package"))
    execution_doc.add("最终原始产物包括固定正文、固定题目、排序校准和逐题完整排名。派生 metrics.json 逐项记录输入文件、定位方式和聚合公式；历史数字明确命名为 initial，不能当成最终数字。", "read", (final_path, "package"))
    execution_doc.add("复现命令（从 run 目录执行，输出目录必须是新目录）：\n\n```powershell\npython ../../experiments/retrieval/run_experiment.py replay --queries results/experiment/queries.json --corpus results/experiment/corpus.json\n```", "read", ("algorithm", "reproduction_process"))
    execution_doc.add("打包命令：\n\n```powershell\npython ../../experiments/retrieval/package_result.py\n```\n\n该命令只刷新派生交付物，最后运行严格证据核对；不重跑检索、不覆盖真实执行记录。", "read", ("package",))
    execution_doc.add("没有生成式模型参与检索评分或回答生成。本地实验消费与 AI 编题、审查和写作应分开理解；后者缺少单独结算费用，本报告没有把未知费用填成零。", "read", ("algorithm", "design"))
    execution_doc.save()

    review_doc = Document("review.md")
    review_doc.add("# 独立审查交接", "read", ("reproduction_review",))
    review_doc.add("审查者先在新目录实跑，独立从完整排名重算结果并保存初步判断，再对作者结果；最终 {{equal_artifacts}} 个产物字节一致。原始复现日志、检查记录与审查报告复制在 results/reproduction。", "read", ("reproduction", "reproduction_process", "reproduction_review"))
    review_doc.add("审查发现并促成修正：初版包含提纲与空文件，正文范围还需排除测试回答笔记和价格资料表；浮点累加顺序不固定导致末位不同。最终版已按输入定义和确定排序修正，题目保持不变。", "read", ("design", "initial_review", "reproduction_review"))
    review_doc.add("最终主指标均为 {{body_hit3}} / {{questions}}；不支持前三命中改善。首位 {{body_hit1}} → {{body_metadata_hit1}} / {{questions}} 可以报告为本题集次指标发现。未发现故意削弱基线或必须修订的真值，但相关集合不保证穷尽。", "read", (final_path, "reproduction_review"))
    review_doc.add("允许形成日语草稿，必须写清简单词面检索、人工便利样本、真实阅读耗时未测及跨语言漏检。机械 gate 只负责可追溯；发布授权、公开范围和作者身份仍需对应判断。", "inferred", ("reproduction_review", "design"))
    review_doc.save()

    editorial = Document("editorial.md")
    editorial.add("# 编辑判断与传播目标", "inferred", ("zenn", final_path))
    editorial.add("目标读者：维护内部博客、RAG 资料库或本地文档搜索的工程师。读者收益是知道怎样区分排名改善与新增找回，以及为什么先审输入再看指标。点赞与注目度是重要目标，但本轮尚无发布后验证。", "inferred", ("zenn", final_path))
    editorial.add("候选标题：\n\n- 記事検索で見出しを重視したら、順位は上がっても見つかる質問は増えなかった\n- 見出しを重くすると検索はよくなる？手元の記事で確かめた\n- 検索の改善を測る前に、本文と下書きを分けておく", "inferred", ("zenn", final_path, "initial_review"))
    editorial.add("推荐第一个：技术对象和实际结果都明确，直接兑现排序与覆盖的区别。第二个突出读者问题，但缺少具体发现；第三个适合内部经验分享，容易掩盖排序实验的主体。候选是编辑判断，不是测得点击率更高的标题。", "inferred", ("zenn", final_path))
    editorial.add("开头采用先给实际结果，再提出『排名变好是否等于更容易找到』。备选开头可从初版误纳提纲进入，但会增加戏剧性而弱化主问题，本稿不采用。", "inferred", ("zenn", "initial_review", final_path))
    editorial.add("参考本轮 Zenn 内容研究：问题式标题有探索性信号，数字或『検証』标签没有通用优势；具体产物有助于解释，但代码和表格不设数量配额。这些是观察性相关，作者与曝光构成可能改变结果。研究文件快照位于 results/content_research。", "read", ("zenn", "zenn_statistics"))
    editorial.add("本文以真实结果表和 Split Injection 排名例子解释，不增加装饰图片或虚构亲历故事。篇幅服从把问题讲清，保留输入修订和跨语言失败；不为了注目度把次指标写成主要成功。", "inferred", ("zenn", final_path, "reproduction_review"))
    editorial.add("发布前需要确认署名、可公开材料和复现包的共享位置。当前仅为草稿，不创建假链接；若今后发布，应保存标题正文版本、分发渠道和固定时点的互动量，曝光缺失时不推断点击率。", "inferred", ("zenn",))
    editorial.save()

    manifest = read(RUN / "run.json")
    manifest.update({"hypothesis": {"claim": "Adding fixed heading/path weighting increases hit@3 on the frozen article questions",
                     "falsification": "Candidate hit@3 <= body hit@3 does not support the improvement hypothesis"},
                     "outcome": "refuted", "outcome_scope": "Preselected hit@3 improvement on this fixed sample only; secondary rank improvement remains valid",
                     "ruler_id": "frozen-document-ranking-v1", "ruler": ref("results/ruler_check.json"),
                     "execution": ref("results/execution.json"), "documents": documents,
                     "budget": {"status": "within", "scope": "Authorized finite local experiment and independent reproduction; AI authoring billing not separately known"}})
    write(RUN / "run.json", manifest)
    command = [sys.executable, str(gate_path), "check", str(RUN), "--strict", "--output", str(RUN / "gate.json")]
    process = subprocess.run(command, capture_output=True)
    (RUN / "results/package_gate.stdout.log").write_bytes(process.stdout)
    (RUN / "results/package_gate.stderr.log").write_bytes(process.stderr)
    write(RUN / "results/package_gate_process.json", {"command": command, "exit_code": process.returncode})
    assert raw_hashes == {str(p): sha(p) for p in raw_paths}, "Raw experiment or execution evidence changed"
    print(json.dumps({"documents": len(documents), "article_characters": len((RUN / "article.md").read_text(encoding="utf-8")),
                      "gate_exit_code": process.returncode, "gate_status": read(RUN / "gate.json")["status"],
                      "raw_evidence_preserved": True}, ensure_ascii=False))
    if process.returncode:
        print(process.stdout.decode("utf-8", errors="replace"))
        raise SystemExit(process.returncode)


if __name__ == "__main__":
    main()
