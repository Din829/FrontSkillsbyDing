# agent 相关 UI（子库）

> 本目录是 [`参考资料/`](../README.md) 的「agent 交互 UI」子库：**交互范式**（工具调用过程怎么展示）+ **现成组件**（思考态指示球等），专供 AI/agent 界面。

## 使用协议（agent 必读）

**你的职责是"知道有货、呈现选项"，不是替用户拍板。** 界面里要用到 agent 状态指示/加载动效时：先翻本索引，把匹配的组件（含效果一句话描述）作为选项**呈现给用户，由用户决定用哪个**；用户明确选定后再落地。别自作主张直接选一个塞进界面。**无人应答时**（脚本任务 / 批处理）：选首选，交付说明里写清候选与理由，别卡住也别静默吞掉候选。

---

## agent-tool-progress（交互范式：工具调用过程展示）

要做 agent 界面里"工具/任务执行过程"的实时展示 → **读 [`agent-tool-progress.md`](agent-tool-progress.md)**。它定义交互骨架：组级/条目级状态机、五条行为铁律（挨个出现、并行独立变脸、running 必须有活着信号、**收起时机=agent 正文首个流式 token**、节点连线）、元信息分级、流式 SDK 事件映射。**骨架不能破，视觉皮随项目**。running 动效可配下面的 thinking-orbs。可跑参考实现：[`demo-tool-progress.html`](demo-tool-progress.html)（零依赖，浏览器直接开；**它的完成态用了绿色，只是演示——落地时颜色按项目 token，遵守 pro 4.1"唯一的彩色留给唯一需要警觉的事"**）。

---

## thinking-orbs（主力组件，MIT，可直接抄）

**AI/agent 界面的"思考中"状态指示球**——点阵球形动画，9 种手调状态各对应一类 agent 动作。纯 2D Canvas（无 WebGL 无滤镜），三大浏览器渲染一致，低端设备友好（DPR 上限 2）。作者 Jakub Antalik，**MIT**，npm 包 `thinking-orbs`（v0.3.1），[在线 demo](https://orbs.jakubantalik.com)。

**本目录 `thinking-orbs/` 是完整源码副本**：`src/`（React 组件 + engine）、`demo/`（可跑演示）、`spec/`（动画规范 JSON）、`ports/react-native/`（RN/Skia 移植）。

### 9 种状态（给用户呈现选项时用这张表）

| state | 效果 | 适合表达的 agent 动作 |
|---|---|---|
| `working` | 粒子在倾斜轨道上运行 | 通用"干活中"（默认值） |
| `searching` | 扫描经线扫过虚线地球 | 检索 / 搜索中 |
| `solving` | 频带打乱后咔哒复位 | 推理 / 解题中 |
| `listening` | 波形穿过纬度环 | 语音输入 / 聆听中 |
| `connecting` | 星座自动连线、数据包沿边跑 | 连接服务 / 调用工具中 |
| `weaving` | 三股辫绕球体编织 | 整合 / 编排中 |
| `composing` | 多频带绶带起伏 | 生成 / 写作中 |
| `breathing` | 正面光环缓慢变形 | 空闲待命 / 轻量等待 |
| `shaping` | 虚线轮廓 圆→三角→方 | 转换 / 塑形处理中 |

### 用法速查（事实源：`thinking-orbs/README.md` + `src/types.ts`）

```tsx
// 方式一：npm（正规项目）
npm install thinking-orbs
import { ThinkingOrb } from 'thinking-orbs';
<ThinkingOrb state="searching" size={64} />

// 方式二：直接抄源码（MIT；单文件场景抄 src/ 进项目）
```

| prop | 取值 | 默认 | 说明 |
|---|---|---|---|
| `state` | 上表 9 选 1 | `working` | 动画状态 |
| `size` | **只有 `64` 或 `20`**（类型锁死） | `64` | 64=聊天头像级，20=行内文本级；两套独立设计，不是缩放 |
| `theme` | `auto` / `dark` / `light` | `auto` | auto 三层探测：祖先 `data-theme`/`dark` 类（Tailwind/shadcn 约定，MutationObserver 实时跟）→ `prefers-color-scheme` → SSR 安全（客户端才绘制） |
| `speed` | 数字倍率 | `1` | 在预设速度上叠乘 |
| `paused` | 布尔 | `false` | 冻结当前帧 |
| `aria-label` | 字符串 | 每状态自带默认 | 覆盖无障碍标签 |

其余 `<canvas>` 属性（`className`/`style`/`data-*`）透传。

**内置的省心项**：`role="img"` 默认无障碍；`prefers-reduced-motion` 自动静态帧；离屏/切标签自动暂停（IntersectionObserver）、恢复时全实例同相位。

**高级入口**：`thinking-orbs/engine` 子导出（`resolvePreset` + `MODE_DRAWS` 帧绘制器）——不用 React、自己驱动 canvas 时用。

---

## aicss.dev（agent 对话界面组件全家桶，本地素材）

Kevin（[@kvnkld](https://x.com/kvnkld)）的 agent 界面组件站：14 个组件覆盖思考态/工具态/文本输出/结构化输出/输入框，每个带 React/Vue/Svelte 三实现，其中 Orbs 有 25 个变体。**是 [`agent-tool-progress.md`](agent-tool-progress.md) 范式的现成皮**（Thinking State=活着信号、To-do List=任务列表、Web Search=时间线）。

- **索引（先读）**：[`aicss组件索引.md`](aicss组件索引.md) —— 全组件中文速查 + 本地路径 + 使用指引
- **源码不入公开仓库**："free to use" 只授权用进产品，没授权再分发（官网无 LICENSE、无条款页、无 GitHub 仓库）。`aicss-dev/` 已被 `.gitignore` 排除。
- **需要时现场取，不必先落盘**：`node fetch-aicss.cjs <slug>` 直接打印四份实现（React/CSS/Vue/Svelte）。零依赖，Node 18+ 即可。整套落盘用 `--all --out aicss-dev`。
- ⚠️ agent 注意：可以把单个组件代码用进用户的项目（作者授权范围内、保留署名注释更好），**但不要把 `aicss-dev/` 整目录复制进任何会公开的仓库**。

---

## Beautiful UI（AI 原生界面 20 个模式，MIT，本地源码）

Shane Levine / Turbo 工作室的 <https://www.beautifului.dev/>：思考态、流式正文、**工具调用芯片 / 任务行**、**审批卡（human-in-the-loop）**、diff 表、记录表、侧边栏、Prompt 输入条……20 个 React + Tailwind 单文件组件，**MIT**，2026-08-19 抓到本地 `beautiful-ui/src/`。

- **索引（先读）**：[`beautiful-ui/README.md`](beautiful-ui/README.md) —— 按场景列 20 个、行数、外部依赖、跟 thinking-orbs / aicss 怎么分工
- **审批卡只有它有**：Harness `事件流对接.md` 的 `tool_approval_requested` 要落到界面，直接用 Approval Card
- 几个组件引用了站上没公开的内部件（GlideMenu / Button / Shimmer / StreamText），索引里写了怎么换

---

## 灵感区（只看效果，禁止搬代码）

| 项目 | 是什么 | License | 使用限制 |
|---|---|---|---|
| [25-unique-loaders](https://github.com/Appllama/25-unique-loaders) | 25 个原创**加载按钮**动画（按钮 loading 态），零依赖 WebGL2/Canvas/SVG/CSS，各带状态文案 | **GPL-3.0** | ⚠️ **传染性协议：代码一行都不能抄进闭源/商用项目**（会要求整个项目开源）。只允许看在线效果找灵感，自己从零实现类似效果 |

---

## 维护

- thinking-orbs 原仓在 `AgenticWorkflow/参考项目/前端与设计/thinking-orbs/`，更新去那边 `git pull` 再同步过来（本目录不含 .git）。
- 加新组件库：目录放进来（MIT/Apache 等宽松协议才收源码；GPL 类只进灵感区表格）→ 本 README 登记 → `frontend-design-pro.md` 第〇节路由表确认覆盖。
