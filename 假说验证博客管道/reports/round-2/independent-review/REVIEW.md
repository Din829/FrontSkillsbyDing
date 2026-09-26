# 第二轮独立审查

最新结论：主代理修复后，原探针仅复测一次，18 项原有预期均符合。旧 identifier 误分类现在给出语义 warning，不再静默消失；线程异常分支已静态确认只在原 author_thread 为空时接纳失败记录的线程。后者未进行真实异常 CLI 复现，不能与机械测试一起称为动态通过。本审查不修改核心代码，也未调用模型。下文保留首测问题现场。

## 一次修复后复测

结果文件：`retest/results.json`、`retest/expectations.json`；完整新输入与源快照均在 `retest/`，首测记录未覆盖。复测入口 `retest_once.py` 直接载入原探针，仅将产物保存到新目录，没有改写场景或预期。

- gate SHA256：`4253f4dacbd56cd73adfd760fdec510a945528976e78c13593adb07f8043806f`。
- runner SHA256：`705a151f29a6a09fcf2e01bd0a5db91de3e0bb995edd4c5e2e4aa2bb103d353a`。
- 误标 identifier 的 99：现在 exit 0/status=warnings，明确 `unclassified_numbers`，detail 为 `Semantic review candidates: 1:99`。未将分类不确定升级为致命错误。
- 原有的实际错值/异 run 来源/伪成功阻断、换行与尺子警告、诚实失败报告、稳定问题 ID、跨进程返工封顶均保持预期。
- finish 对证据材料不足仍输出 incomplete，对审查待输入仍输出 review_pending。
- 线程修补静态条件为 `same_author and state['author_thread'] is None and process_file.exists()`。已有作者线程不会被这个异常分支覆盖，记录见 `retest/thread-static-review.json`。现有成功恢复原始凭据保留；本轮没有诱导 CLI 返回错误线程。

返工与复测次数：首测 1 次、修复后重放 1 次，没有第三轮或刷绿修改；本审查核心修改 0 次、模型调用 0 次、业务试跑 0 次。封顶测试在两套独立夹具各预留 1 次额度，各自后续两次调用均未新增额度；这是计数器测试，不是实际模型修复。18 项匹配是有限工具案例证据，不代表整体研究可靠率。

## 方法和版本

亲自阅读 policy、gate、pipeline、model_session、rework 与契约，没有借用作者测试。脚本 `probe.py` 从零建立明确标记的工具夹具，通过真实 Python 子进程运行 capture/scan/check。`component_worker.py` 在新进程调用真实 finish/claim_repair 函数；其状态是组件输入，不是模拟模型返回，更不是业务研究成果。

初次审查源代码与 hash 保存于 `reviewed-source/`、`versions.json`。gate 首测 hash 为 `38d35890b14a4dee707deba913ff4beceb5ee2415c36239c05cc049106ceaee7`，policy 为 `237ab084566cceb293ae5902e53ada13726db61c17d609a2a4c9ee7dd231796d`。实际调用的命令、退出码、stdout、stderr 和 gate hash 在 `results.json`；所有输入位于 `fixtures/`。

主代理在审查过程中并行修正 runner。最初静态读到的 finish 不完整状态问题，在本审查实际执行时已修好；下文按真实输出报告，不把旧静态问题冒充现存失败，也不声称所有组件属于同一初始版本。

## 实测结果

| 检查 | 真实结果 | 判断 |
|---|---|---|
| BM25/H1/v1.2 旁正常实测 6 | strict exit 0，traceable，checked_measurements=1 | 元数据无需登记；测量数仍被检查 |
| 同位置实测 9，原始值 6 | exit 2，value_mismatch fatal | 标识符不会挡住已登记测量核对 |
| 把错误 9 改成 8 | 仍 exit 2，同一个 value_mismatch ID | ID 没有依赖错误数值 |
| 来源仅增加 CRLF，保留旧 hash | exit 0，hash_drift warning，测量数仍核对 | 纯字节漂移未被冒判数字错误 |
| 同为 6，但来源换另一 run 并更新 hash | exit 2，source_run_mismatch | 不能用同值掩盖实验归属 |
| ruler 改为 needs_review | exit 0，尺子记录提示 | 脚本不替代科学审查 |
| 实际子进程 exit 3，诚实写 failed，保留 6 条部分结果 | capture exit 1；check exit 0/warnings | 失败报告没有被误杀 |
| 同一真实失败，改称 succeeded | exit 2，false_success | 失败事实与成功声明矛盾被识别 |
| gate 缺文档登记 | exit 0/incomplete | 材料不足独立呈现，不冒称致命造假 |
| 将上述结果交真实 finish 函数 | status=incomplete | 修复后的 runner 没有误标完成 |
| gate 正常但 reviewer needs_input | finish status=review_pending | 未完成审查没有被假装完成 |
| capture 的 run.json={} | incomplete，无 should-not-run 文件 | 没有启动该命令；exit 0 仅能配合结构化状态理解 |

以上是具体案例证据，不是管道总体可靠率。

## 发现一：实测，旧 identifier 分类能让真实候选数字无提示消失

位置：`fixtures/identifier-classification-bypass`。

正文 `BM25 measured 99 cases.`；来源实际值 6。scan 把 BM25 的 25 自动标为 identifier，但 99 没有 ignore_reason。claims 将 99 的 kind 写为旧的 identifier；该句本身仍登记为 measured。

实际调用：

```powershell
python skills/evidence-check/scripts/gate.py check reports/round-2/independent-review/fixtures/identifier-classification-bypass --strict
```

首测结果：exit 0，status=traceable，issues=[]，checked_measurements=0。

原因：所有 binding 的 index 先进入 mapped，非 measurement 随即跳过，导致没有被自动识别成元数据的 99 也从 unclassified_numbers 候选里消失。

严重度：中。建议只给语义审查 warning，而不是根据可疑分类直接判 fatal；这样既符合“只核对已登记测量”的范围，也符合 policy 对未确定数字应提示的要求。已经向主代理报告，没有自行改核心。

## 发现二：静态，失败恢复可能接受被拒绝的另一个线程 ID

正常成功恢复有实证，见下一节。这里是对异常控制流的独立分析，未模拟或实际诱导 CLI 换线程。

审查时新版 catch 为了挽回首次中断，会把 process.json 中记录的第一个 thread 写回 author_thread。如果当前请求 resume X，CLI 却返回 Y，model_session 会因不一致正确报错；但 catch 若无条件接受 recorded_threads，就把 author_thread 更新成 Y，下次会恢复错误会话。

建议只在原 author_thread 为空时接纳首次会话已有的唯一 thread；已有 author_thread 不能被不匹配的失败记录覆盖。已交主代理。异常恢复的真实 API 行为没有在本审查中测试，不应把静态修补当成异常路径实测通过。

## 返工封顶与作者会话的独立核对

`stable-id.json` 保存两次值错误的 ID，两者均为 `value_mismatch:fd7000362fccbf3e`。

对该问题实际调用 claim_repair：同一进程第一次 eligible=1，第二次 eligible=0/exhausted=1；再换新 Python 进程调用，仍 eligible=0/exhausted=1。rework.jsonl 只有一条 repair_started 和两条 disagreement_retained，counts.repair_rounds=1。这里预留了一次测试修复额度，没有实际让模型返工，不应把它写成一轮模型修复已经完成。

另独立读取既有 `reports/round-2/author-resume` 的原始 process、events、prompt、answer，未仅相信 result.json：

- 两次实际 thread.started ID 相同。
- 第二次命令使用 exec resume，resume_from 与该 ID 一致。
- 两次 exit 0，各有 turn.completed，均没有工具调用。
- 第二次提示没有重发随机测试标记，但回答保留了原标记。

核对保存在 `author-resume-observation.json`。这证明该成功样本的 CLI 连续性，不证明所有中断场景或研究质量。

## 测试修正与返工账

- 独立探针首轮一次运行；没有为变绿修改输入预期或重写反例。
- 独立审查者修改核心文件次数：0；新模型调用次数：0；业务实验次数：0。
- 独立报告的 gate 修复请求：1 个，原因是旧分类导致候选数字静默消失；静态线程修复请求：1 个，原因是异常路径可能覆盖原线程。
- 最初读取时的 finish 静态问题在主代理并行修复后，本轮真实组件调用已正确返回 incomplete/review_pending；不计成当前新缺陷或独立模型返工。
- claim_repair 机制测试有 3 次调用，只预留 1 次额度；后 2 次明确被封顶，是刻意验证次数限制，不是绕过上限重试。
- 修复后仅针对已报告问题复测一次，另存结果；若仍有分歧则保留，不无限修改。

本审查没有真实公司业务 brief，因此所有新建输入都标记为工具夹具，没有虚构团队经历、发布效果或业务提升。
