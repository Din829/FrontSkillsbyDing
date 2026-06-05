# 前端 skills 总入口

> **先读 [`frontend-design-pro.md`](frontend-design-pro.md)——它是基座方法论。** 读完它，
> 再按下面判断要不要看别的。pro 里也有「配套资源」导航指回这里。

## 按任务找 skill

| 你要做什么 | 读哪个 |
|---|---|
| **原创功能型界面**（B端/工具/数据界面）设计 | **`frontend-design-pro.md`**（主方法论：问对问题→定调→美学→用户视角→Pencil 实操） |
| 创意 / 营销落地页的美学 | `frontend-design.md`（Anthropic 官方，pro 的美学基座出处；营销页主场景） |
| 给界面加微交互 / "魔法"细节 | `design-spells.md`（community；营销页调味，功能型界面克制取用） |
| **复刻一个网页** / 从站里**提取设计系统** | → [`克隆skills-OneClickClone/`](克隆skills-OneClickClone/)（看该目录 README） |
| 写 / 优化 React · Next.js 性能 | `vercel-react-best-practices.md`（Vercel） |
| 审查 UI 代码 / 可访问性 / UX | `web-design-guidelines.md`（Vercel） |

## 三套"做设计"的东西，按意图选主导

pro、克隆、提取看着都"做前端"，但意图不同，别混用——**看意图决定谁主导**：

| 意图 | 主导 | 另两套补位 |
|---|---|---|
| 做原创界面 | **frontend-design-pro** | 克隆/提取只当「找参考」工具：截图、扒真实配色当灵感——**消化，别照搬**（pro 第二节铁律） |
| 要做得像某竞品/参考站 | **克隆 或 提取**（子目录） | pro 当质检：用它反 AI 味清单 + 落地校准查一遍 |
| 用某站的设计语言做新界面 | **两者合流** | 提取出 tokens.css，再用 pro 方法论做新界面套上去 |

## 两个互补点（记住这俩）

- **pro 有「数据诚实」，提取那套没有**：pro 强调用真实数据画、对照后端源码、UI 不撒谎。做真实产品必守。
- **提取那套有「实测证据」，pro 没有**：提取的每个 token 可追溯频次/面积。想要有据可查的视觉真值，用它补。

一句话：**pro 管魂（意图 + 数据诚实 + 落地不翻车），克隆/提取管皮（视觉真值有据可查）。**

## 目录

```
前端skills/
├── README.md                    ← 本文件（总入口）
├── frontend-design-pro.md       ← 必读基座：功能型界面方法论 + Pencil
├── frontend-design.md           ← 官方 frontend-design（营销页美学基座）
├── design-spells.md             ← 微交互细节库
├── vercel-react-best-practices.md  ← React/Next 性能
├── web-design-guidelines.md     ← UI/可访问性审查
└── 克隆skills-OneClickClone/    ← 克隆 + 设计系统提取（含自己的 README）
```
