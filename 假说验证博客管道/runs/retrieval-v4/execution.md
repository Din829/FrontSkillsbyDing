# 执行摘要

主实验由真实 capture 运行，退出码为 0。实际命令、开始结束时间以及 stdout/stderr 散列在 results/execution.json；该记录未被包装过程重写。

最终原始产物包括固定正文、固定题目、排序校准和逐题完整排名。派生 metrics.json 逐项记录输入文件、定位方式和聚合公式；历史数字明确命名为 initial，不能当成最终数字。

复现命令（从 run 目录执行，输出目录必须是新目录）：

```powershell
python ../../experiments/retrieval/run_experiment.py replay --queries results/experiment/queries.json --corpus results/experiment/corpus.json
```

打包命令：

```powershell
python ../../experiments/retrieval/package_result.py
```

该命令只刷新派生交付物，最后运行严格证据核对；不重跑检索、不覆盖真实执行记录。

没有生成式模型参与检索评分或回答生成。本地实验消费与 AI 编题、审查和写作应分开理解；后者缺少单独结算费用，本报告没有把未知费用填成零。

