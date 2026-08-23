# Azure 企业级架构 Skill

> Agent 在 Azure 上设计/审查企业级架构时的参考。
> 原则：先决策定档 → 模块化读章节 → 按档位取舍 → 避反模式 → 自检通过。
> **不写死**：所有配置项标有适用档位 / 场景，Agent 按项目实际情况判断。
> **常见语境**：日本企业咨询项目较多，§16 收集日本相关的额外考虑因素，跨境项目可跳过。
>
> **章节模块化**：
> - §0 Landing Zone — 多订阅 / 多团队时参考
> - §1-10 通用十层 — 所有项目都该过一遍
> - §11 AI 工作负载附加 — AI / LLM 项目参考
> - §12+ 反模式 / 档位 / 自检 — 设计完参考
> - §16 日本运营 / 日本客户项目的额外考虑 — 项目在日时参考

---

## 0. Landing Zone（订阅级前置，多团队/多订阅时读）

**何时要看本节**：组织有 ≥3 个 Azure 订阅、多团队共用、计划长期扩张。**单订阅 / PoC 跳过**。

**核心原则**：把"平台基础"和"工作负载"在订阅级分开，平台团队管网络/身份/合规，应用团队只管自己的 landing zone。

### 决策点

| 问题 | 选 A | 选 B |
|---|---|---|
| 网络拓扑 | **Hub-Spoke**：1-2 region，简单 | **Virtual WAN**：3+ region 或全球用户、18 个月内确定要扩 → 直接选 vWAN（避免后期翻倍迁移） |
| 订阅结构 | 单订阅（PoC / 小项目） | **Management Group + Platform/Application 分离**（Platform: Connectivity/Identity/Management；Application: 各应用各 RG/订阅；Sandbox: 单独 MG 放宽 policy） |
| 模块来源 | 自己写 Bicep / Terraform | **Azure Verified Modules (AVM)**：Microsoft 官方 WAF-aligned 模块库，pin 版本用（见 §06） |

### 必备组件（多订阅项目）

- **Management Group 层级**：按 workload archetype 分（不是按组织结构），便于策略继承
- **Platform 订阅**：放 Hub VNet / Bastion / DNS / Log Analytics 总仓
- **Application 订阅**：每个应用一个，工作负载隔离
- **Azure Policy 继承**：MG 级强制 tag / TLS / 禁公网

**判断依据**：单订阅 / <3 应用 → 跳过本节直接看 §1。否则先定 Landing Zone 再做工作负载。

**官方参考**：CAF Landing Zone design areas（8 areas）— learn.microsoft.com/azure/cloud-adoption-framework/ready/landing-zone/design-areas

---

## 1. 决策树（先定档，再选清单）

设计前先回答 8 个问题，定档后看「§13 场景档位」对应资源集合。

| # | 问题 | 答案影响 |
|---|---|---|
| 1 | **对内还是对外？** | 对外 → 必须 WAF / 自定义域名 / Comm Services |
| 2 | **多租户？** | 是 → 数据层必须 tenant_id 贯通，PE / Index 分离策略要定 |
| 3 | **SLA 几个 9？** | ≥99.95% → 必须 Zone Redundant + 多副本，可能跨 region |
| 4 | **数据敏感度？** | 高 → 必须 PE + pna=Disabled + disableLocalAuth=true |
| 5 | **月预算量级？** | <$500=PoC / $500-3000=标准 / >$3000=企业 |
| 6 | **是否 AI / LLM 工作负载？** | 是 → 加读 §11（Foundry / APIM AI Gateway / Content Safety / GenAI 观测 / PTU 成本） |
| 7 | **是否受监管行业**（金融 / 医疗 / 政府）？ | 是 → 全档位上拉一档；强制 PIM / NSP / Defender CSPM AI / 完整 Diagnostic Settings / 合规 Policy 集 |
| 8 | **运营 / 客户在日本？** | 是 → 参考 §16（Region 选择 / APPI 等法规 / 日语本地化等因素） |

**判档输出**：PoC / 标准 / 企业（详见 §13）。**Agent 注意：档位是参考，不是硬性框架——可单项升档**（如 PoC 项目但受监管 → 安全部分按企业档做）。

---

## 2. 十层必备清单

每层一句原则 + 关键配置项。配置项是「必须显式设置」的——默认值往往不安全。

### 01 网络隔离

**原则**：内网圈地，公网默认关，出网走固定 IP。

| 资源 | 必备配置 | 为什么 |
|---|---|---|
| VNet | 至少 3 subnet：`app` / `pep`（PE 集中区）/ `data` | 应用 / PE / 数据分离便于 NSG 治理 |
| Private Endpoint | 所有数据系都贴（DB / Storage / KV / Search / AOAI） | 内网解析，不走公网 |
| Private DNS Zone | 每种 PE 一个 Zone（`privatelink.*`），VNet link 必加 | 没 Zone Group → DNS 解析失败 fallback 公网 |
| NAT Gateway | 全 egress subnet 共享一个 PIP | 出网 IP 固定，对方好做白名单 |
| pna (publicNetworkAccess) | **`Disabled`** | 仅贴 PE 不够，公网入口必须显式关 |
| Web/Container App | VNet integration 启用 | 应用→PE 才能走内网 |

**反模式**：贴了 PE 但 `pna=Enabled`（=公网+内网都开，没真锁）。

#### Network Security Perimeter (NSP)（2025 GA，企业 / 受监管档考虑）

**何时用**：PaaS 资源跨账号防数据外泄、多 PaaS 资源统一边界管控。已覆盖 KV / Storage / Log Analytics / App Insights / Event Hubs / Service Bus / AI Search / **AI Foundry**；Preview：AOAI / Cosmos DB / SQL DB。

**怎么用**：先 `Transition` 模式学习现有访问 → 再切 `Enforced`（默认拒绝公网，PE 流量直放）。和 PE + `pna=Disabled` **是叠加关系不是替代**（先 PE 再 NSP）。

**坑**：Sentinel-enabled Log Analytics、Backup 关联 Storage **不支持 NSP**。

#### 拓扑选择决策树

| 场景 | 选 | 理由 |
|---|---|---|
| 单 region、<3 应用 | Hub-Spoke | 简单、便宜 |
| 1-2 region、明确不扩 | Hub-Spoke | 同上 |
| **3+ region 或全球用户 / 18 个月内确定扩** | **Virtual WAN** | 跨区双防火墙翻倍成本，hub-spoke 后期迁 vWAN 痛苦 |

#### Firewall / NSG 分工

- **NSG**：subnet / NIC 级 4 层 ACL，基础必备
- **Azure Firewall Standard**：基础 7 层网关，IP/FQDN allow-list
- **Azure Firewall Premium**：**TLS 检测 / IDPS / URL 过滤**（NSG 替代不了，受监管必备）
- **WAF（Application Gateway / Front Door）**：见 §09，HTTP 层防护

### 02 身份认证

**原则**：能 MI 就 MI，不得不用 key 就走 KV。

| 项 | 必备配置 | 备注 |
|---|---|---|
| UAMI | 应用专用 UAMI + ACR Pull 专用 UAMI 分离 | 角色边界清晰，权限最小化 |
| RBAC | 按"读 / 写 / 管理"分层授权 | 用 Data Contributor 不用 Owner |
| `disableLocalAuth` | **`true`**（AI Search / AOAI / Cosmos / Doc Intelligence） | `null` ≠ `true`，默认是有效 key 路径 |
| ACR `adminEnabled` | **`false`** | admin user 是后门，仅 MI Pull |
| Cosmos data-plane RBAC | 单独配 `00000000-...-002` (Built-in Data Contributor) | control-plane RBAC 看不到，要单独检查 |

**反模式**：`disableLocalAuth=null` 当成已禁用（实际仍允许 key）。

#### 特权访问 / 人类管理员侧（PIM，标准档+ 推荐，企业 / 受监管必备）

**何时要看**：项目有人类管理员能登 Azure portal 改资源时。**纯 CI/CD 部署、无人手动操作**可放宽。

**核心思路**：UAMI 管应用侧 → PIM 管人侧。两个分开。

| 项 | 必备 |
|---|---|
| 高权限角色（Owner / Contributor / KV Administrator / RBAC Administrator） | 设为 **PIM eligible**（用时激活，不常驻） |
| 激活要求 | 绑定 **Conditional Access Authentication Context**：要求 MFA + 合规设备 + phishing-resistant（passkey/FIDO2） |
| 审批 | 高敏感角色激活要审批人 |
| Break-glass 账号 | **2 个**，排除 PIM / CA 策略外，定期演练登录 |
| 日常 RBAC | 低权限（Reader / specific Data role）常驻，高权限按需激活 |

**反模式**：把 Owner 永久给个人 / 没 break-glass 账号 / CA 策略锁死自己。

### 03 密钥管理

**原则**：所有 secret 进 KV，应用见到的只是 env 名字。

| 项 | 必备配置 |
|---|---|
| Key Vault | `enableRbacAuthorization=true` + `pna=Disabled` + `purgeProtection=true` + `softDelete=true` |
| Secret 注入 | Container App `secretRef` / Web App `@Microsoft.KeyVault(...)` 引用，绝不 env 平文 |
| 轮换 | Automation Account + Runbook 定时轮换 Storage key / SPN secret / 应用层 key |
| 权限 | UAMI 拿 `Key Vault Secrets User`（只读），不给 Contributor |

**反模式**：env 写明文 key / 占位符 `APP_SECRET=xxxxxx` 没换 / KV 完全不建。

### 04 数据层

**原则**：选型按读写模式，HA / 备份 / 区冗余必配。

| 场景 | 推荐 | HA 要点 |
|---|---|---|
| 文档/KV 型 | Cosmos DB NoSQL | Zone Redundant 启用、Autoscale RU、Periodic 备份至少 7 天 |
| 关系型 | PostgreSQL Flexible / Azure SQL | `highAvailability=ZoneRedundant`、backup ≥7 天 |
| 对象/文件 | Blob Storage | **`Standard_ZRS` 起步**（LRS 单机房风险）、`allowSharedKeyAccess=false`、Lifecycle 自动 Cool/Archive |
| 检索 | AI Search | Basic 起步、`semantic=standard` 适合查询量大（free 仅 1000q/月）、index 分离策略先定 |
| Cache | Managed Redis | port 10000、`accessKeysAuth=Disabled`（MI 必须）、SKU 至少 Balanced_B1 |
| 队列 | Service Bus | Standard 起步；要 PE 必须 Premium |

**反模式**：Storage LRS 装本番 / DB HA=Disabled / 备份不查保留期。

### 05 应用托管

**原则**：选型按弹性需求 + 团队熟练度。

| 形态 | 适用 | 关键配置 |
|---|---|---|
| **Container Apps** | 云原生、弹性强、KEDA scale | min=2+（单 Pod 不算 HA）、Probe 配齐、VNet integration、ACR Pull 走 UAMI |
| **App Service Linux** | 传统 Web、需要 Slot 蓝绿 | PremiumV3 起、`httpsOnly=true`、`minTlsVersion=1.2`、Slot 至少 stg+prod |
| **Container Apps Jobs** | 批处理 / 定时 | KEDA queue depth / cron trigger |
| **Container Apps SessionPools** | **AI Agent 代码执行 sandbox**（Python / Node / Shell） | `poolManagementType=Dynamic`、`maxConcurrentSessions`（按预期并发）、按语言分 pool |
| **Functions** | 短任务 / event 驱动 | Premium / Flex Consumption，不要 Consumption 在 VNet 内 |

**SessionPool 备注**：LLM 代码解释器 / agent tool 调用 Python 时用，比自前 `exec` + sandbox 安全，比起 K8s 自建 namespace 隔离便宜。

**Serverless GPU**（2025 GA、Container Apps 原生）：scale-to-zero + 秒级计费的 A100/T4，AI 推理 / 微调可以不上 AKS。

#### Container Apps vs AKS Automatic 决策

**默认 Container Apps**（覆盖 80% SaaS / 中规模）。**升 AKS Automatic 的硬触发条件 4 个**，命中任一才升：

1. 需要 **Kubernetes API / CRD / admission controller**（如装 ArgoCD / Istio CRD）
2. 自定义 **CNI / Service Mesh**（Istio / Calico / Linkerd 全功能）
3. **复杂有状态** + 自定义 PV（CSI driver）
4. **DaemonSet 类 sidecar** 模式（每节点一份 agent）

**都没命中 → 不要升 AKS**。AKS Standard 现在基本不再推荐给新项目（用 Automatic）。

**反模式**：App Service Basic/Free 跑 SSE（230s 超时）/ Container Apps min=max=1 当本番 / 代码执行用 `exec()` 没 sandbox / 没需求硬上 AKS。

### 06 部署 / CI-CD

**原则**：环境靠代码生成，发布零停机，密钥不出仓库。

| 项 | 必备 |
|---|---|
| **IaC 工具** | 见下「IaC 选型」 |
| **模块来源** | **Azure Verified Modules (AVM)**：Microsoft 官方 WAF-aligned 模块库，2026 已是 Bicep/Terraform 默认起点 |
| **多环境** | dev / stg / prod 至少三套，各自独立 RG 或 subscription |
| **蓝绿发布** | App Service: Deployment Slot + swap（带流量割合）/ Container Apps: Revision + traffic split（10% 灰度可行） |
| **CI/CD 身份** | GitHub Actions OIDC Federation（Workload Identity），不存 SP secret |
| **镜像仓库** | ACR Standard 起、`adminEnabled=false`、Lifecycle policy 清旧 tag |
| **ACR Webhook**（简易 CD） | push 镜像 → 自动通知 Web App / Container App pull，省 GitHub Actions 调 az。规模小适用，大项目走 GitHub Actions |

#### IaC 选型

| 工具 | 选它当 |
|---|---|
| **azd（Azure Developer CLI）** | ≤10 资源、标准 SaaS 模板、入门快 |
| **Bicep + AVM + Deployment Stacks** | 单 Azure、复杂依赖、生态最齐 |
| **Terraform** | 多云、200+ provider、事实标准 |
| **Pulumi** | 强类型 / 有测试文化的开发团队，C#/Py/Go 写 IaC + 单元测试 |
| ~~ARM template JSON~~ | **已退役**，Microsoft 自己只推 Bicep |

#### Azure Verified Modules (AVM)

`br/public:avm/res/...` registry 拉模块，**pin 版本**（如 `1.0.0`，不用 `latest`），企业内做 curated catalog。比自己写 module 省 30-50% 代码，已对齐 WAF + Landing Zone。

#### Deployment Stacks（Bicep 生产推荐，2024 GA）

> 不是"上层封装"，是"生命周期单位"——一个 stack = 一个应用边界。

| 关键开关 | 推荐值 | 作用 |
|---|---|---|
| `actionOnUnmanage` | `detachAll`（生产）/ `deleteAll`（dev） | 删 stack 时是否真删资源，生产防误删 |
| `denySettings` | `denyWriteAndDelete` 或 `denyDelete` | 自带 deny-assignment，**比 Resource Lock 细粒度**，可在 subscription/MG scope 用 |

**和 Resource Lock 关系**：Deployment Stacks 的 denySettings 更新颖、跟 IaC 绑定。Resource Lock 仍用于"完全脱离 IaC 管理"的关键资源（如 break-glass KV）。

**反模式**：环境手点 / SP secret 进 GitHub secret / 直接发 prod 没 swap / ACR `adminEnabled=true` 让 webhook 走 admin 后门 / 自己写 module 不用 AVM / 用 `az deployment group create` 没用 Stacks 生产部署。

### 07 可观测性

**原则**：日志全集中、按用途拆 Insights、设上限防爆账单。

| 项 | 必备 |
|---|---|
| Log Analytics Workspace | 1 个总仓（或按 env 分），保留 30-90 天 |
| Application Insights | **按用途拆分**：api / worker / frontend / batch 至少各 1 个，噪音不混 |
| **Diagnostic Settings** | 每个数据系都把日志/指标灌进 LAW（**默认不灌**，必须每个资源显式配） |
| **Daily Cap** | LAW 设上限（防 1 个 bug 灌爆账单） |
| 自动检测 | Smart Detection action group 开启 |
| 跟踪标准 | OpenTelemetry / GenAI semconv（AI 应用） |

**最容易漏的点**：Diagnostic Settings **不是默认开**。AOAI / AI Search / Cosmos / Key Vault 这些建好后，必须**每个资源单独配 Diagnostic Settings** 把 audit / metrics 灌到 LAW。否则 App Insights 只看到应用层，看不到数据系内部。**实地观察：成熟项目也常漏配，是企业级最大的隐性盲区**。

#### Diagnostic Settings 漏勾陷阱（AI 项目尤其注意）

IaC 模板常按"Audit + RequestResponse"勾，**漏掉 `Trace`**（细到 SDK 调用，新增类别）：

| 资源 | 必勾 log category |
|---|---|
| AOAI / Foundry | `Audit` + `RequestResponse` + **`Trace`** + `AllMetrics` |
| AI Search | `OperationLogs`（**独立类别**，索引/查询，跟 Audit 分离） + `AllMetrics` |
| Doc Intelligence | `Audit` + `RequestResponse` + `Trace`（同 AOAI） |

**Bicep / Terraform 推荐写法**：用 `categoryGroup: allLogs` 而不是手列 category（防漏勾新增类别）。

#### GenAI 应用观测（AI 项目读 §11，此处只列骨架）

OpenTelemetry GenAI semconv 当前 **Development** 状态（未 GA），但 Azure App Insights `Agents (Preview)` blade 已生产采用。**必埋 attribute**：
- `gen_ai.operation.name`、`gen_ai.provider.name`（Required）
- `gen_ai.request.model` / `gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens` / `gen_ai.response.time_to_first_chunk`（Recommended）
- **cost / safety 走自定义 attribute**（spec 未定义）：`gen_ai.usage.cost_usd` / `gen_ai.safety.triggered`
- 环境变量 `OTEL_SEMCONV_STABILITY_OPT_IN` 开 experimental

**反模式**：所有应用塞 1 个 AppInsights / 数据系没 Diagnostic Settings 自以为有日志 / 没 Daily Cap / Diag 只勾 Audit 漏 Trace / GenAI 没埋 token 用量。

### 08 可用性 / 弹性

**原则**：单点都是炸弹。

| 项 | 必备 |
|---|---|
| 副本数 | API 应用 min ≥ 2 |
| Zone Redundant | 应用 + 数据层全开（Cosmos / Postgres / Storage / Redis 各自有开关） |
| 健康探针 | `/healthz` + liveness + readiness + startup 三种 |
| 跨 region | SLA ≥99.99% 必须，备用 region 至少冷备 |
| 备份 PITR | DB 至少 7 天 PITR，定期恢复演练 |
| **Backup Vault / Recovery Services Vault** | 见下「Vault 二分」 |
| 限流 / 重试 | 外部 API 调用必加 timeout + max_retries |

#### Backup Vault vs Recovery Services Vault（2026 二分）

| 用哪个 | 资源 | 计费模式 | 特性 |
|---|---|---|---|
| **Backup Vault**（新工作负载） | Azure Disks / Blob / PostgreSQL Flexible / **AKS** | **delta 计费**，无 vault storage fee | 快、依赖源资源活着才能恢复；CMK / Immutable / MUA / Enhanced Soft Delete 仅 Vault tier |
| **Recovery Services Vault**（老工作负载） | VM / SQL on VM / ASR (Site Recovery) | vault storage fee，数据搬到 vault | 长期归档、源资源死了也能恢复 |
| **服务内置不进 Vault** | Cosmos DB（continuous/periodic backup）/ Azure SQL（PITR） | — | 用服务自带备份，不归 Vault |

**AKS 备份特殊**：用 Backup Vault，分 **Operational tier**（快照在自带 SA，crash-consistent，4h 最小）+ **Vault tier**（异地、仅 1 RP/天、仅 Azure Disk ≤1TB）。生产推荐组合：4h Operational + 每日 Vault tier + GRS + Cross-Region Restore。

**反模式**：min=max=1 / Storage LRS / DB 单 zone / 没探针 / 重试无限 / **以为 DB PITR 就够了不建 vault**（PITR 只能 7-35 天）/ 把 Disks/Blob/AKS 塞进 RSV（用错 vault）。

### 09 安全 / 合规

**原则**：默认安全，事后审计。

| 项 | 必备 |
|---|---|
| TLS | 全资源 `minimumTlsVersion=1.2`+ |
| WAF + Front Door | **对外公网必备**（见下「WAF 选型」） |
| Defender for Cloud | 见下「Defender 分层」 |
| Activity Log 保留 | 至少 90 天，导出到 LAW |
| NSG | subnet 级别加一层（PE subnet 默认拒入） |
| 应用层认证 | Container Apps EasyAuth / App Service AuthV2，背后接 Entra ID |
| **TLS 证书管理** | **Azure Managed Certificate 优先**（自动续期，免费）/ 第三方 CA（GeoTrust 等）必须监控有效期，过期前 30 天告警 |
| **Resource Lock** | 关键资源（KV / Storage / DB / VNet）加 `CanNotDelete` lock，防误删 |
| **azure Policy** | 订阅级强制 tag / 强制 TLS / 禁公网 storage 等，治理基线 |

#### WAF 选型决策

| 场景 | 选 | 备注 |
|---|---|---|
| 单 region、私有后端 | **Application Gateway WAF v2** | 区域内 7 层防护 + 路由 |
| 多 region / 全球用户 | **Front Door Premium WAF** | 边缘拦截 + 降本（边缘截掉无效流量） |
| 推荐企业组合 | **AFD Premium 边缘 WAF + AppGW v2 区域路由** | 边缘 + 区域双层 |

#### Defender for Cloud 分层

| 档位 | 必开 plan |
|---|---|
| 标准 | `FoundationalCspm` + `Discovery`（Standard tier） |
| 企业 / 受监管 | + **`Defender CSPM`**（生成式 AI 应用 SPM、attack path、AI BOM 跨云发现已 GA；**AI Agents discovery — Foundry Agents / Copilot Studio — 仍 Preview**） |
| AI 项目本番 | + **`Defender for AI Services`**（2025-05 GA，订阅级开关、与 Content Safety Prompt Shields 联动检测 jailbreak / prompt injection / 数据泄露）。仅商业云（Gov / 中国云不可用） |
| Storage / DB / Containers | 按资源敏感度加资源级 Defender plan |

**反模式**：对外服务无 WAF / Activity Log 没导出（默认仅 90 天 portal 可看） / Defender 没开 / **没 Resource Lock 误删全 RG** / 第三方证书过期才发现 / AI 项目本番没开 Defender for AI Services。

### 10 成本控制

**原则**：账单可追溯，超支能告警。

| 项 | 必备 |
|---|---|
| Tag | 每个资源至少打 4 项：`env` / `owner`（邮箱）/ `project` / `created` |
| 治理 tag（企业内）| 额外加 `costcenter` / 内部资源 ID（如咨询公司的 `airid`）/ `role`（资源用途说明）/ `created_by`（创建人邮箱）|
| Azure Policy | 订阅级 "Require tags" 策略强制打 tag，缺 tag 阻断创建 |
| Budget | 按 RG / subscription 设月预算，80% 告警 |
| Lifecycle | Blob 自动转 Cool（30d）/ Archive（365d） |
| Reservation | 稳定负载（VM / SQL / Cosmos throughput）买 1-3y 预付 |
| Autoscale | 应用全开，Cosmos 用 autoscale RU |

**Tag 命名陷阱**：`hidden-link:` 开头的 tag 是 Azure 服务自动建的（如 AppInsights 关联），**别手动删**。

**反模式**：无 tag → 月底分账崩溃 / 无 budget → 出事才知道 / Policy 没配 → tag 规范靠人自觉。

---

## 11. AI 工作负载附加（AI / LLM 项目读）

**何时要看本节**：项目用到 AOAI / Foundry / AI Search / 自建 Agent 平台 / LLM 推理。**非 AI 项目跳过**。

**与 §1-10 关系**：本节是十层之上的**附加层**，不是替代。基础架构仍按 §1-10，本节加 AI 专属决策。

### 11.1 Foundry resource（顶层概念，2026-04 取代 AOAI 三件套）

- 2026-01 Microsoft 正式更名「Microsoft Foundry」（January 2026 Product Terms 生效），资源模型从 `Hub + AOAI + AI Services` 压缩为**单一 Foundry resource + Projects**
- Assistants API → **Responses API**，`api-version` → `/openai/v1/` v1 稳定路由
- SDK 统一到 `azure-ai-projects` 2.x
- AOAI 资源可**原地 upgrade 到 Foundry resource**，保留 endpoint / key / 状态

**何时用**：新项目直接 Foundry resource；既有 AOAI 不强制 upgrade，时机成熟再切。

### 11.2 APIM AI Gateway（标准+ 推荐，多 deployment / 多团队必备）

**何时要用**：1 个 AOAI 多团队共用 / 多 deployment / 需要 chargeback / 防 TPM 竞争 / 想加语义缓存。

**核心策略（policy 名直接抄）**：
- `llm-token-limit` — per-subscription TPM 配额
- `llm-emit-token-metric` — 带 User / Client IP / API 维度的 chargeback 指标
- `llm-semantic-cache-store` / `llm-semantic-cache-lookup` — Azure Managed Redis 语义缓存，**省 token 显著**（检索/摘要型业务尤其值钱）
- `backend load balancer`（round-robin / weighted / priority / session-aware）+ circuit breaker（动态 `Retry-After` 解析）
- `llm-content-safety` — 直接挂 Content Safety，防 prompt injection

**vs 拆账号方案**：APIM 是 2026 事实标准，"chat / embedding 拆 AOAI 账号"是 APIM 出现前的折中——新项目优先 APIM。

**何时不用**：单一 AOAI、单团队、流量小、暂不要 chargeback → 不需要 APIM 复杂度。

### 11.3 Responsible AI / Guardrails（企业基线）

**何时必做**：对外 AI 服务、企业架构评审会问、受监管行业。**内部 PoC 可暂缓但要记入待办**。

| 组件 | 用途 | 状态 |
|---|---|---|
| **Prompt Shields** | direct injection（用户恶意 prompt）+ indirect injection（文档/邮件夹带攻击 payload）检测 | GA |
| **Groundedness detection** | 幻觉检测（输出是否依据 source） | GA |
| **Task Adherence guardrail** | 防 agent 跑偏 | Preview |
| **Protected material detection** | 版权检测 | GA |
| **Content Safety**（基础） | 暴力 / 性 / 仇恨 / 自伤 4 大类 | GA |

**接入方式**：直接挂 APIM `llm-content-safety` policy 最省事。Foundry 也内嵌"Guardrails"。

### 11.4 AOAI 成本优化

| 流量类型 | 选 | 折扣 |
|---|---|---|
| 实时（chat / agent） | PAYG（Standard）或 **PTU Reservation** | PTU 月度 reservation 最高约 60% off / 年度最高约 70% off（按 region / model 用 PTU 计算器实测） |
| 可异步（embedding 批量 / 文档分析 / 夜间任务） | **Batch API**（24h 返回，global standard） | **绝大多数模型 50% off**（少数除外，查 model reference） |
| 盈亏平衡（PTU vs PAYG，GPT-4o） | ≥150-200M tokens/月 → PTU 划算 | — |

**架构建议**：流量分两类——实时走 PTU/PAYG，可异步走 Batch API，可观测埋点分类（用 `gen_ai.request.type` 自定义 attribute）。

### 11.5 AI 专属观测（Diag + GenAI semconv）

- **Diag 必勾**：AOAI / Foundry / DocIntel 要 `Audit` + `RequestResponse` + **`Trace`** + `AllMetrics`；AI Search 要 `OperationLogs` + `AllMetrics`
- **GenAI semconv 埋点**（见 §07）：必埋 model / tokens / TTFC；cost / safety triggers 走自定义 attribute
- **Azure App Insights `Agents (Preview)` blade**：遵循 GenAI semconv 就自动聚合，无论 Agents SDK / Foundry / Copilot Studio / 自建

### 11.6 AI 应用托管选型

| 场景 | 选 |
|---|---|
| Agent 代码执行 sandbox（Python/Node/Shell） | **Container Apps SessionPools** Dynamic pool |
| Agent 编排 + Tool 治理（吃 Microsoft 生态） | **Foundry Agent Service**（1400+ Logic Apps connector / MCP / BYOM、每 agent 独立 Entra identity） |
| Agent 编排（自建 / 开源路线） | OpenAI Agents SDK / LangGraph / 自建在 Container Apps |
| GPU 推理 / 微调 | **Container Apps Serverless GPU**（scale-to-zero A100/T4）→ 大规模生产再升 AKS |

**判断**：自建 vs Foundry Agent Service 看是否吃 Microsoft 生态深度——前者灵活、后者 batteries-included。

### 11.7 AI 检索 / 知识库

- **AI Search**：hybrid (BM25 + vector) + Semantic Ranker + 日语形态素（`ja.microsoft` / `ja.lucene`），企业 `semantic=standard`（付费 reranker，free 仅 1000 q/月）
- **Index 分离 vs 单 index + tenant_id filter**：跨租户检索选后者，物理隔离选前者
- **Doc Intelligence**：表格 / 手写文档解析，文字层 PDF 直接 pypdf 更便宜

### 11.8 AI 安全（与 §09 联动）

- **Defender for AI Services**（订阅级开关，2025-05 GA）：Microsoft 关联 Content Safety Prompt Shields 检测 jailbreak / 数据泄露 / 数据中毒 / 凭据窃取 / 模型滥用
- **Defender CSPM AI Posture**：AI BOM 跨云发现 + attack path + IaC 错配检测
- **NSP for AI**（GA: AI Foundry / Search；Preview: AOAI）：PaaS 边界防数据外泄

---

## 12. 反模式速查（"以为做了其实没做"）

设计完扫一遍，命中即整改。

| # | 反模式 | 检查方式 |
|---|---|---|
| 1 | 贴了 PE 但 `pna=Enabled` | `az xxx show --query publicNetworkAccess` 必须 `Disabled` |
| 2 | `disableLocalAuth=null` 当 true | 必须显式 `true`，null = 未禁用 |
| 3 | ACR `adminEnabled=true` | 必须 `false`，admin user 是后门 |
| 4 | env 写明文 key / 占位符没换 | 抓 `*key*` / `*secret*` / `*password*` env，必须 secretRef |
| 5 | 全 Storage `defaultAction=Allow` | 配 PE 后改 `Deny` + 加 VNet rule |
| 6 | 1 个 AppInsights 装所有应用 | 至少按 api / worker / frontend 拆 |
| 7 | DB / Storage / Redis 单 zone | 本番必须 Zone Redundant |
| 8 | 手点资源没 IaC | Bicep / Terraform 必须有 |
| 9 | min=max=1 当 HA | 副本 ≥2、Zone Redundant |
| 10 | Daily Cap 没设 | 1 个 bug 日志能烧穿月预算 |
| 11 | Diagnostic Settings 缺失 | 各数据系默认不灌 LAW，必须显式配 |
| 12 | KV 没建、secret 散落 env | 集中到 KV + secretRef |
| 13 | 对外服务无 WAF | Front Door Standard+ 必须 |
| 14 | Cosmos data-plane RBAC 漏配 | `az cosmosdb sql role assignment list` 单独查 |
| 15 | 自定义证书没用 Managed Certificate | 自维护证书会过期忘续 |
| 16 | **数据系 Diagnostic Settings 缺失**（最常见的隐性盲区） | `az monitor diagnostic-settings list --resource $ID` 必须非空 |
| 17 | KV / DB / VNet 没 Resource Lock | `az lock list -g $RG` 关键资源必须有 `CanNotDelete` |
| 18 | 关键资源没进 Backup Vault | `az backup vault list` + 检查 protected items |
| 19 | 订阅级没配 tag Policy | `az policy assignment list` 至少有 "Require tags" 类策略 |
| 20 | `hidden-link:` 开头 tag 被人手动删 | 这是 Azure 自动关联标签（如 AppInsights 链接），删了会断关联 |
| 21 | **[企业档]** PaaS 资源没用 NSP 自以为锁了 | KV / Storage / AI 资源跨账号防外泄要 NSP Enforced |
| 22 | **[人类管理员]** Owner / Contributor 永久授权个人 | 用 PIM eligible + CA Authentication Context + 2 个 break-glass |
| 23 | **[AI 项目]** Diag 只勾 Audit + RequestResponse 漏 `Trace` | AOAI / Foundry / DocIntel 三类必勾，推荐 `categoryGroup: allLogs` |
| 24 | **[AI 项目]** GenAI 应用没埋 token / 没埋 cost | `gen_ai.usage.input_tokens` / `output_tokens` 是 Recommended、cost 自定义 attribute |
| 25 | **[AI 项目本番]** AOAI 上线没开 Defender for AI Services | 2025-05 GA 订阅级开关，企业本番准必备 |
| 26 | **[多订阅]** 没 Landing Zone 直接铺资源 | 后期 MG / 拓扑迁移成本高，3+ 应用前先做 §0 |
| 27 | **[Vault 用错]** AKS / Blob 塞进 RSV、VM 塞进 Backup Vault | 见 §08 二分表 |
| 28 | **[受监管]** 没 Azure Firewall Premium 只靠 NSG | NSG 不做 TLS 检测 / IDPS / URL 过滤 |
| 29 | **[IaC]** 自己写 module 不用 AVM | AVM 已对齐 WAF + LZ，比手写省 30-50% |
| 30 | **[IaC]** 生产 `az deployment group create` 没用 Stacks | Stacks 自带 denySettings 防带外手改 + 生命周期管理 |
| 31 | **[日本项目]** 数据系不留意建在了海外 region（portal 默认 region 残留） | 核对 region 是否符合客户数据驻留口径 |
| 32 | **[日本项目]** AOAI deployment 类型没核对路由范围 | Global / Data Zone / Regional Standard 路由不同，受监管客户需明示 |
| 33 | **[日本项目]** 日志保留期默认 30 天没和客户合规口径对齐 | 按客户实际要求（J-SOX / FISC 等）核对 |
| 34 | **[日本项目]** 资源名塞日语字符遇到 API 报错 | 资源名 ASCII，日语放 description / display name |

---

## 13. 场景档位（资源最小集）

**Agent 用法**：档位是参考起点，**可单项升档**：
- AI 项目 → 全档位加读 §11
- 受监管行业（金融 / 医疗 / 政府）→ 安全 / 身份 / 观测部分按上一档做
- 多订阅 / 多团队 → 加做 §0 Landing Zone
- 日本运营 / 日本客户 → 参考 §16（Region / 合规 / 日语 等附加考虑因素）

### 档位 A：PoC / 内部验证（~$200-500/月）

**特征**：用户 <50、可单 region、可容忍偶尔停机、不对外。

**必备**：
- VNet（最简 3 subnet）+ 至少数据系 PE
- UAMI + RBAC（不强求 disableLocalAuth）
- Container Apps Consumption（min=0 / max=3）
- 数据层选 Serverless / Burstable（Cosmos Serverless / Postgres B2s）
- AI Search Free（Skill <1000）/ Standard_LRS Storage
- LAW + AppInsights 1 个 + Daily Cap 1GB
- Tag + Budget

**可省**：Key Vault（用 env，但 secretRef 优先）/ WAF / 多 region / Zone Redundant / Runbook 轮换

### 档位 B：标准生产 / 对内中台（~$1500-3000/月）

**特征**：用户 50-500、单 region 可接受、SLA 99.9%、内部使用。

**必备**：
- 档位 A 全部
- **Key Vault**（pna=Disabled）+ secretRef
- **disableLocalAuth=true**（AI Search / AOAI / Cosmos / KV）
- 应用副本 min≥2 + Probe
- 数据层 Autoscale（Cosmos / SQL）
- **AppInsights 按用途拆**（api / worker / frontend 各 1）
- **Diagnostic Settings 全配**（数据系日志灌 LAW，`categoryGroup: allLogs` 写法）
- **IaC**（azd 或 Bicep + AVM）+ 多环境（dev / stg / prod）+ 生产用 Deployment Stacks
- Automation Runbook（至少 Storage key + 应用层 key 轮换）
- ACR Standard、Lifecycle policy
- **关键资源 Resource Lock 或 Stack denySettings**（KV / 主 Storage / DB）
- **订阅级 Policy**：强制 tag
- **PIM eligible**（高权限角色不常驻）+ 2 个 break-glass

**可省**：跨 region / Front Door / Comm Services / Slot（如内部无蓝绿需求） / Backup Vault（DB PITR 暂可） / NSP / Defender CSPM Premium

### 档位 C：企业级 / 对外 SaaS（~$5000+/月）

**特征**：用户 500+、SLA 99.95%+、对外公网、品牌域名、可能多租户。

**必备**：
- 档位 B 全部
- **VNet 全锁定**：所有数据系 `pna=Disabled`、NSG 细颗粒
- **NSP Enforced**（PaaS 边界防外泄，至少 KV / Storage / AI 资源）
- **Zone Redundant** 全开（应用 + Cosmos + Postgres + Storage ZRS + Redis）
- **跨 region**：备用 region 冷备或热备（AOAI 主备 + Cosmos multi-region write）
- **Front Door Premium WAF + AppGW v2** 推荐组合（边缘 + 区域双层）
- **Azure Firewall Premium**（受监管必备，TLS 检测 / IDPS / URL 过滤）
- **自定义域名 + Managed Certificate**（或第三方 CA + 过期监控）
- **Deployment Slot / Revision traffic split** 蓝绿
- **Azure Communication Services**（邮件 / SMS 验证码）
- **AI Search Standard + semantic=standard**（付费 reranker）
- **Defender CSPM Premium**（AI Posture / attack path / AI BOM 跨云）+ **AI 项目本番加 Defender for AI Services**
- **Landing Zone**（§0）：Management Group + Platform / Application 订阅分离
- **Shared Private Link**（AI Search → AOAI 等服务间内网）
- **Application Gateway / Front Door 入口 + Private Link Service**
- **Backup Vault 用对**（Disks / Blob / Postgres Flex / AKS）+ **RSV 用对**（VM / SQL-in-VM / ASR）
- 监控集成 Grafana / 第三方 SIEM
- **AI 专属**：见 §11（APIM AI Gateway / Content Safety + Prompt Shields / SessionPool / Foundry resource / PTU Reservation + Batch API 分流）

---

## 14. 自检清单（设计完跑一遍）

Agent 出完架构方案，按此清单自检。**带 `[条件]` 的项目按需触发**。

**通用 10 问**（所有项目）：
1. **网络**：所有数据系 PE 贴了，且 `pna=Disabled`？拓扑选对了（单 region Hub-Spoke / 多 region vWAN）？
2. **身份**：所有支持的服务 `disableLocalAuth=true`？UAMI / RBAC 最小权限？
3. **密钥**：所有 secret 在 KV？env 没有明文 key？
4. **数据**：DB / Storage Zone Redundant？备份保留 ≥7 天？关键资源进 **Backup Vault**（用对 Vault 类型）？
5. **应用**：min ≥2？探针配齐？VNet integration？没有"无需求硬上 AKS"？
6. **部署**：IaC 写了（AVM / Stacks 用上了）？多环境分离？蓝绿机制有？
7. **观测**：AppInsights 按用途拆？**每个数据系都配 Diagnostic Settings**（`allLogs` 写法）？Daily Cap 有？
8. **可用性**：单点全消除？跨 region（如档位 C）？
9. **安全**：TLS 1.2+？对外有 WAF？Defender 至少 FoundationalCspm？关键资源有 Resource Lock 或 Stack denySettings？
10. **成本**：Tag 4 项打全？Budget 告警设了？

**条件触发 5 问**：
11. **[AI 项目]** §11 全部考虑了吗？APIM Gateway / Content Safety / Diag 三类必勾 / GenAI 埋点 / PTU vs Batch 分流？
12. **[受监管 / 企业档]** PIM + CA Authentication Context 配了？break-glass 2 个排除 PIM 外？
13. **[企业档 / PaaS 防外泄]** NSP 至少对 KV / Storage / AI 资源开 Enforced？
14. **[多订阅]** §0 Landing Zone 设计完了？Management Group 层级 + Platform/Application 分离？
15. **[对外公网]** 自定义域名用 Managed Cert？第三方 CA 有过期监控？Defender for AI Services 开了（如 AI 项目）？
16. **[日本项目]** Region 选择和数据驻留需求对齐了吗？日语本地化（形态素 / 编码 / 字体）按需考虑了？日志保留期与客户合规口径核对过吗？

---

## 15. 常用 az CLI 自检命令

设计完用这几条查实际状态（不是看 portal 显示）：

```bash
# 网络
az xxx show --query "{pna:publicNetworkAccess,disableLocalAuth:disableLocalAuth}"
az network private-endpoint list -g $RG --query "[].{name:name,state:privateLinkServiceConnections[0].privateLinkServiceConnectionState.status}"

# 身份
az role assignment list --assignee $PRINCIPAL --all
az cosmosdb sql role assignment list --account-name $ACC -g $RG   # data-plane 单独查

# KV
az keyvault show -n $KV --query "{rbac:properties.enableRbacAuthorization,pna:properties.publicNetworkAccess,purge:properties.enablePurgeProtection}"

# 应用副本 / 探针
az containerapp show -n $APP -g $RG --query "{min:properties.template.scale.minReplicas,probes:properties.template.containers[0].probes}"

# 数据层 HA
az cosmosdb show --query "locations[].isZoneRedundant"
az postgres flexible-server show --query "highAvailability.mode"
az storage account show --query "sku.name"   # Standard_ZRS / GRS

# 观测
az monitor diagnostic-settings list --resource $RESOURCE_ID
az monitor log-analytics workspace show --query "workspaceCapping.dailyQuotaGb"
```

---

## 16. 日本运营 / 日本客户项目的额外考虑

**何时参考**：项目用户 / 数据 / 业务主体在日本时，下列维度值得纳入决策。**不是必做清单**，按项目实际取舍。

### 16.1 Region 与数据驻留

要点：Azure 在日本有 **Japan East（东京）** 和 **Japan West（大阪）** 两个 region，互为 Azure paired region。

可能的考虑因素：
- 用户主要在日本时，延迟 + 数据驻留两个理由倾向用 Japan region
- 跨 region 冗余 / DR 时，Japan East ↔ Japan West 是天然配对
- AOAI 的 deployment 类型（Global / Data Zone / Regional Standard）决定流量路由——**Global 可能跨国，Data Zone 限定地理区域，Regional 限定单 region**。受监管项目要核对哪种符合客户合规口径
- 部分模型只在特定 region 可用（如 Claude 在 Sweden Central）。需要时要评估"模型能力 vs 数据出境"的取舍

### 16.2 法规与合规上下文

日本项目可能涉及的法规（agent 按实际项目核对，不是每项都触发）：

| 法规 | 何时相关 |
|---|---|
| 個人情報保護法（APPI） | 处理日本居民个人信息时 |
| マイナンバー法 | 处理マイナンバー / 关联信息时 |
| 金融機関 FISC 安全対策基準 | 金融客户 |
| 三省二ガイドライン | 医疗信息系统 |
| ISMAP | 公共部门 / 政府客户 |
| J-SOX / 電子帳簿保存法 | 上市公司财务系统 / 财务凭据长留存 |

参考：Microsoft 提供 FISC / ISMAP / 三省二 等合规对应资料，咨询交付时可作为依据查询。

### 16.3 日语 / 本地化场景

可能要考虑的点：
- **AI Search 形态素**：日语场景有 `ja.microsoft` / `ja.lucene` 两种 analyzer，特性不同（精度 vs 配额）
- **文本编码**：日本老系统常见 CP932 / Shift-JIS，与 UTF-8 系统对接时要 detect + 转码
- **字体**：Web 前端日语 serif 通常 fallback 到系统已装的明朝（`Shippori Mincho` / `Noto Serif JP` / `Yu Mincho`），看项目设计要求
- **邮件 / SMS**：Azure Communication Services 邮件支持 UTF-8；SMS 日文字符按 2 byte 计长
- **文档解析**：Doc Intelligence 有日语手写专用 model

### 16.4 日本企业项目惯例（参考，非强制）

- **资源命名**：Storage Account / Key Vault / ACR 等基础设施类资源**命名 schema 只接受 `[a-z0-9-]`，不收 Unicode**（schema 硬约束，不是兼容性问题）；Resource Group / Tag value / display name 可放日语
- **多环境分离**：稟議（ringi）审批流程下，dev/stg/prod 分离 + IaC 化便于内部审批演示
- **变更窗口**：本番变更通常避开工作时间 / 月末 / 决算期
- **审计日志保留期**：J-SOX / 内部監査 / FISC 等场景对日志留存期有具体要求（数月到数年不等，按客户合规口径定）
- **責任分界文档**：咨询交付一般要明确云供应商 / 集成商 / 客户的責任共有モデル

### 16.5 容易忽略的点

- 数据系不小心建在海外 region（默认 region 是 portal 上次选的，不一定 Japan）
- AOAI deployment 类型没核对路由范围，受监管客户问起来答不上
- 用海外限定的模型（如 Claude）时，数据出境影响没和客户对齐
- 审计日志保留期按通用 30 天设置，与客户合规要求不符
- 资源名塞日语字符遇到 API 报错

---

## 附：选型决策速记

| 决策点 | 选 A 当 | 选 B 当 |
|---|---|---|
| 应用：App Service vs Container Apps | 传统 Web、需 Slot、团队熟 IIS/Tomcat | 微服务、KEDA scale、云原生 |
| DB：Cosmos vs SQL/Postgres | 文档型、多 region 写、schemaless | 关系型、事务、报表 |
| Cache：Managed Redis vs Cache for Redis | 新项目、要 MI、port 10000 | 已有项目、port 6380 |
| 队列：Service Bus vs Storage Queue | 事务消息、DLQ、PE | 简单队列、超大量、便宜 |
| 检索：AI Search vs Cosmos vector | 全文 + 向量 + 语义、日语 | 仅向量、轻量 |
| 文档解析：Doc Intelligence vs 自前 OCR | 高精度、表格/手写、有预算 | 文字层为主、低成本 |
| LLM：AOAI vs Foundry | 主流 GPT 系、Japan East 优先 | Claude / Llama / 多模型、可能要 Sweden Central |
| LLM：chat 和 embedding 同账号 vs 拆账号 | 小项目、TPM 充足 | 大项目、防 TPM 竞争（embedding 高频会饿死 chat） |
| 检索 index：单 index + tenant filter vs 多 index 分离 | 跨租户检索、租户少（<50） | 物理隔离、租户多、quota 不爆 |
| Code 执行：自前 sandbox vs SessionPools | 简单计算、可信代码 | LLM 生成代码、untrusted、Python/Node/Shell 多语言 |
| 蓝绿：Slot vs Revision traffic split | App Service、Slot 配置切换简单 | Container Apps、版本灰度 10%/90% |
| IaC：azd vs Bicep+AVM | ≤10 资源、标准 SaaS 模板 | 复杂依赖、多 region、单 Azure |
| IaC：Bicep vs Terraform vs Pulumi | 单 Azure → Bicep | 多云 → Terraform；强类型 + 测试 → Pulumi |
| 生命周期管理：Deployment Stacks vs Resource Lock | IaC 管的资源用 Stacks denySettings | 完全脱离 IaC 的关键资源用 Lock |
| CD：ACR Webhook vs GitHub Actions | 小项目、镜像 push 即部署 | 多环境、要 approval / 测试 gate |
| 证书：Managed Certificate vs 第三方 CA | Azure 域名、自动续期 | 公司域名、合规要求特定 CA |
| 应用：Container Apps vs AKS Automatic | 默认 ACA（覆盖 80% 场景） | 命中 4 个硬触发条件（CRD / 自定义 CNI / 复杂 PV / DaemonSet） |
| 拓扑：Hub-Spoke vs Virtual WAN | 1-2 region | 3+ region 或 18 个月内必扩 → 直选 vWAN |
| WAF：AppGW v2 vs Front Door Premium | 单 region | 多 region / 全球；推荐组合 AFD + AppGW |
| 边界：PE + pna=Disabled vs NSP | 基础必备 | PaaS 跨账号防数据外泄 → 叠加 NSP |
| Vault：Backup Vault vs RSV | Disks/Blob/Postgres Flex/AKS | VM/SQL-in-VM/ASR |
| AI 顶层：AOAI vs Foundry resource | 已有 AOAI 不强切 | 新项目直接 Foundry |
| AI Gateway：APIM vs 拆账号 | 单 AOAI / 小流量 | 多团队 / chargeback / 语义缓存 → APIM |
| AI 编排：自建 SDK vs Foundry Agent Service | 灵活、开源路线 | 吃 Microsoft 生态、要 1400+ connector |
| AI 成本：PTU vs PAYG vs Batch | <150M tokens/月用 PAYG | 高量 → PTU Reservation；可异步 → Batch 50% off |
| Region：Japan East/West vs 海外 | 用户 / 数据在日本，延迟 + 驻留 | 全球用户 / 需要海外限定模型 |
| AOAI deployment 类型 | 通用场景用 Global Standard（最经济） | 数据驻留有要求 → 考虑 Data Zone 或 Regional Standard，按客户合规口径选 |
| 海外限定模型（如 Claude on Foundry） | 数据出境可接受 | 数据出境有限制时，评估替代模型 |

---

> Skill 用法：设计前读 §1 定档 → 按档位 §13 拿资源集合 → 用 §2 十层清单展开（AI 项目参考 §11、日本项目参考 §16）→ §12 反模式扫一遍 → §14 自检 → §15 命令验证。多订阅项目参考 §0 Landing Zone。