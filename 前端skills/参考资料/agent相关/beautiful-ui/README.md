# Beautiful UI（AI 原生界面 20 个模式，MIT，本地源码）

> 来源：<https://www.beautifului.dev/>（作者 Shane Levine / Turbo 设计工作室，**MIT**，见 [LICENSE](LICENSE)）
> 抓取于 2026-08-19：站是 Next.js，源码在懒加载 chunk 里，用 Playwright 点每个区块的 "Copy code" 读剪贴板抓的（脚本在本目录 [`fetch-beautiful-ui.cjs`](fetch-beautiful-ui.cjs)：`npm i playwright` 后 `node fetch-beautiful-ui.cjs src`，重抓照跑）。`src/_index.json` 是机器可读索引。
>
> **用法协议同 [`../README.md`](../README.md)：知道有货、呈现选项，选用权在用户。**

## 是什么

专为"agent 跟人说话"的界面做的 20 个极其讲究的组件：思考态、流式正文、工具调用芯片、审批卡、任务行、diff 表、记录表、侧边栏、Prompt 输入条……全是 **React + Tailwind 类名 + 少量 CSS 变量**，单文件 copy-paste。跟本目录的 thinking-orbs（思考球）、aicss（14 组件）是同一件事的三套皮，按场景挑、给用户看选项。

## 索引（按场景）

| 场景 | 组件 | 一句话 | 文件 | 行 | 外部依赖（react 之外） |
|---|---|---|---|---|---|
| **思考中** | Thinking | 可展开的思考轨迹：steps / reasoning / search / coding 四种 | `ThinkingState.tsx` | 274 | — |
| **长任务等待** | Loading State | 像素网格加载器 + shimmer + 已用时；4 变体 Drive / Dots / Orbit / Surfer | `LoadingState.tsx` | 152 | — |
| **流式正文** | Streaming Text | 流式回答 + 行内来源 + 操作 + 追问建议 | `StreamingText.tsx` | 224 | — |
| **工具调用（紧凑）** | Tool Chips | 代码编辑 / 工具调用压成芯片 | `ToolChips.tsx` | 290 | react-dom |
| **工具调用（列表）** | Task Rows | agent 任务实时状态 running / failed / completed；2 变体 Capsules / List | `TaskRows.tsx` | 222 | — |
| **人工审批** | Approval Card | agent 动手前问人的问题卡（human-in-the-loop）。**形态是多问题分页问卷**（三问 + 圆点分页），做单次"批准 / 拒绝"要裁成一问一卡 | `ApprovalCard.tsx` | 241 | — |
| **代码输出** | Code Block | agent 写的代码逐行流出 | `CodeBlock.tsx` | 109 | — |
| **diff** | Diff Table | AI 提议的修改在表格里扫过 | `DiffTable.tsx` | 238 | `@/components/atoms/Button`（内部，自换） |
| **检索结果** | Context Cards | 召回的知识块 + 来源 | `ContextCards.tsx` | 91 | — |
| **建议 / 洞察** | Recommendation Card | 带置信度条的建议 + 操作 | `RecommendationCard.tsx` | 174 | `@/components/atoms/Button`（内部） |
| | Insight Cards | 分页洞察 + 可拖动实时图 | `InsightCards.tsx` | 456 | `liveline` |
| **输入** | Prompt Bar | @ 来源、/ 命令、模型选择、语音 | `PromptBar.tsx` | 713 | `glimm` |
| | Chat | 带推理回复的标签页聊天面板 + 输入框 | `ChatComposer.tsx` | 190 | `posthog-js`（只是埋点，删掉即可） |
| **选中文字交给 agent** | Selection Actions | 划一段文字让 agent 重写 | `SelectionActions.tsx` | 492 | `iconoir-react`、内部 Shimmer / StreamText |
| **数据表** | Records Table | CRM 式表格：标签、排序、关系状态 | `RecordsTable.tsx` | 765 | 内部 GlideMenu |
| | Filter Table | 状态芯片实时重排数据 | `FilterTable.tsx` | 123 | — |
| **导航 / 搜索** | Sidebar Nav | 可折叠工作区 + 聊天导航，滑动 hover | `SidebarNav.tsx` | 389 | `@central-icons-react`（换任意图标库）、内部 GlideMenu |
| | Search | 命令式搜索 + 实时过滤 + 空态 | `SearchList.tsx` | 94 | 内部 GlideMenu |
| **流程** | Flowchart | 点阵画布上的触发 / 条件步骤 | `Flowchart.tsx` | 539 | — |
| **属性面板** | Fine-tune Card | agent 在检查器里调设计属性 | `FineTuneCard.tsx` | 250 | 内部 GlideMenu |

**内部依赖没抓到**（站上没公开）：`@/components/primitives/GlideMenu`（一个滑动高亮的下拉菜单）、`@/components/atoms/{Button, Shimmer, StreamText}`。用的时候自己换：Button → 项目里的按钮；GlideMenu → 任意下拉；Shimmer / StreamText → [`../aicss组件索引.md`](../aicss组件索引.md) 的 `thinking-state` / `streaming-text` 同义。

## 跟同目录其他料怎么分工

| 你要 | 先看 |
|---|---|
| 思考态一个小球 / 行内指示 | thinking-orbs（canvas，9 态）或 aicss `orbs`（DOM，25 个） |
| 思考态要展开看过程 | 本库 Thinking 或 aicss `thinking-reasoning` |
| 工具调用过程的**范式**（状态机、收起时机） | [`../agent-tool-progress.md`](../agent-tool-progress.md)，皮可用本库 Tool Chips / Task Rows 或 aicss `web-search` / `task-list` |
| **审批卡**（Harness 的 `tool_approval_requested` 落到界面） | **只有本库有现成的**（Approval Card） |
| 表格 / 侧栏 / 搜索这类功能型件 | 本库 Records Table / Sidebar Nav / Search；基座仍是 shadcn/ui（AI 会） |
