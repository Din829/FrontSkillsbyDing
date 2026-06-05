# 前端复刻 / 设计提取工具集

> 本目录是 [`前端skills/`](../README.md) 的「克隆 + 设计系统提取」子集。整体前端 skills
> 导航见上层 README；本文件只管克隆/提取这一套的细节。

无 MCP、纯 Playwright（node + playwright，三系统通用）。一句话定位：**脚本扒真相，判断交给 AI/人**。

## 按任务找文件

### 任务 A：克隆一个网页（像素级重建成代码）
1. 读 **`site-clone.md`** — 主方法论（5 阶段、23 反模式）
2. 读 **`实战补丁-无MCP的Playwright路径.md`** — 必读：无 MCP 落地路径 + 6 条治"脑补"铁律 + Windows 坑
3. 用 **`clone-kit.cjs`** 扒料（进站/截图/dump CSS/下资产/实测/对比），用法见 **`clone-kit用法.md`**
4. 收尾想做原站 vs 克隆并排对比图 → **`showcase.md`**

### 任务 B：从网站/代码提取可迁移的设计系统（token + 风格 + 资产）
1. 扒原料：
   - 有网址 → **`extract-tokens.cjs <url>`**（computed 真值，最准）
   - 只有代码 → **`extract-from-code.cjs <file|dir>`**（静态解析，不起浏览器）
   - 图标 → **`extract-icons.cjs <url>`**（内联 svg / svg-img / 字体图标识别库）
2. 归类：读 **`extract-design-system.md`**（AI 指令），把原料套 open-design schema，产出
   `design-systems/<slug>/`（tokens.css + DESIGN.md + components.html + assets/）
3. 校验：**`gen-components-manifest.cjs <dir>`** 查"无未声明 token 引用 + 零裸 hex"

### 任务 D：没有参考站，但想要参考图（生成精美网页设计图喂给实现 AI）
- **`gen-refs.cjs "<设计意图>" --sections hero,features,…`** —— 让 GPT-image-2（默认）/ Nano Banana
  生成网页设计参考图。**默认每区块一张**（别憋单张长图，否则文字糊、AI 提取不出来）。
- `--design-system design-systems/<brand>` —— 有现成设计系统就注入，生成的图带该品牌的色/字/组件/气质，
  多区块自然风格统一（continuity）。
- `--ref shot.png` —— 有真站截图当视觉锚点出变体；没有就纯文生成。
- **软指示哲学**（学 AIPowerPoint）：prompt 只给「事实」——设计系统 + 内容 + 区块 + 输出格式，
  具体设计/排版/艺术化交给图像模型，不堆"禁止 XX"的硬禁令。
- 比例：两后端都出真 16:9 宽屏网页比例（gpt-image-2 接受任意尺寸，landscape=1920×1088；gemini=16:9）。
- **配 key**：环境变量 `OPENAI_API_KEY`/`GEMINI_API_KEY` 优先，或在跑命令的目录放 `.env`（范本见 `.env.example`）。哪台电脑都靠这两处之一，不写死路径。
- **想让生图每次不一样**（防千篇一律）：从 `生图设计-精华笔记.md` 的「组合变化引擎」各维度选一个，拼进 `<设计意图>` 传给 gen-refs（不要写进脚本 prompt——那会变回硬指示）。
- 流程：`有参考站 → clone-kit shot 截图`；`没有 → gen-refs 生成` → 都能当实现 AI 的视觉蓝本。

### 任务 C：只想查某条经验 / 工具用法
- 克隆踩坑铁律、工具清单 → `实战补丁-无MCP的Playwright路径.md`
- clone-kit 命令速查 → `clone-kit用法.md`
- 设计系统归类规则（颜色看面积、圆角分组件…） → `extract-design-system.md`

## 文件一览

| 文件 | 类型 | 作用 |
|---|---|---|
| `site-clone.md` | 方法论 | 网站克隆主流程 |
| `实战补丁-无MCP的Playwright路径.md` | 方法论 | 无 MCP 路径 + 铁律 + 工具登记（**克隆必读**） |
| `showcase.md` | 方法论 | 原站 vs 克隆并排对比页 |
| `clone-kit.cjs` | 脚本 | 克隆通用 CLI：probe/dump/assets/fetch/measure/shot |
| `clone-kit用法.md` | 文档 | clone-kit 用法 |
| `extract-tokens.cjs` | 脚本 | URL 扒设计 token 真值（含组件采样） |
| `extract-from-code.cjs` | 脚本 | 代码扒 token（不起浏览器） |
| `extract-icons.cjs` | 脚本 | 图标全抽 + 识别图标库来源 |
| `gen-components-manifest.cjs` | 脚本 | 组件/token 一致性校验 |
| `gen-refs.cjs` | 脚本 | 无参考站时，GPT-image-2/Nano Banana 生成网页设计参考图（分区块、可带参考图出变体） |
| `.env.example` | 配置 | gen-refs 的 API key 范本（复制成 `.env` 填 key；或设环境变量） |
| `extract-design-system.md` | AI 指令 | 原料 → 设计系统（归类判断规则） |
| `生图设计-精华笔记.md` | 笔记 | taste-skill 提炼：组合变化引擎（防生图千篇一律）+ 已吸收清单 |

## 共同原则

- **脚本扒候选、AI 做判断**：会变/需拿捏的不写死（颜色角色、组件圆角、图标语义都交 AI）。
- **先 dump 再写，不肉眼估**：每个值实测、可追溯。
- **不重复造轮子**：设计系统格式套 [open-design](../../../副项目-和Dinreact区分/AIPowerPoint/参考项目/open-design) 的 schema，配色科学调它的 color-expert；我们只做它没有的"从真站提取"。
