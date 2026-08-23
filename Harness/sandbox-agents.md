# 沙箱 Agent（SandboxAgent）

> 从 `agent-sdk.md` 路由过来的深水区。**这套能力 2026-04 才有，你的训练数据里几乎没有，别凭印象写。**
>
> **来源**：<https://openai.github.io/openai-agents-js/guides/sandbox-agents/> ＋ 仓库 `examples/docs/sandbox-agents/`
> **核对于 2026-08-18**，`@openai/agents` 0.16.1。**TS 侧仍标 beta**，API、默认值、能力支持都可能变。

---

## 先判断：你真的需要沙箱吗

| 情况 | 用什么 |
|---|---|
| 不需要碰文件、没有活的文件系统 | **普通 `Agent`**，别上沙箱 |
| 只是偶尔要执行一条命令 | 普通 `Agent` + hosted shell 工具 |
| **工作区边界本身就是功能的一部分** | `SandboxAgent` |

适合沙箱的活：改代码并跑测试、处理整批文档、基于文件做审阅、给每个子 agent 独立工作区、跨轮次接着上次的工作干。

**判断问句：如果没有持久工作区，这个需求还成立吗？** 成立就别上沙箱——它带来的概念量不小。

---

## 四层结构

写之前先建立坐标系，这四样各管一件事：

| 零件 | 管什么 | 回答的问题 |
|---|---|---|
| `SandboxAgent` | agent 定义 | 这个 agent 干什么，哪些默认值跟着它走 |
| `Manifest` | 新会话的工作区内容 | 开跑时文件系统上该有什么 |
| `Capability` | 沙箱原生行为 | 挂哪些工具、指令片段、运行时行为 |
| `sandbox` 运行参数 | 每次运行的后端和会话来源 | 这次运行是新建、注入还是恢复会话 |

**官方推荐的设计顺序**：① 用 `Manifest` 定义工作区 → ② 用 `SandboxAgent` 定义 agent → ③ 加 capabilities → ④ 在 `run()` 或 `new Runner()` 里决定这次运行怎么拿到沙箱会话。

---

## 最小可跑

```ts
import { run } from '@openai/agents';
import { Capabilities, Manifest, SandboxAgent, localDir, skills } from '@openai/agents/sandbox';
import { UnixLocalSandboxClient, localDirLazySkillSource } from '@openai/agents/sandbox/local';

const manifest = new Manifest({
  entries: { repo: localDir({ src: hostRepoDir }) },
});

const agent = new SandboxAgent({
  name: 'Sandbox engineer',
  instructions: '改文件前先读 repo/task.md。apply_patch 的路径相对工作区根目录。',
  defaultManifest: manifest,
  capabilities: [
    ...Capabilities.default(),        // ← 这个展开不能省，见下方 🔴
    skills({ lazyFrom: localDirLazySkillSource({ src: hostSkillsDir }) }),
  ],
});

const result = await run(agent, '读 repo/task.md，修掉问题，跑针对性测试，总结改动', {
  sandbox: { client: new UnixLocalSandboxClient() },
});
```

### 🔴 沙箱是隔离的：改动**不会**回到宿主机

`localDir()` / `localFile()` 是把宿主机文件**物化进沙箱**，**单向**。agent 在沙箱里改完文件，宿主机上的源文件**原封不动**——`Manifest` 定义的是"新会话的起始内容"，不是双向同步。

**实测**：让 agent 修 `sandbox-repo/calc.js` 的 bug，沙箱内改成功、`node test.js` 输出 PASS，宿主机上的 `calc.js` 一个字符没变。

**看到"agent 说改好了但我的文件没变"，先别当成 bug**，这是设计如此。要把结果拿出来，用 `sandbox.snapshot`（`SnapshotSpec` 负责把工作区内容持久化并在下次恢复），或让 agent 通过挂载（`s3Mount()` 等）写到外部存储。

**判断问句：这次运行的产物，我打算怎么拿出来？** 答不上来就是还没设计完。

---

## Capabilities（能力）

| Capability | 什么时候加 | 给什么工具 |
|---|---|---|
| `filesystem()` | 要编辑文件、看图 | `apply_patch`、`view_image` |
| `shell()` | 要执行命令 | `exec_command`（客户端支持 PTY 时还有 `write_stdin`） |
| `skills()` | 要在沙箱里发现和装载 skill | 比手动挂 `.agents/skills` 目录更该用这个 |
| `memory()` | 后续运行要读/写记忆产物 | **依赖 `shell()`**；要实时更新还需 `filesystem()` |
| `compaction()` | 长流程要裁剪上下文 | 调整采样与输入处理 |

### 🔴 `capabilities` 是替换，不是追加

```ts
capabilities: [skills({...})]                          // ❌ filesystem/shell/compaction 全没了
capabilities: [...Capabilities.default(), skills({...})] // ✅
```

`Capabilities.default()` = `filesystem()` + `shell()` + `compaction()`。一旦你传了自己的数组，**整个默认列表被替换掉**，不是合并。中招的表现是 agent 突然"不会"读写文件了，而且不报错。

### compaction 的默认阈值

`compaction()` 默认用 `DynamicCompactionPolicy`：认识的模型按上下文窗口的 **90%** 触发压缩；模型未知则回退到 **240,000 tokens**。要改就传 `new DynamicCompactionPolicy(比例, 回退阈值)`，或用 `new StaticCompactionPolicy(固定阈值)`。

压缩产物是**不可读的模型状态**，不是给人看的摘要——**原样传下去，别改它**。

---

## Manifest（工作区）

| 条目类型 | 用于 |
|---|---|
| `file()` / `dir()` | 小的合成输入、辅助文件、输出目录 |
| `localFile()` / `localDir()` | 把宿主机的文件/目录物化进沙箱 |
| `gitRepo()` | 拉一个仓库进工作区 |
| `s3Mount()` / `gcsMount()` / `r2Mount()` / `azureBlobMount()` / `s3FilesMount()` | 挂外部存储 |

### 🔴 环境变量默认会被持久化

Manifest 里的环境变量**默认跟沙箱状态一起存下来**。API key、access token 这类短期凭据必须显式标记：

```ts
{ value: '...', ephemeral: true }   // 不随状态保存
```

需要在物化/恢复时重新查的密钥，继承 `EnvValueReference` 并用 `registerEnvValueReference()` 注册——它只持久化非密钥的查找元数据，运行时通过 `resolve()` 拿当前值。

**判断问句：这个值被存进快照后泄露了要紧吗？** 要紧就加 `ephemeral`。

### 🟡 路径规则（几乎人人踩一次）

- Manifest 条目路径**必须相对工作区**，不能是绝对路径，不能用 `..` 逃逸
- `localFile()` / `localDir()` 的**源路径必须待在 source base 目录内**（默认是 Node 进程的 cwd）。要用别的绝对路径，加**最小必要**的 `Manifest.extraPathGrants`
- 只读输入（共享 skills、数据集、参考仓库）优先 `readOnly: true`
- 本地惰性 skill 发现同理：`localDirLazySkillSource()` 指向 source base 外面时会被**静默忽略**，除非 manifest 授权了那个目录

---

## 选沙箱客户端

| 目标 | 用哪个 | 前提 |
|---|---|---|
| macOS / Linux 上最快本地迭代 | `UnixLocalSandboxClient` | 无额外依赖 |
| 要容器隔离，或指定镜像 | `DockerSandboxClient` | Docker CLI **且 daemon 在跑**（见下） |
| 托管执行 / 接近生产的隔离 | 七家托管客户端之一 | 见 `@openai/agents-extensions/sandbox/*` |

**切客户端不用改 agent 定义**，只换 `sandbox.client` 就行——这是这套设计做得好的地方。

### 🟡 Docker 默认镜像是 `python:3.14-slim`，里面没有 node

不指定 `image` 就用这个默认值（源码 `DEFAULT_DOCKER_IMAGE`）。**实测踩到**：让 agent 跑 `node test.js`，它老实回报 `bash: node: command not found`。

```ts
new DockerSandboxClient({ image: 'node:22-slim' })   // 按你的技术栈选
```

镜像里没有的东西 agent 就是用不了（`git` 同理，slim 镜像通常不带）。**选镜像时先想清楚 agent 要跑什么命令。**

### 🟡 光装 Docker CLI 不够，daemon 必须在跑

官方文档写的是"本地有 Docker CLI"，**实测不准**：SDK 的检查要求 CLI **和** daemon 都可用，Docker Desktop 没启动时直接抛

```
UserError: Docker sandbox execution requires a working Docker CLI and daemon.
```

**坑在于 `docker --version` 会正常返回版本号**（它只查 CLI 不连 daemon），让人以为环境没问题。**要验证得用 `docker info` 或 `docker ps`** —— 连不上 daemon 时它们会报命名管道找不到。

### 平台与网络的硬约束

- **Windows 没有 `UnixLocalSandboxClient`**，必须 Docker 或托管
- `UnixLocalSandboxClient` 要求宿主路径和沙箱路径**完全相同**，所以路径授权里**不要写 `hostPath`**
- `DockerSandboxClient` 支持独立 `hostPath`，但**只能在创建容器时定**，容器跑起来就改不了。Windows 上 `hostPath` 必须带盘符，**不支持 UNC 和设备路径**
- Docker 默认走 Docker 的默认网络。要断网设 `networkMode: 'none'`，但**不能和 `exposedPorts` 同时用**——SDK 会在创建/恢复容器前直接拒绝。目前不支持其他 `networkMode` 值

---

## 排查：看到这条报错先别下结论

```
Failed to execute apply_patch operation: object
```

**实测三轮，两轮出现这条，但任务照样完成了**（文件真改了，`node test.js` 真跑出 PASS）。

两个原因让它极具误导性：

1. **信息量为零** —— 末尾那个 `object` 是没序列化好的错误对象，等于什么都没说。
2. **它是间歇性的** —— apply_patch 偶尔会失败（多半是 diff 上下文没匹配上），但**模型会自己重试**，下一次就成功了。日志留在那，结果其实是好的。

**判断成败别看这条日志，看这两个地方**：

| 看哪 | 成功的样子 |
|---|---|
| `apply_patch_call_output` 的 `status` | `completed`（真失败时这里是 `failed`，源码 `toolExecution.ts` 的 catch 分支会改它） |
| 事件项的 `executionStatus` | `executed` |

拿这两个字段最直接的办法是流式跑一遍、打印 `run_item_stream_event` 的 `item`——**工具的原始返回值是事实，agent 的自述不是**。具体接法见 `事件流对接.md`。

---

## 跨轮次接着干

三种恢复方式，别搞混：

| 方式 | 干什么 |
|---|---|
| `sandbox.session` | 注入一个已有的活会话 |
| `sandbox.sessionState` | 从你自己序列化保存的沙箱状态恢复 |
| `sandbox.snapshot` | 用保存的工作区内容**新建**一个会话 |

另外 `RunState` 里带沙箱负载，走 runner 管理的续跑流程时会自动带上。

**注意**：如果持久化的 `RunState` 里有环境变量引用，恢复时需要一份**当前可信的 manifest**且含对应的 reference 条目，否则 SDK 会在恢复会话前直接拒绝。

---

## 还需要什么

- `runAs` 决定模型可见工具（shell、读文件、打补丁）以哪个沙箱用户身份执行；`Permissions` 决定那个用户能读写执行哪些文件。**两者是两件事，别混**
- `view_image` 支持 PNG / JPEG / GIF / WebP / BMP / TIFF / SVG，上限 10 MB。SDK 按**文件签名**判断格式而非扩展名，所以改后缀骗不过去
- 用 `tty: true` 的交互式 PTY 会话时，宿主进程需要 `python3`（或设 `OPENAI_AGENTS_PYTHON`）

完整参数表和边界值去官方 [concepts 页](https://openai.github.io/openai-agents-js/guides/sandbox-agents/concepts/)——**那些会随版本变，抄进本文档就是埋雷。**
