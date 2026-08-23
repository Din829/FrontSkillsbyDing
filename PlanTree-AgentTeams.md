# PlanTree：基于计划树的 Agent Teams 设计思想

> 一种"轻量、灵活、可靠"兼顾的多 agent 协作范式。
> 取 Claude Code Team 和 Hermes Kanban 之长，避两家之短。

---

## 1. 为什么要做这件事

目前业界两家"正经"的多 agent 系统，各有命门。

**Claude Code Team**（同步密集型）：leader 在主驾，几个 teammate 在副驾结对编程。优势是快、人在环精确到每个 tool call、plan mode 能"先审批方案再动手"。**命门是怕崩** —— teammate 跑在同一个 Node 进程里，一锅端；不擅长跨天累积的长任务。

**Hermes Kanban**（异步可靠型）：任务扔进 SQLite 工单白板，独立 OS 进程当 worker 排队干。优势是稳、可断点续传、人不在场也能跑。**命门是怕慢** —— dispatcher 60 秒一 tick，永远有调度延迟；不适合需要快速来回的协作。

两家各自的架构选择已经把对方的形态锁死了：Claude Code 想要 Kanban 的可靠性，得重写进程模型；Kanban 想要 Claude Code 的响应速度，得砍掉 dispatcher 那层解耦。

**真正的生产级多 agent 系统应该两层叠用** —— 外层 Kanban 管"什么时候干、谁来干、出错怎么办"，内层 Team 管"这一轮里几个 agent 怎么协调"。但叠起来意味着两套心智模型、两套数据结构、两套调试工具，对用户和开发者都不友好。

**PlanTree 的诉求**：用一套统一抽象，把"快"和"稳"做成可切换的开关。

---

## 2. 先理清两家到底怎么做的（重要前置）

### Claude Code 实际上有"两层 agent"

不要混在一起说：

| 层 | 名字 | 寿命 | 嵌套 | 通信 | 典型用途 |
|---|---|---|---|---|---|
| **第一层** | Teammate | 长命（session 级） | **扁平**，teammate 不能再 spawn teammate | mailbox 文件 + 协议消息 | 结对协作的"同事" |
| **第二层** | Subagent | 短命（一次调用） | **可嵌套**，subagent 可继续开 subagent | fork-join 返回值 | 临时跑个调研、扫个代码 |

Claude Code 源码里写得很死：`AgentTool.tsx` 直接抛错 "Teammates cannot spawn other teammates — the team roster is flat"（精确行号随版本漂移，此处不固定）。

这意味着 Claude Code 实际是 **flat team + nested subagent** 的两层混合，不是纯扁平也不是纯树。

### Claude Code 的 team-lead 是固定角色

Team 里有一个特殊成员叫 `team-lead`：
- 创 team 时自动生成（agentId = `team-lead@<team-name>`）
- 是默认收件人（teammate 不知道发给谁时 fallback 给它）
- 是权限审批中心（teammate 的 `permission_request` 走它）
- 是 plan mode 审批方
- 是唯一能 spawn teammate 的角色

**team-lead 一个人扛 4 个职责**，这是 Claude Code 心智模型的核心。

### Hermes Kanban 是 DAG 不是树

task_links 是真正的有向无环图：
- 一个 task 可以有多个 parent（多对多）
- 创建 link 时主动检查环（`_would_cycle` 函数）
- 比纯树灵活，能表达"两个任务都完成才能开始第三个"

### Hermes Swarm 用 comment 当黑板

Hermes 有个 `kanban_swarm.py`，写的固定拓扑：
```
planning root（瞬间完成）
    ├─ parallel workers（并行干活）
    └─ verifier（等所有 worker 完成）
         └─ synthesizer（等 verifier 完成）
```
**共享黑板就是 root task 上的 JSON 格式 comment** —— 没有专门的 context 表，复用 task_comments。

---

## 3. PlanTree 核心思想

### 3.1 一句话本质

**一棵 plan 树就是一个 team。每个节点是一个任务，可以选择"快"或"稳"的方式跑，所有节点共享一份单向流动的视图来决定自己该做什么。**

### 3.2 为什么用树而不用 DAG / 看板

- Kanban 是 DAG，灵活但复杂。多 parent 让"谁是 lead"模糊，调试时画图都难
- Claude Code 是扁平 + 嵌套两层，心智割裂
- **PlanTree 选纯树**，理由有三：
  - 实际工作天然层级（目标 → 项目 → 任务 → 子任务）
  - 父子关系明确，谁是谁的 lead 一目了然
  - DAG 的"多 parent"场景可以用"共同祖先 + 共享 context"替代，不损失表达力

把树当一等公民有几个好处：
- 父节点天然是 leader，子节点天然是 teammate —— 不用固定 `team-lead` 角色
- "谁能看到谁的数据"由树结构决定，不需要点对点路由
- 完成判定有递归定义：所有子节点 done → 父节点可以继续

### 3.3 lead 是结构属性，不是固定角色

这是 PlanTree 和 Claude Code 最重要的差异。

Claude Code：**全局一个 team-lead**，扛所有审批和协调。

PlanTree：**lead 性是相对的** —— 你是谁的父节点，你就是谁的 lead。任意子树都有自己的 lead（子树根节点），不需要全局协调中心。

好处：
- 没有"team-lead 单点瓶颈"
- 子树可以独立运转（局部审批、局部协调）
- 嵌套天然支持（lead 也可以是别人的 worker）

### 3.4 双 Backend：快慢可选

每个 plan 节点声明自己用哪种执行方式：

**inline（快）**
- 同一个进程里 async 函数跑
- 启动 0 延迟、通信走内存、共享父进程的运行时
- 适合：开发调试、需要快速来回的子任务、生命周期短的活
- 代价：进程崩了一锅端、不能跨重启

**detached（稳）**
- 独立 OS 进程跑（或独立容器）
- 通过共享数据库通信、有心跳和 reclaim 机制
- 适合：长任务、不可靠的活（构建、测试、网络爬取）、生产环境
- 代价：启动有延迟、通信序列化开销

**关键**：同一棵 plan 树里的节点**可以混搭**。父节点 inline 快速规划，关键子节点 detached 慢慢跑。这是两家都做不到的灵活性。

### 3.5 共享视图：只读、按需、单向

这是 PlanTree 最核心的设计决策。

**Claude Code 的做法**：teammate 之间互发邮件（包括广播 `to: "*"`），私聊 + 广播为主。mailbox 承载 11 种协议消息（permission、plan_approval、shutdown、idle_notification...），变成万能总线，复杂度爆炸。

**Hermes Kanban 的做法**：所有 worker 共享 SQLite 数据库，但每个 worker 只能看自己 task 的 context。本质是"按 task 隔离的小看板"。swarm 子项目用 root task 的 comment 当黑板。

**PlanTree 的做法**：每个节点行动前，从 plan 树视图拿到**它该看的部分**：
- 自己的任务定义
- 父节点的输出（输入数据）
- 显式声明 reads 的共享 context key

干完后把结果写回去：
- 自己的 output（人读的 summary + 机器读的结构化数据）
- 显式声明 writes 的共享 context key

**单向数据流**，像 React 的 props 往下传 + 子组件 emit 事件往上报。

兄弟节点之间**不直接通信** —— 真要协调走共同父节点。这从设计上杜绝了"广播泛滥"和"两个 worker 互发消息死锁"的可能性。

这样有几个好处：
- 不需要 11 种点对点协议消息
- context 不会变成无限增长的聊天垃圾桶
- 调试时一眼看清"这个节点为什么这么做" —— 看它的输入即可

---

## 4. 最小数据模型

只需要 4 个对象。

### 4.1 Plan

```
{
  id: 唯一标识
  goal: 这个 plan 要解决什么（用户原始诉求）
  root_node_id: 根节点
  context: 共享 key-value 存储（按需读写）
  created_at, updated_at
}
```

一个 plan 对应一次"用户提了个目标"。

### 4.2 Node

```
{
  id: 节点唯一标识
  plan_id: 属于哪个 plan
  parent_id: 父节点（root 节点为 null）
  task: 这个节点要干什么（自然语言描述 + 结构化参数）
  backend: inline | detached
  status: pending | running | done | failed
  reads: ["api_spec", "user_pref"]   ← 声明读哪些共享 context key
  writes: ["test_report"]            ← 声明写哪些共享 context key
  output: { summary, data }          ← done 后填
  error: 失败时的诊断信息
  created_at, started_at, ended_at
}
```

**reads / writes 是契约**：节点跑之前系统会校验，不在 reads 列表里的 key 它读不到（运行时报错），不在 writes 里的 key 它写不了。这避免 plan 跑久了 context 变成"啥都往里塞"的垃圾桶。

### 4.3 Run（每次执行尝试）

```
{
  id, node_id
  attempt: 第几次尝试
  status: running | done | failed | reclaimed
  worker_pid: 如果是 detached，记 PID
  started_at, ended_at
  heartbeat_at: 最近一次心跳
  output, error
}
```

**学 Kanban 的 task_runs 分离设计** —— 一个 node 可能跑多次（失败重试、被回收重跑），每次跑都是独立的 run 行。node 是"逻辑任务"，run 是"物理尝试"。这样重试历史天然保留。

### 4.4 Event

```
{
  id, plan_id, node_id (可选), run_id (可选)
  kind: created | started | done | failed | reclaimed | approval_requested | approval_granted | ...
  payload: 结构化数据
  created_at
}
```

append-only 日志，给观察者用（UI 实时刷新、调试追踪、审计）。**不参与状态机决策**，纯记录。

---

## 5. Approval Gate：可挂任意层级

Claude Code 的 plan mode 是"一个 teammate 干活前给 team-lead 看方案"。Hermes 的人在环是"task 整体 block 等用户 unblock"。**前者过细（每个 Bash 都问），后者过粗（要么完整任务停，要么完整任务跑）**。

PlanTree 把审批做成一个统一概念：**Gate**。Gate 可以挂在三个层级：

**Plan-level gate**：整个 plan 启动前要审批 → "你确定要让 AI 改 50 个文件吗？"

**Node-level gate**：某个 node 启动前要审批 → "data-migration 这个节点风险大，跑之前让我看下方案"

**Tool-level gate**：某个 node 用某个工具时要审批 → "这个 node 调 Bash 要逐条问我"（Claude Code 风格）

**审批方默认是父节点（结构 lead），不是固定的 team-lead**。父节点也可以转交给人（root 节点的 gate 自然就是问用户）。

Gate 触发时：
1. 节点暂停，状态变 `awaiting_approval`
2. 写一条 Event，等审批方
3. 审批方（父节点或人）通过 / 拒绝 / 修改
4. 通过则继续，拒绝则节点 failed，修改则按新参数跑

**关键**：Gate 是节点定义里声明的属性，不是单独的协议消息。所有审批走同一套机制，不像 Claude Code 那样为了不同审批场景搞 6 种协议消息。

---

## 6. 执行流程（一个具体例子）

用户说"帮我把这个 React 项目的状态管理从 Redux 迁移到 Zustand"。

**Step 1：规划阶段（root 节点）**
- 创建 plan，root 节点跑 inline（快速规划，几秒到几十秒）
- root 节点读取代码库，产出 plan 树：
  - 子节点 A：分析现有 Redux 用法（inline）
  - 子节点 B：编写 Zustand 等价实现（detached，慢工出细活）
  - 子节点 C：迁移单元测试（detached）
  - 子节点 D：人工 review 审批 gate
  - 子节点 E：执行批量替换（detached + tool-level gate on Bash）

**Step 2：执行阶段**
- A 立即跑（inline，无延迟），完成后 output 写入共享 context 的 `redux_usage_map`
- B 启动 detached worker，读 `redux_usage_map`，产出 `zustand_impl`
- C 启动 detached worker，读 `redux_usage_map` + `zustand_impl`，产出 `test_diff`
- D 是 gate 节点，等用户点"批准"
- E 等 D 批准后启动，每次 Bash 调用前用户都要点 yes/no

**Step 3：汇总阶段**
- 所有叶子节点 done 后，root 节点 wake up，读取所有子节点的 output
- 产出最终 summary 返回给用户

**整个过程**：用户只需要在 D 节点点一次批准，E 节点跑 Bash 时再点几下。其他时候 agent 自驱。如果中途 detached worker 崩了，dispatcher 自动 reclaim 重跑，不影响其他节点。

---

## 7. 关键设计权衡

### 7.1 不要做的事

**不做的事 1：跨 plan 的 agent 复用**
每个 plan 自己一棵树，节点不跨 plan 共享。这避免了 Kanban "fleet farming" 那种一个 worker 跨多个 task 的复杂状态。要复用就抽成 skill / function，别复用 agent 实例。

**不做的事 2：兄弟节点直接通信**
兄弟节点之间不能互发消息。要协调，要么走共同父节点（父节点把数据从一个子节点 output 转写到另一个子节点的 reads 里），要么走共享 context（带 reads/writes 契约）。这从设计上杜绝了"两个 worker 互发消息陷入死锁"和"广播泛滥"。

**不做的事 3：动态修改已建好的 plan 树**
plan 树一旦开始执行，已建结构不可变。子节点想加新任务，只能创建自己的子节点（往下伸），不能加兄弟（横向扩展）也不能改父节点。这保证了层级关系稳定、可追溯。

**不做的事 4：DAG 多 parent**
一个节点只有一个父节点。需要"等多个东西都完成"用共同父节点解决（父节点等所有子节点 done，再 spawn 下游）。损失一点表达力，换来巨大的心智简化。

### 7.2 必须做的事

**必须 1：reads/writes 契约强制**
节点声明的 reads/writes 必须在运行时强制检查。否则 context 会变成全局变量地狱。

**必须 2：output 必须有 summary + data 两层**
- summary 给人看（dashboard 一眼看完成了啥）
- data 给下游节点机器读（结构化字段）
- 不能只有一个 —— 只有 summary 下游无法精确消费，只有 data 用户看不懂

**必须 3：run 和 node 分离**
node 是逻辑，run 是物理。一个 node 可能有 3 次 run（失败重试）。这样重试历史天然保留，调试时能看到"第二次跑的时候才解决了那个 bug"。

---

## 8. 与两家对照表

| 维度 | Claude Code Team | Hermes Kanban | PlanTree |
|---|---|---|---|
| **核心抽象** | flat teammate + 嵌套 subagent | DAG task 看板 | 纯 plan 树 |
| **进程模型** | 进程内协程 + tmux | 独立 OS 进程 | 节点级混搭（inline / detached） |
| **lead 角色** | 固定 team-lead（4 职责合一） | 无（dispatcher 全干） | 结构属性（父节点即 lead） |
| **共享什么** | 各自邮箱 + team 配置 | SQLite 工单 + comment 黑板 | plan 树视图 + 显式 reads/writes context |
| **通信方式** | 11 种 mailbox 协议消息 + 广播 | comment + metadata + result + events | 单向数据流（父→子输入，子→父输出） |
| **人在环粒度** | tool-call 级（plan mode） | task 级（block/unblock） | 三档可选（plan / node / tool） |
| **崩溃恢复** | 弱 | 强（dispatcher reclaim） | inline 节点弱、detached 节点强 |
| **典型规模** | 几十个 teammate 几分钟 | 几个 worker 几天 | 任意混搭 |
| **心智模型** | "结对编程的副驾 + 临时调研员" | "无人工厂流水线" | "项目经理 + 可选远程团队" |

---

## 9. 适用与不适用

**适合 PlanTree 的场景**：
- 既要快速迭代又要可靠落地（开发期 inline 调试、生产期 detached 跑）
- 任务有清晰的层级结构（可拆解的目标）
- 需要灵活的人在环（有些地方放手让 AI 跑，有些地方要审批）
- 希望调试时能看清"为什么 AI 做了这个决定"（单向数据流好追踪）

**不适合 PlanTree 的场景**：
- 任务天然是平铺的（没有层级，一堆独立小任务）→ 用 Kanban 更合适
- 完全交互式的开发协作（每秒钟都在变方向）→ 用 Claude Code Team 更合适
- 极大规模舰队作业（一个 worker 管 500 个账号）→ Kanban 的 fleet farming 更直接
- 必须 DAG 多 parent 才能表达的复杂依赖 → 用 Kanban

---

## 10. 实现的最小骨架

不是详细设计，只列出"如果要做，至少包含这些模块"：

1. **Plan Store**：SQLite 持久化 plan / node / run / event 四张表
2. **Node Runner**：抽象接口，inline runner 和 detached runner 各一份实现
3. **Context Bag**：按 plan 隔离的 key-value，带 reads/writes 校验
4. **Dispatcher**：扫 pending 节点，根据 backend 选择 runner 启动
5. **Gate Handler**：识别 awaiting_approval 状态，挂到 UI / 通知机制
6. **Event Bus**：append-only 事件流，给 UI 和审计用

整个系统的核心数据流是：**用户提目标 → root 节点规划 → dispatcher 跑节点 → 节点读 context + 父输出 → 写 output → 父节点 wake up → 汇总返回**。

---

## 11. 一句话总结

**PlanTree = 把"层级"做成第一公民，把"快慢"做成可选项，把"共享"做成单向受控数据流，把"lead"做成结构属性而非固定角色。**

学 Claude Code 的"层级心智 + 进程内速度 + 卡点审批"。
学 Kanban 的"SQLite 可靠 + 进程隔离 + run/node 分离 + comment 黑板思路"。
砍掉两家的"过度工程的协议消息、固定的 lead 单点、扁平 + 嵌套割裂的心智、DAG 多 parent 的复杂度"。

不追求像两家那样精密到极致，追求**够用、好懂、能演进**。
