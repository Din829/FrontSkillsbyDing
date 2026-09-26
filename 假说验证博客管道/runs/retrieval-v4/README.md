# 第一轮检索研究的当前入口

这是保留的第一轮有效研究包，原始正文、台账和执行记录未修改。历史文档中的旧工作路径保留为当时的记录；复现请使用下面的归档脚本和冻结输入。

在 `_pipeline/` 目录执行，输出目录必须是新的：

```powershell
python archive/round-1/experiments/retrieval/run_experiment.py runs/retrieval-reproduction/results --corpus runs/retrieval-v4/results/experiment/corpus.json --queries runs/retrieval-v4/results/experiment/queries.json
```

阅读 [研究报告](REPORT.md) 或 [第二轮日语稿](article-round2.md)，[原稿](article.md) 留作对照。不要重新运行旧打包脚本覆盖归档；完整第一轮程序及依赖保存在 [archive/round-1](../../archive/round-1/README.md)。
