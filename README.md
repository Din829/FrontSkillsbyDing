# 前端 skills 总入口

> **先读 [`frontend-design-pro.md`](frontend-design-pro.md)——它是基座方法论。** 读完它，
> 再按下面判断要不要看别的。pro 里也有「配套资源」导航指回这里。

## 按任务找 skill

| 你要做什么 | 读哪个 |
|---|---|
| **原创功能型界面**（B端/工具/数据界面）设计 | **`frontend-design-pro.md`**（主方法论：问对问题→定调→美学→用户视角→Pencil 实操） |
| 创意 / 营销落地页的美学 | `frontend-design.md`（Anthropic 官方，pro 的美学基座出处；营销页主场景） |
| 给界面加微交互 / "魔法"细节 | `design-spells.md`（community；营销页调味，功能型界面克制取用） |
| **找设计参考** / 要做**某品牌风格**界面 | → [`参考资料/设计系统库/`](参考资料/设计系统库/)（73 个大牌现成 DESIGN.md，即拿即用；看该目录 README） |
| 写**动效**（滚动驱动 / 载入编排 / React 动画） | `frontend-motion-gsap.md`（GSAP 实操简约版，pro 第三节落地补全）；要深抠细节 → [`参考资料/gsap-skills/`](参考资料/gsap-skills/)（官方完整原文） |
| **复刻一个网页** / 从站里**提取设计系统** | → [`克隆skills-OneClickClone/`](克隆skills-OneClickClone/)（看该目录 README） |
| 写 / 优化 React · Next.js 性能 | `vercel-react-best-practices.md`（Vercel） |
| 审查 UI 代码 / 可访问性 / UX | `web-design-guidelines.md`（Vercel） |

## 三套"做设计"的东西，按意图选主导

pro、克隆、提取看着都"做前端"，但意图不同，别混用——**看意图决定谁主导**：

| 意图 | 主导 | 另几套补位 |
|---|---|---|
| 做原创界面 | **frontend-design-pro** | 找参考时先翻 `参考资料/设计系统库/`（73 个现成）或用克隆/提取扒真站——**消化，别照搬**（pro 第二节铁律） |
| 要做得像某竞品/参考站 | **克隆 或 提取**（子目录） | pro 当质检：用它反 AI 味清单 + 落地校准查一遍 |
| 用某站的设计语言做新界面 | **两者合流** | 设计系统库有现成的直接用；没有就提取出 tokens.css，再用 pro 方法论做新界面套上去 |

> **找参考三选一的顺序**：要做某品牌风格 → 先查 `参考资料/设计系统库/`（有现成最省）→ 没有再走克隆/提取扒真站 → 都不沾边（纯原创）就用 pro 方法论从头定调。

## 动效（GSAP）

两层：先读简约版上手，要深抠再下钻完整版。

- **`frontend-motion-gsap.md`**（简约版/入口）= pro 第三节「动效」的实操补全：pro 给原则（该不该动、克制取用），它给怎么写（滚动驱动 / 载入编排 / React / 性能底线），已按我们场景做过取舍。功能型界面克制用，营销页/滚动叙事是它主场。
- **`参考资料/gsap-skills/`**（完整原文）= 官方 8 份 SKILL.md + 四套可跑示例。简约版没展开的细节（插件全配置、Nuxt 懒加载…）来这里查。

## 两个互补点（记住这俩）

- **pro 有「数据诚实」，提取那套没有**：pro 强调用真实数据画、对照后端源码、UI 不撒谎。做真实产品必守。
- **提取那套有「实测证据」，pro 没有**：提取的每个 token 可追溯频次/面积。想要有据可查的视觉真值，用它补。

一句话：**pro 管魂（意图 + 数据诚实 + 落地不翻车），克隆/提取管皮（视觉真值有据可查）。**

## 目录

```
前端skills/
│
│  ┌─ 自写的精炼方法论（"魂"，先读这些）
├── README.md                    ← 本文件（总入口）
├── frontend-design-pro.md       ← 必读基座：功能型界面方法论 + Pencil
├── frontend-design.md           ← 官方 frontend-design（营销页美学基座）
├── frontend-motion-gsap.md      ← 动效实操简约版（GSAP，pro 第三节落地补全）
├── design-spells.md             ← 微交互细节库
├── vercel-react-best-practices.md  ← React/Next 性能
├── web-design-guidelines.md     ← UI/可访问性审查
├── 克隆skills-OneClickClone/    ← 克隆 + 设计系统提取（含自己的 README）
│
│  ┌─ 外部素材仓库（"料"，按需下钻）
└── 参考资料/                    ← 外部拉进来的现成资料，按主题分子库（含自己的 README）
    ├── 设计系统库/              ← 73 个大牌现成 DESIGN.md
    └── gsap-skills/             ← GSAP 官方完整原文（8 份 SKILL + 四套示例）
```
