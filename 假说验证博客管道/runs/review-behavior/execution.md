# 执行证据

原模型调用逐份保存在 results/study/sessions，补测副本保存在 results/pinned-study-snapshot/sessions。source-index.json 逐项记录答案、提示、进程和事件文件散列。

原研究有 48 个不同 thread，全部成功完成；原始事件中工具项目为 0。补测另有 24 个不同 thread，与原批次不重叠。

results/execution.json 记录的是交付阶段真实运行 review_results.py 的核对过程，不是原模型调用的统一执行记录。其开始结束时间只属于本次核对；没有回填或伪造原调用时间。

ruler_check.json 校准的是来源与计数检查；原标签评分器的语义缺陷仍记录为未通过，不能用本包 gate 通过覆盖该缺陷。
