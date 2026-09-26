# 本地复算与更新

Python 3 标准库可以运行采集和分析；独立 HTML 解析器对照测试另需 beautifulsoup4。所有路径相对于 `_pipeline/research/zenn/`，在这里执行：

```powershell
python scripts/collect.py probe
python scripts/collect.py collect --plan sampling-plan.json
python scripts/analyze.py select
python scripts/collect.py details --selection selection.json
python scripts/analyze.py analyze
python scripts/validate.py
```

可选图表运行 `python scripts/plot.py`，需要 matplotlib。图中数字直接来自 statistics.json。

`probe` 的原始 liked_count 探测只为证明该参数无效，正式研究使用网站页面可见的 latest/alltime。`probe-extra.json` 还记录未知排序、trending、第二页和 count=200 实测。

采集计划是 JSON：queries 内每条包含 `topicname`（可省略表示全站）、`order`、`count`、`sample_target`。sample_target 是事前声明的研究采样目标，按完整页取回，因此可能超过目标；并非静默丢弃多余文章。不设置 sample_target 就继续 next_page 直到 API 结束，或错误/重复页停止；这仍不证明全站完整。当前 count 最大实测返回 100，不能靠增大 count 假设一次取全。

默认缓存命中不联网。要扫描新文章并在遇到一整页已知 ID 后停止：

```powershell
python scripts/collect.py collect --plan sampling-plan.json --refresh --incremental
```

incremental 的提前终止仅适用于 latest；alltime 会按计划重新扫描。最新内容增量不等于历史点赞更新；需要跟踪的正文列表另用 `details --selection selection.json --refresh`。刷新前的响应进入 raw/history。每次覆盖记录也进入 coverage-history。分页期间文章新增/排序变化仍可能导致漏项；需要稳定快照时重复检查边界与 ID 差异。

`validate.py --live` 用现有真实缓存验证零网络命中、刷新并遇到已知页后停止，保存 ruler_check.json；该检查会更新部分索引和 raw 历史，故完整研究发布前应重新跑 analyze。只离线复算则不加 --live。

原始 API 响应位于 raw；每个快照含 URL、观测时间、HTTP 状态及响应。metadata.json、body-features.json、statistics.json 都是衍生产物，可从 indexes 与 detail-index.json 重算。reading 是本地抽读文本，不进入公开产物。selection.json 与 pairs.json 保留正文选样依据。

所有统计都用 liked_count 字段快照；正文特征用详情快照，所以列表与正文观测时刻略有不同。分析不访问 /search、不登录、不读取任何 API key。超时、访问拒绝和解析错误显式失败，不替换成空数据，不将失败当作采集完成。
