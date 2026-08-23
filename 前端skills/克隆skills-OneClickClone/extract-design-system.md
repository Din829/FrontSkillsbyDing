---
name: extract-design-system
description: 把提取原料归类成一套符合 open-design schema 的可迁移设计系统（tokens.css + DESIGN.md + components.html）。原料来自 extract-tokens（URL）/ extract-from-code（代码）；脚本抓瞎的站（canvas/登录墙/重噪声）退回看截图写。脚本扒原料，本指令教 AI 做归类判断。
---

# 从真值原料归类出设计系统

> **动手提取前先查一眼**：要的这个品牌，[`../参考资料/设计系统库/`](../参考资料/设计系统库/) 73 个里有没有现成的 `DESIGN.md`（格式和本指令产出的同构）？**有就直接用，别重复扒**（DRY）。只有"库里没有"或"要最新真站状态"才往下走提取流水线。

你拿到一份 `tokens.source.json`（由 `extract-tokens.cjs` 或 `extract-from-code.cjs` 产出），
要把它归类成一套 **open-design 格式**的设计系统。**脚本只扒了原料，归类的判断由你做**——
这正是机器做不好、需要你拿捏的部分。

## 输入可能是两种来源（看 `_meta.source`）

- **URL 来源**（extract-tokens）：有 `bgByArea`（背景色按面积）、`textByChars`（文字色按字符数）、
  `accentHints`、`radiusByRole`、`buttonSamples`、`shadows`。**最准**，computed 值。
- **代码来源**（extract-from-code）：有 `colorsByFreq`、`fontSizes`、`radii`、`tailwindClasses`。
  **无面积信息**，颜色角色更靠你从用途+频次推断；Tailwind preset class（rounded-lg 等）尺度要你换算。
- **图标**（extract-icons → `icons.json`）：内联 svg 清单、svg-img、**字体图标库识别**（哪套库+用了哪些名）。
- **组件证据**（extract-tokens → `source/snippets/components.snippets.json`）：按钮/卡片/输入的
  真实 outerHTML + computed。**这是核对表，不是成品**——你据此重写干净组件。

## 脚本抓瞎时的 fallback：看截图写（和 open-design 同路）

extract-tokens 靠真实 DOM + computed。**有些站脚本会抓瞎或失真**，此时不要硬用脏数据：

- **canvas / WebGL / 重 SPA**（图画在 canvas 里，DOM 无真实样式）→ computed 抓不到。
- **登录墙 / 强反爬**（Playwright 进不去）→ 没原料。
- **重噪声站**（电商商品流、媒体广告位）→ 颜色频次/面积统计被污染，accent 可能选错。

**fallback**：退回 open-design 的人肉做法——**用 `clone-kit.cjs shot` 截几张图（多视口/多区块），
你直接看图 + 读可见文字，凭判断写 DESIGN.md 和 tokens.css**。这正是 open-design 全部 138 个
设计系统的产出方式（它们都是看着品牌手写的散文，没有机器提取）。

判断原则：
- **能信脚本就信**（有 DOM、噪声低）：computed 是客观真值，比肉眼准。
- **脚本可疑就看图**（数据反常、accent 选出广告色、字号阶全是分数 px）：以截图为准，脚本数据降级为参考。
- **混合最佳**：脚本抓到的干净部分（如字体栈、间距）照用，被污染的部分（如 accent）看图定。
- fallback 产出**没有 source/ 证据层的频次数据**，但 evidence.md 仍要写"此值来自截图判断，非脚本实测"——诚实标注来源，别假装有数据。

## 产出（一个 `design-systems/<slug>/` 目录）

| 文件 | 内容 |
|---|---|
| `manifest.json` | 套 od-design-system-project/v1（见下「manifest 合规」） |
| `tokens.css` | `:root{}` 全部 token，每个值带注释说明取证 |
| `DESIGN.md` | 10 段设计语言（见下「DESIGN.md 结构」） |
| `components.html` | 用 token 搭的组件示例，零裸 hex |
| `source/` | 把 tokens.source.json + 你的 evidence.md 放进去 |
| `assets/` | logo/字体等品牌资产（若有） |

token schema 槽位（约 50 个）见 open-design 的 `_schema/tokens.schema.ts`。

**硬规则：A1 + A2 + B-slot 全部必须在 `:root{}` 里显式写出，一个都不能省。**
原因：artifact 是把单个品牌的 `:root` 块直接粘进一个 `<style>`，没有全局 stylesheet 兜底。
漏一个 B-slot/A2，组件里 `var(--fg-2)` 就解析成空、规则静默失效。
- **A2 扒不到 → 用 `_schema/defaults.css` 的默认值写进 :root**（"用默认"=写出默认值，不是省略）。
- **B-slot 无更丰富层级 → 写 alias**（如 `--fg-2: var(--fg);`），仍要显式写这一行。
- **C 扩展**（品牌特有，如 `--accent-link`）登记到该品牌名下，跨品牌组件不引用。

**别造垃圾 token**（open-design AGENTS.md 明确）：组件内部一次性值、能用 `color-mix(...)`
表达的、纯推测"以后可能要"的——**不要新建 token**，内联在组件里即可。schema 每多一个名，
所有品牌都要跟着声明。

下面是**归类的判断规则**，每条都是踩坑换来的。

---

## 归类规则（核心——这些是 AI 该做的判断）

### 1. 颜色：分角色，不是按频次堆
- **`--accent`（品牌主色）看「大面积色块」，不看「谁最亮」。** URL 来源用 `bgByArea` 排名靠前
  的非中性色；代码来源结合 `colorsByFreq` + 用途（出现在大容器 bg 的）。
  > KPMG 教训：页面上交互蓝 #1E49E2 更亮更显眼，但品牌主色其实是大面积的藏青蓝 #00338D。
- **区分「品牌色」和「交互色」**：按钮/链接的颜色（`accentHints` 里 text: 前缀、buttonSamples 的 bg）
  往往是独立的「交互色」，单独绑 `--accent-link`（C 扩展），别和品牌色合并。
- `--bg` = 面积最大的中性色（通常白）；`--surface` = 第二大（浅灰/卡片底）。
- `--fg` 系列：`textByChars` 排名 = 文字色阶。最多的是 `--fg`，依次 `--fg-2` / `--muted`。
  注意主文字常不是纯黑（KPMG 是藏青 #0c233c）——照实记，这是调性。
- 强调色 ≤2 视觉用量是 schema 硬规则，DESIGN.md 里点明。

### 2. 圆角：**按组件类别分别归类，绝不全站一个值**
- 看 `radiusByRole`（已分桶）+ **`buttonSamples` 的 borderRadius（最可靠）**。
- 典型分化：卡片/图片 0px 或小圆角（`--radius-card`），按钮/CTA 大圆角胶囊（`--radius-button`），
  标签/搜索框 pill。**「方容器 + 圆按钮」这种对比本身就是品牌特征**，别抹平成一个数。
  > KPMG 教训：全站 0px 最多（卡片），但按钮是 32px。按频次取会错判成「近直角品牌」。
  > `radiusByRole.button` 可能被手风琴/列表项污染——**以 buttonSamples 里真正 CTA 的值为准**。

### 3. 字号：22+ 档实测 → 归并成 8 阶
- `typeScale`（URL）或 `fontSizes`（代码）会有很多档，含分数 px（13.008/21.92——是 rem/缩放残留）。
- **丢弃分数档，取整到规则档**，归并到 `--text-xs…4xl` 8 阶。
- 找「出现最多」的那档当 `--text-base` 正文基线（KPMG 是 18px，出现 215 次——比 16px web 常态大）。
- 行高/字距照实记（KPMG 正文 lh 32px ≈ 1.78，偏松，是调性）。

### 4. 间距：高频值对齐 4/8 基数
- `spacing` 高频值通常天然落在 4/8/12/16/24/32/48。映射 `--space-*`。
- 区块级大间距（如 88px）→ `--section-y-desktop`。

### 5. 阴影：分静态 vs hover
- `shadows` 里若有值，判断是静态还是 hover（hover 常是单个、较大模糊）。
- 很多企业站静态扁平、hover 才浮起。`--elev-raised` 取 hover 那个的近似。**别写「不靠投影」这种绝对话**
  除非真的一个阴影都没有。

### 6. 字体：display / body 分栈
- `fonts.display`（h1/h2 computed）→ `--font-display`；body → `--font-body`。
- 注意 fallback：computed 的 `"Times New Roman"` 往往是 webfont 没加载的 fallback，**别当真**——
  看 fontLinks / fontFamilies 找真实字体（如 Open Sans / Noto Sans JP）。

### 7. A2 槽位：扒不到就用 schema 默认，别硬造
- semantic（success/warn/danger）、motion、focus-ring——站上没出现就用 `_schema/defaults.css` 默认。
- `--text-4xl` 等若站上没那么大的字，可外推一档给 display 场景，**注释标明是外推**。

### 8. 需要配色变体/对比度时 → 调 color-expert
- 要生成 `--accent-hover`/`--accent-active`，简单情况用 schema 的 color-mix 默认公式即可。
- 要严谨的 OKLCH 配色、对比度校验、明暗变体 → **调 open-design 的 `color-expert` skill**，别自己写色彩科学。

---

## DESIGN.md 结构（10 段，仿 apple 样板深度）

1. Visual Theme & Atmosphere（+ Key Characteristics 列表）
2. Color（每色标 token 名 + hex + 角色）
3. Typography（字阶表：角色/size/weight/lh/用途）
4. Components（**按钮规格必写**：bg/圆角/字号/padding；卡片；其它）
5. Spacing & Layout
6. Shape, Border & Elevation（圆角分级、边框、阴影静态vs hover）
7. Motion
8. Responsive Behavior（多视口断点表——URL 来源可多扒几个视口补）
9. Iconography & Imagery
10. Agent Prompt Guide（快速参考 + 示例 prompt + **Known Gaps 诚实标注**）

## manifest 合规（open-design guard 严格白名单）

- `source.type` 只能 `bundled | local | github`——从 URL 提取用 `github` + url 字段最贴近。
- `assetsDir` 只能值 `"assets"`，`previewDir` 只能 `"preview"`。
- `files.{design,tokens}` 固定 `DESIGN.md`/`tokens.css`，components 可选 `components.html`。
- `importMode` 用 `normalized`（我们是归类重整，非逐字搬运）。

## 组件 & 图标 → 干净 components.html（铁律5：源码当参考，不照搬）

`components.html` 是给 AI 的「组件样板」——一个完整可渲染的参考页（仿 apple：hero/features/form
分段），所有组件全程 `var(--token)`。怎么从证据产出它：

1. **读组件证据**（`source/snippets/components.snippets.json`）：拿到按钮/卡片/输入的真实结构 +
   computed。**只当核对表**——混淆 class、压缩 CSS 不照搬，重写成语义清晰的干净 HTML。
2. **每个组件用 token 重建**：颜色/圆角/间距/字号全 `var(--*)`，零裸 hex。圆角按组件分
   （卡片 `--radius-card`、按钮 `--radius-button`）。
3. **图标**（`icons.json`）：
   - 内联 svg → 直接内联进组件（已存 `assets/icons/`）。
   - 字体图标库（Material 等）→ 产出页 `<link>` 同款库，用 `icons.json` 里记录的真实图标名；
     **字体图标不能当 svg 复用**，要么装同款库，要么换内联 svg 替代。
   - 标注 `headIconStylesheets` 确认的库（交叉验证过的更可靠）。
4. **组织成参考页**：`:root` 块粘 tokens.css（第一项），下面分段放组件，每段 `data-od-id`。
5. **生成缓存**：`node gen-components-manifest.cjs design-systems/<slug>` 自动产出
   `components.manifest.json`，并**校验「无未声明引用 + 零裸 hex」**——红色项必须改。

## 验证（不验不算完）

1. tokens.css 用 Grep 核对 schema 必填槽位是否齐（约 50 个 A1+A2+B-slot 全写出）。
2. `gen-components-manifest.cjs` 跑过，`undeclaredReferenced` 为空、裸 hex/字体为 0。
3. **拿 tokens.css 套 components.html / 一个 demo，截图看是否呈现该品牌风**——零裸 hex，全 var(--token)。
   换一份别的 tokens.css 同结构应变成别的品牌，这才证明「可迁移」。
4. evidence.md 记每个关键 token 取自原料哪里（哪个 sample、频次多少）。
