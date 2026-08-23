---
name: openai-agent-sdk
description: OpenAI Agents SDK（TypeScript/JavaScript）实战参考。当任务是"用 Agents SDK 搭 agent / 加沙箱 / 接非 OpenAI 模型 / 把 agent 流式过程接到前端"时读这份。核心：只写你记忆里没有或已经过时的部分。
---

用中文交流。

> **来源**：OpenAI Agents SDK 官方文档 + 仓库源码 <https://github.com/openai/openai-agents-js>
> **核对于 2026-08-18**，对应 `@openai/agents` **0.16.1**（Python 版 `openai-agents` 0.21.1）。同日用四组干净上下文的 agent 盲测过一轮（`devtest/harness-skill-test/`），据此补了陷阱 8、9 和官方页抓取提示。

---

## 三条信条

**1. 先划清你的知识边界。** 这个 SDK 还在 **0.x**——发布一年多、上百个版本没标 1.0，且**每月都在加新 API**。

好消息：核心概念（Agent / Runner / handoff / guardrail / tool）从 0.1 到现在**没有 breaking change**，那部分信你自己的记忆没问题。

坏消息：**你的训练数据一定不包含最近几个月的东西。** 下面这些是近期加的，按发布时间排——**你的知识截止在哪个月，那之后的全部是你的盲区**：

| 时间 | 加了什么 | 不知道会怎样 |
|---|---|---|
| 2026-08-16 | 模型调用超时（`model call timeouts`） | 不知道有这个参数，自己造轮子 |
| 2026-08-05 | Session 历史事务 | 自定义 session 的并发安全写法不对 |
| 2026-07-24 | **敏感数据日志默认关闭** | debug 时奇怪"日志里怎么没内容"，要显式 `setSensitiveDataLoggingEnabled(true)` |
| 2026-07-18 | **Programmatic Tool Calling** | 完全不知道有这功能：模型可以生成 JS 代码来编排多个工具调用，需要 `programmaticToolCallingTool()` ＋ 每个工具设 `allowedCallers` |
| 2026-04 | 沙箱、子 agent、Codex 式文件工具 | 硬写必错，见 `sandbox-agents.md` |
| — | Standard Schema 输入/输出、`RunState` 持久化待处理输入、自定义 session 拿 run context | 用旧写法 |

**判断问句：我的知识截止是哪个月？** 在这张表里找到那个位置，往上的全部是盲区——**别猜，去查**（查法见本文最后一节）。

**2. 这份文档不是教程，是差异表。** 你已经会的东西这里只给一句话和链接，不复述。真正展开的是四块：对话式应用、沙箱、接别家模型、流式对接。

路由表里标"你会"的行，意思是**"多数情况下你会"，不是保证**。判断标准很简单：**你能不能直接写出这个 API 的准确签名？** 能就写，有一丝犹豫就点链接——**点链接的代价是几百 token，写错的代价是整段返工。**

**3. 报错比静默失败值钱。** 这个 SDK 有好几处"配错了不报错、只是行为变了"的地方（见第二节标 🔴 的几条）。写完自己回头对一遍那几条，比加一堆 try/catch 有用。

---

## 〇、按需路由（先看这个）

### 第〇步：你在做哪一档

| 档 | 判断 | 读什么 |
|---|---|---|
| **Demo / 给客户摸一下 / 内部小工具** | 单人用、坏了重启没人骂 | 本目录五份按下面路由读，**够了**（`生产层-经验总结.md` 自己就说"只跑 demo 九成内容用不上"） |
| **生产** | 真人用户、多轮、要能停、要可审计 | 下面路由之外，**必读 [`生产层-经验总结.md`](生产层-经验总结.md)**——SDK 只给循环，产品层九个域（模型接入 / 上下文 / 长期记忆 / 工具 / 运行时控制 / 流式 / 提示词 / 观测 / 质量）全要自己补，那份每条钉着实测或事故；它第 0 节"SDK 到哪儿为止"就是分界线 |

同一个功能在两档做多深不一样（记忆：demo 一行 `MemorySession`，生产要落库 + 事务 + 锁；审批：demo 存活对象，生产要序列化 + TTL + 跨实例）。**先定档，再往下走。**

### 第一步：你在做哪类应用

| 应用形态 | 先读 |
|---|---|
| **聊天型**（独立聊天产品、嵌进现有产品的助手/客服窗） | **`对话式应用.md`** —— 三个必须先定的决策 |
| **语音对话** | `对话式应用.md` 最后一节定 transport，然后直接看官方 Realtime 那条线 |
| 要把 agent 干活过程**展示到前端** | **`事件流对接.md`** |
| **agent 要改文件、跑命令**（coding / 文档处理） | **`sandbox-agents.md`** |

### 第二步：具体功能去哪查

**本地深水区**（我们写了、你多半不会的）：

| 主题 | 去哪 |
|---|---|
| 沙箱、文件系统工具、工作区隔离 | `sandbox-agents.md` |
| 流式事件 → UI、收起时机、AI SDK UI helper | `事件流对接.md` |
| Session 读写时机、`asTool` vs `handoff`、两种 context | `对话式应用.md` 决策一 ~ 三 |
| **人工审批完整链路**（needsApproval → interruptions → approve/reject → 续跑） | `对话式应用.md` 决策四 |
| **上下文怎么控**（裁历史 / 压缩 / 服务端会话 / 工具元数据不进历史 / maxTurns） | `对话式应用.md` 决策五 |
| **生产化**（并发锁 / 显式停止 / 心跳 / 长期记忆 / 观测 / 提示词纪律） | `生产层-经验总结.md`（生产档必读，见第〇步） |
| **图片/文件输入**、撤回一轮 | `对话式应用.md` 决策五之后 / 决策二 |
| 装包、导入路径、9 条陷阱 | ↓ 本文第一、二节 |

**官方文档**（你多半会，或细节易变，直接查原文）。"这页有什么"一列**只列名字**——让你知道功能存在，要用再点进去，别凭记忆猜签名：

| 页 | 这页有什么（只列名字） | 备注 |
|---|---|---|
| [agents](https://openai.github.io/openai-agents-js/guides/agents/) | 基本配置 · `outputType`（结构化输出）· 动态 instructions / `prompt` · 生命周期钩子 · guardrails · `clone()` · **Forcing tool use**（`modelSettings.toolChoice` + `toolUseBehavior`，含防死循环 `resetToolChoice`） | 你会基础；`outputType` / `toolUseBehavior` 拿不准查 |
| [running-agents](https://openai.github.io/openai-agents-js/guides/running-agents/) | agent loop · run 参数 · RunConfig · **四种记忆策略对照表**（`result.history` / `session` / `conversationId` / `previousResponseId`）· `callModelInputFilter` · `toolErrorFormatter` · `reasoningItemIdPolicy` · 错误处理器 · 异常清单（`MaxTurnsExceededError` 等） | 记忆策略那节必看，摘要在 `对话式应用.md` 决策五 |
| [tools](https://openai.github.io/openai-agents-js/guides/tools/) | ① Hosted：`web_search` / `file_search` / `code_interpreter` / `image_generation` / `tool_search`（延迟加载）/ PTC · ② 内置执行工具：computer / shell / apply_patch · ③ 函数工具：Options reference · `customDataExtractor`（SDK 侧私有数据）· `timeoutMs` · 非严格 schema · ④ agents as tools（`onStream`）· ⑤ MCP · ⑥ Codex（实验）· 工具策略与最佳实践 | hosted 清单和函数工具选项要查 |
| 同页 **Programmatic Tool Calling** | 模型生成 JS 编排多个工具 | **2026-07 才有，你不知道**。要 `programmaticToolCallingTool()` ＋ 每个工具设 `allowedCallers` |
| [multi-agent](https://openai.github.io/openai-agents-js/guides/multi-agent/) | LLM 编排（asTool / handoff）· 代码编排 | **对话式必看**，摘要在 `对话式应用.md` 决策一 |
| [handoffs](https://openai.github.io/openai-agents-js/guides/handoffs/) | `handoff()` 定制（`toolNameOverride` / `toolDescriptionOverride` / `inputType` / `inputFilter` / `onHandoff`）· `removeAllTools` 输入过滤 · 推荐 prompt 前缀 | 你会；工具名陷阱见 🔴8 |
| [guardrails](https://openai.github.io/openai-agents-js/guides/guardrails/) | input / output / tool 三处 · 执行模式（`runInParallel` 并行 vs 先拦后跑）· tripwire | 你会 |
| [sessions](https://openai.github.io/openai-agents-js/guides/sessions/) | `MemorySession` / `OpenAIConversationsSession` / `OpenAIResponsesCompactionSession` · runner 读写时机 · CRUD · 自定义存储（原子幂等 · run context 作用域 · 历史事务）· `sessionInputCallback` 合并规则 · 审批恢复 · **history compaction**（自动 / 手动） | **关键语义在 `对话式应用.md` 决策二、五** |
| [context](https://openai.github.io/openai-agents-js/guides/context/) | Local context（`RunContext`）· LLM-visible context | 摘要在 `对话式应用.md` 决策三 |
| [results](https://openai.github.io/openai-agents-js/guides/results/) | `finalOutput` · `history` / `newItems` · `lastAgent` · `interruptions` + `state` · `lastResponseId`（服务端续接）· 嵌套 agent-tool 元数据 · `rawResponses` · guardrail 结果 · `usage` | 你会基础 |
| [models](https://openai.github.io/openai-agents-js/guides/models/) | 默认模型 · GPT-5.x vs 非 5.x · OpenAI provider 选项（认证 · Chat Completions 音频 · **Responses WebSocket 传输** · Responses 专属延迟工具）· **Hosted Multi-agent（实验）** · ModelSettings（`reasoning` / `verbosity` / `promptCacheRetention` / **`contextManagement` 服务端压缩** / **`timeoutMs`**）· **Model retries**（`modelSettings.retry`，**默认不重试**）· `prompt` 模板 · 自定义 provider · tracing 凭据 | **先看第二节 🔴1、🔴2** |
| [streaming](https://openai.github.io/openai-agents-js/guides/streaming/) | 开启 · `toTextStream()` · 三类事件 · Responses WebSocket · 流式中审批 · 中途停流续同一轮 | 接 UI 看 `事件流对接.md` |
| [human-in-the-loop](https://openai.github.io/openai-agents-js/guides/human-in-the-loop/) | 审批流 · 恢复前追加输入 · **自动审批决策**（shell / apply_patch 的 `onApproval`，hosted MCP 的 `requireApproval`）· 流式 + session · 长时间挂起（`RunState` 序列化 + 版本化） | **链路已写在 `对话式应用.md` 决策四**，先看那个 |
| [schemas](https://openai.github.io/openai-agents-js/guides/schemas/) | Standard Schema 库 · 限制 | **先看第二节 🟡5**，zod 是 4 |
| [mcp](https://openai.github.io/openai-agents-js/guides/mcp/) | Hosted MCP（含审批 · connector 型）· Streamable HTTP · Stdio · agent 级 MCP 配置 · 生命周期 / dispose · server 前缀工具名 · **tool filtering** | 你会概念，接法细节查原文 |
| [tracing](https://openai.github.io/openai-agents-js/guides/tracing/) | trace / span · 默认导出 · 高层 trace · 敏感数据 · OpenAI exporter · 自定义 processor · 外部 processor 列表 | **先看第二节 🔴1** |
| [testing](https://openai.github.io/openai-agents-js/guides/testing/) | 固定响应 · 工具流 · 检查模型调用 · 流式 · 注入失败 · 漂移检测 · 沙箱 recipe · Realtime recipe · API 速查 | recipe 型，照抄比复述准 |
| [config](https://openai.github.io/openai-agents-js/guides/config/) | key 与 client · API 选择（Responses vs Chat Completions）· Responses transport · tracing 开关 · debug 日志（敏感数据） | 排查连接问题时看 |
| [troubleshooting](https://openai.github.io/openai-agents-js/guides/troubleshooting/) | 支持环境（Deno / Bun / Workers 限制）· debug 日志 | 遇到怪问题先看这 |
| [release](https://openai.github.io/openai-agents-js/guides/release/) | 版本规则（0.x 的 minor 可能 breaking）· changelog 入口 | **对照第一节知识边界表用**：不确定某 API 是哪个版本加的，去 changelog 查 |
| [voice-agents](https://openai.github.io/openai-agents-js/guides/voice-agents/) ＋ [transport](https://openai.github.io/openai-agents-js/guides/voice-agents/transport/) | 概览 · quickstart · build（工具 / 审批 / 中断 / guardrail）· transport（WebRTC / WebSocket / SIP） | 本 Harness 不复述，直接看官方 |
| [extensions/ai-sdk](https://openai.github.io/openai-agents-js/extensions/ai-sdk/) | 接非 OpenAI 模型 | **先看第二节 🔴2** |
| [extensions/twilio](https://openai.github.io/openai-agents-js/extensions/twilio/) | Realtime 上 Twilio（电话） | 电话客服场景 |
| [extensions/cloudflare](https://openai.github.io/openai-agents-js/extensions/cloudflare/) | Realtime 上 Cloudflare | 边缘部署 |
| **API Reference** | [文档站](https://openai.github.io/openai-agents-js/) 左侧导航，typedoc 自动生成，按包分（`@openai/agents`、`agents-core`、`agents-realtime` 等） | **拿不准签名去这里或本地 `.d.ts`，别猜** |

**🟡 上面这些官方页用 WebFetch 抓，常常只拿到导航壳、正文被截断**（human-in-the-loop / streaming 页实测如此，三次白跑）。要原文抓仓库 raw：`https://raw.githubusercontent.com/openai/openai-agents-js/main/docs/src/content/docs/guides/<slug>.mdx`（`<slug>` 就是上面链接最后一段；multi-agent 那页是 `.md`，404 就换后缀）。更快的是直接翻本地 `node_modules/@openai/agents-core/dist/*.d.ts`——见第三节。

**Python 版**在 <https://openai.github.io/openai-agents-python/>。它多出 Voice agents（STT/TTS 管道，和 Realtime 是两套）、Usage、Visualization、REPL 几页，Sessions 也有更多现成的持久化后端。**新能力通常 Python 先落地**，TS 里找不到时去那边确认是不是版本差。

---

## 一、基盘：起手

### 包结构

装一个 `@openai/agents` 就够了，它是壳，把三个实现包收在一起：

```
@openai/agents          ← 你装这个（壳，带默认配置副作用）
├── @openai/agents-core     真正的 Agent / Runner / tool / tracing
├── @openai/agents-openai   OpenAI provider 与 tracing exporter
└── @openai/agents-realtime 语音

@openai/agents-extensions   ← 另装：接别家模型、托管沙箱、前端流
```

### 导入路径矩阵

写错子路径是最常见的低级错误，照这张表：

| 从哪导 | 拿什么 |
|---|---|
| `@openai/agents` | `Agent` `run` `Runner` `tool` `handoff` 等主力 |
| `@openai/agents/sandbox` | `SandboxAgent` `Manifest` `Capabilities` `localDir` `skills` |
| `@openai/agents/sandbox/local` | `UnixLocalSandboxClient` `DockerSandboxClient` |
| `@openai/agents/testing` | 测试替身 |
| `@openai/agents/realtime` `/realtime/testing` | 语音 |
| `@openai/agents/utils` | 杂项工具 |
| `@openai/agents-extensions/ai-sdk` | **接非 OpenAI 模型**（走 Vercel AI SDK provider） |
| `@openai/agents-extensions/ai-sdk-ui` | **把 agent 流转成前端可消费的响应** |
| `@openai/agents-extensions/sandbox/{e2b,modal,daytona,vercel,cloudflare,blaxel,runloop}` | 七家托管沙箱 |
| `@openai/agents-extensions/experimental/codex` | Codex 工具（实验中） |

### 运行环境事实

- **Node.js 22+**（也支持 Deno、Bun；Cloudflare Workers 需开 `nodejs_compat`，实验支持）
- **peerDependency 是 `zod ^4`**
- 本机 TypeScript 是 **7.x**：`moduleResolution: "node"`/`"node10"` 已被移除（报 `TS5108`），tsconfig 用 `nodenext` 或 `bundler`（盲测里两个 Sonnet 组都撞了这条）
- 沙箱用 `tty: true` 时，宿主进程要能找到 `python3`（或设 `OPENAI_AGENTS_PYTHON`）；不开 PTY 则不需要

### 最小可跑

```ts
import { Agent, run } from '@openai/agents';

const agent = new Agent({
  name: 'Assistant',
  instructions: 'You are a helpful assistant.',
});

const result = await run(agent, '用一句话解释递归');
console.log(result.finalOutput);
```

要沙箱、要文件操作 → 去 `sandbox-agents.md`，别在这里往下猜。

---

## 二、陷阱清单

> 🔴 = 配错了**不报错**，只是行为变了（最危险）　🟡 = 会报错或明显失败

### 🔴 1. `import` 那一刻就绑定 OpenAI 了

主包 `index.ts` 在模块加载时执行了两句副作用：

```ts
setDefaultModelProvider(new OpenAIProvider({ ... }));
setDefaultOpenAITracingExporter();
```

**后果**：只要 `import { Agent } from '@openai/agents'`，默认 model provider 和 **tracing 上传目标**就已经是 OpenAI 了——哪怕你后面把模型换成了 Claude。你没写任何 tracing 代码，追踪数据照样往 OpenAI 服务器传，且需要 OpenAI API key。

**用非 OpenAI 模型时必须显式处理**，二选一：

```ts
import { setTracingDisabled } from '@openai/agents';
setTracingDisabled(true);                    // 方案 A：关掉
// 方案 B：换成自己的 tracing processor（见官方 tracing 指南）
```

**判断问句：我的数据现在往哪传？** 答不上来就是没处理。

### 🔴 2. 接非 OpenAI 模型要选对路，别默认能力对等

官方给了两类路径，能力差别很大：

| 路径 | 怎么接 | 代价 |
|---|---|---|
| **AI SDK 适配器**（推荐） | `@openai/agents-extensions/ai-sdk` + 装对应 `@ai-sdk/*` provider 包 | 覆盖最广，维护最好 |
| OpenAI 兼容端点 | 设 `baseURL` / `apiKey` | 只适用于真的兼容 OpenAI 协议的服务 |

适配器函数名是**全小写 `aisdk`**（不是 `aiSdk`、不是 `createAiSdkModel`）：

```ts
import { aisdk } from '@openai/agents-extensions/ai-sdk';
import { anthropic } from '@ai-sdk/anthropic';   // 换成你要的 provider 包

const agent = new Agent({ name: 'X', model: aisdk(anthropic('...')) });
```

**必须知道的能力落差**：Responses API 是 OpenAI 模型的一等路径，非 OpenAI 模型走 Chat Completions，**部分功能直接没有**（如 `toolSearchTool()` 的延迟加载工具）。另外结构化输出、流式工具调用在不同 provider 上表现不一致。

**别写"换个模型名就行"的代码**——换 provider 是要改配置 + 验能力的。

### 🔴 3. `capabilities` 是**替换**不是追加

这条最容易中招，属于沙箱部分但危害大，提前放这：

```ts
// ❌ 你以为是"加一个 skills 能力"
capabilities: [skills({ ... })]
// 实际：默认的 filesystem() / shell() / compaction() 全没了，agent 突然不会读写文件

// ✅ 正确
capabilities: [...Capabilities.default(), skills({ ... })]
```

默认值 `Capabilities.default()` 含 `filesystem()`、`shell()`、`compaction()`。传了自己的数组就整个替换。详见 `sandbox-agents.md`。

### 🔴 4. 敏感数据日志**默认是关的**（2026-07 改的）

调试时看不到请求/响应内容，不是 bug，是默认行为。要看得显式打开：

```ts
import { setSensitiveDataLoggingEnabled } from '@openai/agents';
setSensitiveDataLoggingEnabled(true);   // 只在本地调试开，别带上生产
```

同理，tracing 里也有 `traceIncludeSensitiveData` 控制敏感数据入不入 trace。

**判断问句：我是在"没记录"还是在"没发生"？** 分不清就先把日志打开再看。

### 🟡 5. zod 是 4，不是 3

peerDependency 写死 `zod ^4.0.0`。训练数据里大量是 zod 3 的写法，直接抄会在 schema 定义处炸。写 tool 参数前先确认项目里的 zod 版本。

### 🟡 6. Windows 上没有本地沙箱

`UnixLocalSandboxClient` 顾名思义只支持 macOS / Linux。**Windows 必须用 `DockerSandboxClient` 或托管沙箱**，且要先装好 Docker。

### 🟡 7. 新能力 Python 先行、TS 后跟

2026-04 那批大改（沙箱、子 agent、Codex 式文件工具）是 Python 版先落地，TypeScript 版随后跟进，且沙箱在 TS 侧仍标 **beta**。**遇到"官方说有但 TS 里找不到"的 API，先怀疑是版本差，去仓库 CHANGELOG 确认，别硬造。**

### 🔴 8. 中文 agent 名会把 handoff 工具名抹成 `transfer_to_____`

名字里非 `[a-zA-Z0-9]` 全换成 `_`，两个中文名专家会撞名，默认只 warn 不报错。agent 名用 ASCII 或 `handoff(agent, { toolNameOverride })`。详见 `对话式应用.md` 决策一。

### 🟡 9. `StreamedRunResult<…>` / `RunState<…>` 的泛型别"写宽点显得通用"

四组盲测三组撞同一个 tsc 错：`TContext` 在这些类型上是**不变**的——不传 context 时 `run()` 推出来的是 `undefined`，你把参数标成 `<unknown, …>` 就报 `ProcessedResponse<undefined> is not assignable to ProcessedResponse<unknown>`；第二个参数写 `Agent<…, 'text'>` 也不满足 `Agent<…, AgentOutputType>`。要么老实写 `<undefined, any>`，要么让编译器推：

```ts
function startRun(input: AgentInputItem[] | RunState<undefined, typeof agent>) {
  return run(agent, input, { stream: true });
}
type ChatStream = Awaited<ReturnType<typeof startRun>>;   // 参数类型用这个，别自己拼
```

### 附：生产层文档的 Python → TS 差异（读 `生产层-经验总结.md` 前看这个）

那份的底座是 Python 版 `openai-agents`，三处已核实的差异（其余对不上时以实测为准）：

1. **§2"裁剪回调深拷贝会污染真源"——TS 版同样中招，症状不同**（本机实测 `live-deepcopy.ts`，0.16.1，三场景各 3 轮）：`sessionInputCallback` 里深拷贝改写旧工具结果，被改的条目会被 SDK 当"新条目"**重复追加入库**——同一 callId 的结果原文 + 占位文并存、条目 4→9→13 超线性膨胀，且原文还在（裁剪目的落空）。与 Python 版差异：**没有立刻 400**（Responses 链路容忍重复），但历史矛盾照样发生。**"正确做法是原地改"在 TS 版同样成立**（实测原地改三轮库零污染）。另：`callModelInputFilter` 里深拷贝改**安全**（历史不被重写），但它连**当轮工具循环中间的结果**也会裁掉——用它做裁剪必须留保护窗，别裁最近的。
2. **§1"缓存断点要手动声明"**——那是走多厂商网关 / Chat Completions 的玩法；TS 版直连 OpenAI Responses API 是自动前缀缓存，这节只在接非 OpenAI 模型（🔴2 那条路）时才相关。
3. **§7"docstring 缩进陷阱"**——Python 特有；TS 版参数说明是 zod `.describe()`，缩进坑不存在，但"参数说明是独立通道、可以不动工具说明单独 A/B"这个思想通用。

---

## 三、写完必须自检（不依赖你会不会）

上面所有"你会 / 你不会"的判断都可能出错。**这一节是兜底：不管你会不会，都能机械地查出来。**

### 第一道：类型检查

```bash
npx tsc --noEmit
```

这一步能抓出**绝大多数写错**：API 名不存在、参数结构不对、事件名拼错、枚举值不合法。TypeScript 的类型定义是跟着 SDK 版本走的，**它比你的记忆新**。

举个真实例子：`raw_model_stream_event` 的 `data.type` 只有四个合法值，你写第五个，tsc 会直接告诉你 `'xxx' 和 '"model" | "output_text_delta" | "response_done" | "response_started"' 没有重叠`。

**看到零输出别急着信** —— 先确认 tsconfig 的 `include` 真的匹配到了你的文件（故意写错一行，看它报不报错，报了再信）。

### 第二道：拿不准签名时去哪查

按可靠度排序：

| 查法 | 什么时候用 |
|---|---|
| **本地类型定义** `node_modules/@openai/agents/dist/index.d.ts` | 最准，跟你装的版本完全一致。搜符号名即可 |
| 官方 [API Reference](https://openai.github.io/openai-agents-js/)（左侧导航） | 要看完整参数表和说明 |
| 仓库 `examples/` 目录 | 要看真实用法组合，比文档片段可信 |

**别猜签名。** 这个 SDK 每月都在加 API，猜错的概率比你想的高。

### 第三道：真跑一次

类型对 ≠ 行为对。类型检查过不了的它会报，**过了但行为不对的它不会说**——比如 tracing 默默往 OpenAI 传数据、`capabilities` 把默认能力覆盖掉了、沙箱改动没回到宿主机。

这几样都得真跑才看得出。**判断成败要看工具的原始返回值，不看 agent 自己怎么说**（怎么看见 `事件流对接.md`）。

---

## 四、去哪查

**官方文档**（TS 版）<https://openai.github.io/openai-agents-js/>　·　**Python 版** <https://openai.github.io/openai-agents-python/>

常用直达：

| 主题 | 链接 |
|---|---|
| Agent 配置 / 动态指令 / 生命周期钩子 | [guides/agents](https://openai.github.io/openai-agents-js/guides/agents/) |
| Runner 循环 / 错误恢复 | [guides/running-agents](https://openai.github.io/openai-agents-js/guides/running-agents/) |
| 六类工具（hosted / 函数 / agent-as-tool / MCP…） | [guides/tools](https://openai.github.io/openai-agents-js/guides/tools/) |
| 模型选择 / 自定义 provider | [guides/models](https://openai.github.io/openai-agents-js/guides/models/) |
| 流式事件 | [guides/streaming](https://openai.github.io/openai-agents-js/guides/streaming/) |
| 沙箱概念全解 | [sandbox-agents/concepts](https://openai.github.io/openai-agents-js/guides/sandbox-agents/concepts/) |
| AI SDK 适配器 | [extensions/ai-sdk](https://openai.github.io/openai-agents-js/extensions/ai-sdk/) |

**什么时候该去查原文**：本文档只覆盖判断和陷阱，**具体 API 签名、完整参数列表、边界值一律去官方**——那些东西会随版本变，写在这里就是给你埋雷。

**仓库里的示例是好东西**：`examples/` 目录下有可跑的完整例子，比文档片段更可信。找不到用法时优先翻那里。
