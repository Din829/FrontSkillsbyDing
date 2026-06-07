# 设计系统库（73 个品牌的现成 DESIGN.md）

> 本目录是 [`前端skills/`](../../README.md) 下 [`参考资料/`](../README.md) 里的「现成设计系统」子库。73 个真实大牌的设计系统，
> 每个一份 `DESIGN.md`，**即拿即用**——不用自己扒真站、不用归类。

来源：[VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md)（MIT，见 `LICENSE`）。
只复制了 `DESIGN.md`，剔掉了原仓库每个品牌指向 getdesign.md 的引流空壳 README。

## 这是什么 / 怎么用

每个 `design-md/<品牌>/DESIGN.md` 是一份完整的设计系统文档：**YAML（颜色/字体/圆角/间距/组件 token）+ Markdown（设计哲学、Do's & Don'ts、给 AI 的提示词速查）**。

两种用法，对应总入口 README 里的两种意图：

| 你在干什么 | 怎么用这个库 |
|---|---|
| **做原创界面，要找参考定调** | 翻 2-3 个气质接近的品牌，**消化「它为什么好」，别照搬色值/布局**（[`frontend-design-pro.md`](../../frontend-design-pro.md) 第二节铁律：直接照搬 = 同质化） |
| **要做某品牌风格 / 用它的设计语言** | 直接把对应 `DESIGN.md` 丢进项目，告诉 AI「照这个建页面」，AI 生成视觉一致的 UI |

> ⚠️ 即便是"照某品牌风格"，落地仍守 pro 的魂：**UI 不撒谎、把复杂藏后台、数据用真实契约画**。设计系统给的是"皮"，pro 管的是"魂"。

## 和「克隆/提取」流水线的关系（先查这里，别重复造）

这个库的 `DESIGN.md` 和 [`克隆skills-OneClickClone/extract-design-system.md`](../../克隆skills-OneClickClone/extract-design-system.md) **提取真站后产出的格式同构**。所以：

- **要某品牌、这里有现成的 → 直接用**，别再跑一遍 extract-tokens 扒真站（DRY）。
- **这里没有的品牌 / 要最新的真站状态 → 走克隆流水线提取**，产出同样结构的 DESIGN.md。

一句话：**这里是「别人提取好的」，克隆流水线是「自己现扒的」，先查这里。**

## 73 个品牌速查（按类型）

- **AI / LLM 平台**：claude、cohere、minimax、mistral.ai、x.ai、together.ai、replicate、runwayml、elevenlabs、ollama、composio、lovable、voltagent
- **开发者工具 / 平台**：cursor、warp、raycast、vercel、framer、webflow、expo、supabase、sentry、posthog、mintlify、clickhouse、mongodb、hashicorp、opencode.ai、sanity、resend
- **SaaS / 协作 / 生产力**：linear.app、notion、figma、miro、airtable、slack、intercom、zapier、cal、superhuman、clay
- **金融 / 加密 / 支付**：stripe、coinbase、binance、kraken、revolut、wise、mastercard
- **电商 / 出行 / 消费**：shopify、airbnb、uber、nike、starbucks、spotify、pinterest、playstation
- **汽车**：tesla、ferrari、lamborghini、bugatti、bmw、bmw-m、renault
- **大厂 / 综合科技**：apple、meta、ibm、hp、dell-1996、nvidia、vodafone
- **媒体**：theverge、wired

> 特殊条目：`dell-1996` 是 1990 年代真实网站提取的复古怀旧系列，做 retro 风格时翻它。

## DESIGN.md 长什么样（结构速览）

```yaml
colors:
  primary: "#5e6ad2"        # 命名色板
typography:
  display-xl: { fontFamily: Linear Display, fontSize: 80px, fontWeight: 600, letterSpacing: -3.0px }
rounded / spacing: ...       # 命名 token（4px → 96px）
components:
  button-primary:            # 组件用 token 引用拼，不写死值
    backgroundColor: "{colors.primary}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
```
下面 Markdown 正文有：Overview（设计哲学）、各维度详解、**Do's and Don'ts（禁区）**、Responsive、**Agent Prompt Guide（给 AI 的速查 + 提示词模板）**。

## 维护 / 扩展

- 想更新到最新（原仓库一直在加品牌）：去 `参考项目/awesome-design-md/` 跑 `git pull`，再把新增品牌的 `DESIGN.md` 复制过来（只复制 DESIGN.md，跳过引流 README）。
- 想加自己提取的品牌：用克隆流水线产出 DESIGN.md，放进 `design-md/<品牌>/` 即可，格式一致。

> **TODO（待办，不急）**：这个库的 DESIGN.md 比我们 `extract-design-system.md` 的 10 段格式多了几样好东西——`Do's and Don'ts`（禁区清单）、字体精确到 OpenType feature、`Agent Prompt Guide`（提示词模板）。以后可参考它反哺 extract-design-system 的产出格式。
