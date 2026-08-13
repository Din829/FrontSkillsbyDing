# 参考资料（外部素材库，按需读取）

> 本目录是 [`前端skills/`](../README.md) 的**外部素材仓库**：从各处拉进来的现成原始资料，按主题分子库。
> 和顶层那几份**自写的精炼方法论**（pro / 简约 gsap / 克隆）分开——**那边是"魂"（怎么思考），这边是"料"（现成弹药，要用时翻）。**

## 怎么用

AI 按需读取：顶层方法论会在该用的地方指向这里的具体子库，不用一次全读。每个子库自带 README 说明。

## 子库一览

| 子库 | 是什么 | 什么时候翻 | 配套的顶层方法论 |
|---|---|---|---|
| **`设计系统库/`** | 73 个大牌现成的 `DESIGN.md`（Apple/Linear/Stripe/Ferrari…） | 要做某品牌风格、或找设计参考定调时 | [`frontend-design-pro.md`](../frontend-design-pro.md) 第二节 + [`克隆skills-OneClickClone/`](../克隆skills-OneClickClone/) |
| **`gsap-skills/`** | GSAP 官方动画 skills **完整原文**（8 份 SKILL.md + 四套可跑示例） | 简约版不够、要某插件/API 的完整配置时（MorphSVG 全选项、Nuxt 懒加载…） | [`frontend-motion-gsap.md`](../frontend-motion-gsap.md)（简约入口/速查） |
| **`react-bits/`** | 134 个动效 React 组件**完整源码**（文字/背景/特效，各 4 种技术栈变体），入口是 [`组件索引-中文.md`](react-bits/组件索引-中文.md) | 想要现成动效组件、别手造时 | [`frontend-design-pro.md`](../frontend-design-pro.md) 第三节 + [`frontend-motion-gsap.md`](../frontend-motion-gsap.md) |
| **`agent相关/`** | agent 交互 UI：agent-tool-progress（工具调用过程展示范式）+ thinking-orbs（9 态 AI 思考指示球，MIT 全源码）+ 灵感区（GPL 项目只留链接），入口是 [`README.md`](agent相关/README.md) | 界面要展示"agent 在思考/干活/调工具"的过程时；**组件选用权在用户，agent 只呈现选项** | [`frontend-design-pro.md`](../frontend-design-pro.md) 第〇节路由 |

## 存档（顶层方法论已消化其精华，一般不用读）

| 文件 | 是什么 |
|---|---|
| [`frontend-design.md`](frontend-design.md) | Anthropic 官方美学 skill 原文（营销页倾向），pro 第三节的美学基座出处 |
| [`design-spells.md`](design-spells.md) | 微交互/"魔法"细节灵感索引（community），pro 第三节已定其取舍立场 |

## 分工原则（重要）

- **顶层方法论 = 入口 + 取舍判断**：先读这些。它们已经按"我们的场景"做过提炼和取舍，告诉你该怎么做、用哪个。
- **本目录 = 全文兜底**：提炼时舍掉的细节都在这里的原文里。简约版讲到某处说"需要时查官方/完整版"，就来这里对应子库翻。

一句话：**先看顶层精炼版上手，要深抠细节再下钻到 `参考资料/` 看全文。**

## 维护 / 扩展

- 每个子库都来自独立外部 repo（设计系统库 ← VoltAgent/awesome-design-md；gsap-skills ← greensock/gsap-skills；react-bits ← DavidHDev/react-bits），原 repo 留在 `参考项目/`，要更新去那边 `git pull` 再同步过来。
- **加新子库**：往本目录新建一个 `<主题>/` 放进去，在上面表格加一行，并**在 `frontend-design-pro.md` 第〇节路由表加一行**（关键——agent 只认 pro 的路由，不看本 README）。完全可插拔。
