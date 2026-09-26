# 数据接口

执行与修复策略只有一份权威配置：[policy.json](../../../policy.json)。本文件仅定义输入、输出和历史数据兼容方式。Python 标准库即可运行。

```sh
python skills/evidence-check/scripts/gate.py capture runs/example -- python experiment.py
python skills/evidence-check/scripts/gate.py scan runs/example/article.md --candidates
python skills/evidence-check/scripts/gate.py check runs/example --strict --output runs/example/gate.json
```

## 输出

```json
{
  "run_id": "example",
  "status": "warnings",
  "issues": [{
    "id": "hash_drift:stable-location-hash",
    "code": "hash_drift",
    "category": "record_note",
    "severity": "warning",
    "location": {"document": "article.md", "claim_id": "c1", "ref": {"path": "results/metrics.json", "pointer": "/metrics/correct"}},
    "detail": "Source file hash changed; current field still matches"
  }],
  "ruler": {"path": "results/ruler_check.json", "recorded_status": "needs_review"},
  "checked_measurements": 1,
  "policy_sha256": "POLICY_FILE_SHA256"
}
```

`status`：blocked 表示存在由 policy 分类为 fatal 的问题；incomplete 表示材料缺失而无法完成核对；warnings 表示已核对材料中仍有提示；traceable 仅表示已登记数字的机械核对无问题，不代表研究正确。

每条 issue 的 severity 由 policy 决定。`id` 根据 code、document、claim_id、来源 path/pointer 生成，不含数值、散列或 detail。调用方用此 ID 记录同一问题，不靠措辞变化开启新一轮修复。gate 不执行自动返工。

`check --strict` 仅在 blocked 时退出 2；其余状态退出 0。普通 check 总是输出报告并退出 0。capture 返回真实进程 exit_code；进程本身失败时 CLI 退出 1，与授权拒绝的退出 2 分开。启动前无法读取必要配置时返回 incomplete，不启动进程。

## run.json

```json
{
  "run_id": "example",
  "outcome": "refuted",
  "execution_claim": "succeeded",
  "execution": {"path": "results/execution.json", "sha256": "FILE_SHA256"},
  "ruler": {"path": "results/ruler_check.json", "sha256": "FILE_SHA256"},
  "budget": {"status": "within"},
  "documents": [{"draft": {"path": "article.md", "sha256": "FILE_SHA256"}, "claims": "claims.json"}]
}
```

capture 的最小启动记录只需 run_id，已有预算状态则一并携带；capture 保存命令、起止时间、真实退出码和 stdout/stderr。命令参数不要包含密钥。已存在的执行证据不会覆盖。

`execution_claim` 描述报告如何陈述执行事实：succeeded / failed / not_run。诚实报告失败时写 failed，研究假说的 refuted 与执行失败不同。历史记录没有 execution_claim 时，从已登记 measured 断言识别是否正在声称取得实测结果；这只是机械提示，语义仍由审查者确认。

hypothesis、ruler_id、budget 及其他研究材料可继续保留，缺少模板字段不等于数字不真实。JSON 无法读取或尚未提供文档时输出 incomplete。

## 尺子记录

```json
{
  "status": "needs_review",
  "alignment": "希望计数对应任务正确性，是否足够由审查者判断",
  "observations": "已知反例未被当前指标分开，尚未形成有效判断",
  "evidence": [{"path": "results/calibration.log", "sha256": "FILE_SHA256"}]
}
```

ruler 可以引用 JSON 或 Markdown。gate 只记录现有 status（Markdown 为 see_document），不要求 good/bad 字段，不用字段存在或标签匹配裁定科学有效性。旧 cases、expected、observed 结构仍可读取。

## 来源和登记数字

来源放在当前 run 的 results 下：

```json
{
  "run_id": "example",
  "metrics": {
    "correct": {"value": 6, "unit": "cases"},
    "total": {"value": 10, "unit": "cases"}
  }
}
```

文章为 `v1.2 を使用し、正解は 6 件でした。` 时，scan 仍保留版本数字的旧 index，实测数字使用它实际的 index：

```json
{
  "run_id": "example",
  "draft_sha256": "FILE_SHA256",
  "claims": [{"id": "c1", "text": "正解は 6 件でした。", "level": "measured", "scope": "本批任务"}],
  "numbers": [{
    "index": 1,
    "token": "6",
    "kind": "measurement",
    "claim_id": "c1",
    "unit": "cases",
    "ref": {"path": "results/metrics.json", "sha256": "FILE_SHA256", "run_id": "example", "pointer": "/metrics/correct", "unit": "cases"}
  }]
}
```

numbers 只需登记实验测量及派生值；版本、URL、BM25、H1 等标识符和结构编号自动带 ignore_reason。旧 date/version/identifier/structure/code 登记不要求 reason；自动识别出的元数据直接跳过，但手工分类不能隐藏未被自动识别的数字，这些数字仍提示语义核对，不升级为致命问题。scan 默认输出所有 token，保证旧 index 不变；--candidates 隐去自动识别的元数据，保留剩余 token 的原 index。

未登记且无法机械判断性质的数字只提示语义审查。四种 level 仍可用于辅助写作：measured / read / inferred / speculative；不要求把每条非实测句子都做成台账。

来源散列是原始字节的 SHA256。格式变动可能改变散列，gate 会继续读取当前值、单位和 run_id，而不是仅凭散列漂移判定数字错误。来源缺失或无法解析会如实记录无法核验。JSON Pointer 指向 value/unit 对象，数组索引采用非负整数且不能有多余前导零。

派生数字将 ref 换为 `calculation: {"op": "percent", "inputs": [正确数引用, 总数引用]}`。可用 sum、mean、difference(a-b)、ratio(a/b)、percent(a/b*100)、relative_change_percent((candidate-baseline)/baseline*100)。输入单位一致，结果单位分别为原单位、ratio 或 percent。复杂统计由实验代码计算并保留原始输入，不在 gate 内执行通用表达式。可选 decimals 使用 ROUND_HALF_UP。

外部来源可附 `origin: {"kind": "external", "url": "实际地址", "retrieved_at": "实际时间", "snapshot": {"path": "results/source.html", "sha256": "FILE_SHA256"}}`，并保留来源口径。hash 不是防伪签名，文件内容与散列一起修改仍需独立语义审查。

扫描边界仍包括 `1_000`、窄空格千分位、全角逗号、汉字量级及 Unicode 指数减号。此类表达可能拆成多个 token；不要把自动分类或 traceable 当成全文数学意义已验证。需要报告实测数时，采用清晰半角数字格式并检查对应原始值即可。
