# 前端 skills（本文件给人看：用法 + 维护）

## 怎么用（唯一入口）

**给 agent 只递一样东西：`frontend-design-pro.md` 的文件路径**（Claude Code 里 `@` 引用或写路径均可）。

- pro 开头的「第〇节 按需路由」会在正确时机把 agent 踢到正确文件——写动效前必读 motion-gsap、React 落码前必读 vercel 性能规则、找参考先查设计系统库……你不用管，路由自动完成。
- **必须递"路径"，不能复制粘贴正文**——粘正文 agent 够不着同目录其他文件，整套路由失效。
- 常驻项目更省事的做法：在该项目 CLAUDE.md 加一行「前端任务先读 `<路径>/frontend-design-pro.md` 并服从其路由」。

## 目录

```
前端skills/
│  ┌─ 魂：自写方法论（agent 主动读的，全部被 pro 路由覆盖）
├── README.md                       ← 本文件（给人看）
├── frontend-design-pro.md          ← 唯一入口：功能型界面方法论 + 第〇节路由表
├── frontend-motion-gsap.md         ← 动效实操（GSAP 简约版）
├── vercel-react-best-practices.md  ← React/Next 性能 70 条
├── web-design-guidelines.md        ← UI/可访问性审查（运行时拉 Vercel 最新守则）
├── 克隆skills-OneClickClone/       ← 复刻网站 + 设计系统提取流水线（自带 README）
│
│  ┌─ 料：外部素材（按需下钻，pro 路由指到才读）
└── 参考资料/                       ← 自带 README，子库可插拔
    ├── 设计系统库/                 ← 73 个大牌现成 DESIGN.md
    ├── gsap-skills/                ← GSAP 官方完整原文（8 份 SKILL + 4 套示例）
    ├── react-bits/                 ← 134 个动效 React 组件源码 + 中文索引
    ├── frontend-design.md          ← 存档：官方美学原文（pro 已消化）
    └── design-spells.md            ← 存档：微交互灵感索引（pro 已消化）
```

## 设计原则（为什么长这样）

- **入口唯一**：agent 只认它被递到的文件，所以路由表长在 pro 里，不在这份 README 里。
- **魂 / 料分层**：顶层是消化过的方法论（怎么思考），`参考资料/` 是外部原文和素材（现成弹药）。料不需要存在感，被路由指到才读。
- **pro 管魂（意图 + 数据诚实 + 落地不翻车），克隆/提取管皮（视觉真值有据可查）**。两套的互补：pro 有「数据诚实」，提取有「实测证据」（每个 token 可追溯）。

## 维护 / 扩展

- **加新料库**（如内部 UI 组件仓库）：① `参考资料/` 建目录放料 + 自带 README；② `参考资料/README.md` 表格加一行；③ **pro 第〇节路由表加一行**（这步最关键，没有它 agent 永远看不见）。
- **改路由**：只动 pro 第〇节和正文三个检查点（第二节找参考、第三节动效、第七节落地）。
- **自包含红线**：本文件夹会被整体带走，任何文件不得引用文件夹外的路径；外部素材只能复制进来。
- 外部子库更新：原 repo 在 `参考项目/`（设计系统库 ← VoltAgent/awesome-design-md；gsap-skills ← greensock/gsap-skills；react-bits ← DavidHDev/react-bits），去那边 `git pull` 再同步过来。
