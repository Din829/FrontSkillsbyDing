# aicss.dev 组件中文索引

> 来源：[aicss.dev](https://www.aicss.dev)（Kevin [@kvnkld](https://x.com/kvnkld)，Beta，2026-08 爬取）。
> agent 对话界面组件全家桶：14 组件 × React/Vue/Svelte 三实现，Orbs 另有 25 变体。

## 授权与红线（agent 必读）

- 作者授权 "free to use"：**可以把单个组件代码用进用户的产品**（建议保留来源注释）。
- **没有再分发授权**：本地源码目录 `aicss-dev/` 已被 `.gitignore` 排除，**绝不把它复制进任何会公开的仓库**。
- 本机没有 `aicss-dev/` 目录？跑同目录 [`crawl-aicss.cjs`](crawl-aicss.cjs) 再生（需 node + playwright，见脚本头注释）。
- 站点在 beta 快速迭代，要最新版可重跑脚本；线上效果预览直接开组件页链接。
- 子库协议同样适用：**用哪个组件，呈现选项给用户挑，别自己拍板。**

## 怎么用（三步）

1. 按下表找到匹配场景的组件，把"效果"一句话+线上预览链接呈现给用户选；
2. 用户选定后，按用户技术栈取本地文件：`aicss-dev/<slug>/<react|vue|svelte>/<文件>`（React 是 `.tsx` + `.module.css` 两件套，Vue/Svelte 是单文件组件）；
3. 融入项目：改成项目的 token/主题（对照 `参考资料/设计系统库/` 或项目自己的 tokens），别原样硬贴。

## 组件索引（14 个，按 5 类）

### 思考与推理

| slug | 效果 | 对应范式角色 | 预览 |
|---|---|---|---|
| `thinking-state` | 极简 shimmer 微光文字标签，"回答前正在处理"的信号 | [`agent-tool-progress`](agent-tool-progress.md) 的**活着信号**最小实现 | [页面](https://www.aicss.dev/components/thinking-state) |
| `thinking-reasoning` | 可折叠思考块：shimmer 标签展开露出推理过程，结束折成 "Thought for Ns" 汇总 | 范式"干活时透明、说完收起"的思考版 | [页面](https://www.aicss.dev/components/thinking-reasoning) |
| `orbs` | 25 个紧凑活动指示球（纯 DOM+CSS，不阻塞线程），5 族×5：**S**=Lattice 点阵 / **B**=Lens 透镜 / **C**=Ring 环 / **G**=Helix 螺旋 / **M**=Morph 变形 | 活着信号图标位；与 thinking-orbs（canvas 版）二选一呈现给用户 | [页面](https://www.aicss.dev/components/orbs) |

> orbs 本地路径特殊：`aicss-dev/orbs/<变体>/<框架>/`，每变体是裁剪好的独立组件（如 `orbs/M3/react/Orb.tsx`）。

### 工具与操作状态

| slug | 效果 | 对应范式角色 | 预览 |
|---|---|---|---|
| `web-search` | 实时搜索态：shimmer 查询头 + 来源逐条出现、地球图标逐个变对勾 | 范式**时间线皮**的完整现成示例（挨个出现+变脸都有） | [页面](https://www.aicss.dev/components/web-search) |
| `file-diff` | 行内 diff 卡片：agent 提议的增删改一目了然 | 工具结果展示 | [页面](https://www.aicss.dev/components/file-diff) |
| `image-generation` | 生图中的 shimmer 画布占位 | 长任务等待态 | [页面](https://www.aicss.dev/components/image-generation) |

### 文本输出

| slug | 效果 | 预览 |
|---|---|---|
| `text-response` | 标准回答的干净排版（含行内 code） | [页面](https://www.aicss.dev/components/text-response) |
| `streaming-text` | 打字机流式文字 + 闪烁光标 | [页面](https://www.aicss.dev/components/streaming-text) |
| `inline-citations` | 上标引用角标 + 紧凑来源脚注 | [页面](https://www.aicss.dev/components/inline-citations) |
| `code-block` | 代码块：语言标签 + 一键复制 | [页面](https://www.aicss.dev/components/code-block) |

### 结构化输出

| slug | 效果 | 对应范式角色 | 预览 |
|---|---|---|---|
| `task-list` | Cursor 风格任务列表：可折叠头部 + done/in-progress/pending 三态条目 | 范式**卡片组皮**的现成示例 | [页面](https://www.aicss.dev/components/task-list) |
| `data-table` | 整洁数据表 | — | [页面](https://www.aicss.dev/components/data-table) |
| `comparison-table` | 按方案对比的功能矩阵（对勾） | — | [页面](https://www.aicss.dev/components/comparison-table) |

### 富交互

| slug | 效果 | 预览 |
|---|---|---|
| `ai-agent-input` | 输入框组合件：附件 + 模型切换菜单 + "增强提示词"工作态（idle/filled/enhancing/enhanced 四态） | [页面](https://www.aicss.dev/components/ai-agent-input) |

## 与本子库其他资产的关系

- **[`agent-tool-progress.md`](agent-tool-progress.md)** 管骨架（状态机/时机/铁律），本库组件是现成的皮：`thinking-state`=活着信号、`task-list`=卡片组、`web-search`=时间线。皮怎么换，骨架规则都得守（尤其收起时机）。
- **thinking-orbs**（canvas，9 态）和这里的 **orbs**（DOM+CSS，25 变体）是同一角色的两套备选——呈现给用户时说明差异：前者语义化状态（searching/composing…），后者视觉族谱更多但无语义绑定。
