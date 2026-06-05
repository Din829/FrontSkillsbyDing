---
name: site-clone-playwright-patch
description: site-clone 的实战补丁。两个作用：① 不依赖任何浏览器 MCP，用 Playwright 脚本跑通 site-clone 全套动作；② 把实战踩坑换来的硬纪律补成"绕不过去的检查"，治 AI 克隆时"看一眼就脑补重写"的通病。配合 site-clone.md 一起用。
status: 实战验证过(PwC Japan / Accenture Japan), 但只覆盖到"单区块像素级", 整页克隆仍待补
---

# site-clone 实战补丁

> 这份不是替代 site-clone.md，是补它的两个缺口。site-clone 方法论本身是对的，坑出在"没把关键步骤变成强制动作"和"默认要 MCP"。

---

## 缺口一：不需要任何浏览器 MCP

site-clone 原文说"需要 Chrome MCP / Playwright MCP / 类似的"。**实测证明：不用 MCP，Playwright 的 Node 脚本就能跑通全部动作。** 公司电脑首选这条——隔离浏览器、不开调试端口、不碰你的登录态，安全。

### 一次性准备
```bash
# 在工作目录装(浏览器若已下过, 秒装)
npm i playwright
# 没下过浏览器才需要: npx playwright install chromium
```

### site-clone 每个"via browser MCP"动作 → Playwright 一行对照

| site-clone 要求 | Playwright 写法 |
|---|---|
| 打开页面 | `page.goto(url, {waitUntil:'domcontentloaded'})` |
| 点按钮/tab | `await el.click()` |
| 滚动触发懒加载 | `page.evaluate` 里 `window.scrollTo` 循环 |
| hover 取悬停态 | `await el.hover()` 后再读 computed |
| 抽 computed CSS | `page.evaluate(()=> getComputedStyle(el))` |
| 多视口测响应式 | `newContext({viewport:{width,height}})` 切 1440/768/390 |
| 截图 | `page.screenshot({path})` |
| 下载素材 | Node `fetch`（不是 curl，CDN 常拒 curl） |
| **取真实 HTML 源码** | `el.outerHTML` / `page.content()` |
| **取真实 CSS 规则** | 遍历 `document.styleSheets` 匹配 class |
| **取 SVG 真实代码** | `svg.outerHTML` |

> 能力和 MCP 完全一样，脚本反而更高效（一次跑完一整套提取，不来回交互）。

### Windows 中文路径坑（实测踩过）
- **bash 的 `cd` 进中文目录会乱码失败** → 别 cd，脚本里全用绝对路径，从任意目录 `node 绝对路径/x.cjs` 运行
- **Chrome headless 写 png 到中文目录会权限拒（0x5）** → 截图先写临时目录或英文路径
- **`node -e` 里套模板字符串易被 shell 转义搞坏** → 用 Write 工具直接写 `.cjs` 文件，别用 `node -e` 拼长脚本

---

## 缺口二：把"治脑补病"的硬纪律补上

AI 克隆最大的通病：**看一眼截图，就用自己的理解重写一个"差不多的"**。每隔一层"我觉得"，就差一截。下面每条都是实战翻车换来的，做成"绕不过去的检查"。

### 铁律 0：先 dump，再写。不准看截图凭记忆写。
开工第一件事不是写 HTML，是把目标区块的**真实 outerHTML + 真实 computed 值 + 真实 CSS 规则**全 dump 成文件。写代码时这些文件是"真相核对表"，每个数值都去查，不靠肉眼估。
> 翻车实例：标题字号我肉眼估 88px，实测是 100px；padding 估 0/40，实测 60/80。不 dump 永远是错的。

### 铁律 1：素材先判本质，再决定下载还是写代码。
对每个视觉元素，先问一句：**这是图/视频/SVG，还是 CSS 能画的？**
- 是图/视频/SVG → **下载真实素材 / 拉真实代码**，绝不手画
- 是渐变/圆角/阴影等纯 CSS 效果 → 才用 CSS 写
> 翻车实例1：PwC 的橙色斜条，我用 clip-path 手画死活对不上——真相是它**印在底图照片里**，下真图就对了。
> 翻车实例2：Accenture 标题里的紫 〉和 logo，我用文字 `>` 凑，难看且形状不对——它们是**真实 SVG**，拉下来内联就是原版。

### 铁律 2：图标 99% 是 SVG，必拉，不准手画。
现代网站图标几乎都是 `<svg>`（真实矢量代码），不是 CSS 画的。
- 用 `[...document.querySelectorAll('svg')].map(s=>s.outerHTML)` 把所有 SVG 拉出来
- 存成 .svg 文件内联，或转 React 组件
- **手画的图标永远难看、比例不对**——这是相似度的隐形杀手
> 判断技巧：dump 时统计 `svg` 数量，挨个看 viewBox + rect 定位它是哪个图标（logo/搜索/箭头/菜单…）

### 铁律 3：枚举"全部"素材，不准挑。
按 site-clone Stage2 第6步"Discover ALL assets"**强制枚举、逐个下载**，不是"我觉得需要哪几个"。漏图 = 空块 = 一眼假。
> 翻车实例：Accenture 首屏有 12 张真实卡片图，dump 早就列出来了，我视而不见、卡片全做成空灰块，相似度直接掉到 30%。

### 铁律 4：不对比，不算完成。
严格执行 site-clone Stage5（同视口并排对差、回查真值改源头），**这是最常被偷懒跳过的一步**——绝不能截完克隆图就说"做好了"。
> 翻车实例：我跳过对比直接交付，标题差了一倍大小都没发现。

### 铁律 5：源码当参考，重建出干净代码（不照搬混淆码）
能 `page.content()` 拉整页源码，但现代站是**机器生成的混淆 class + 几百KB压缩CSS**（如 Accenture 的 AEM 栅格），照搬跑不起来也没法改。
- **正确姿势**：拉源码当"真相核对表"——拿不准的值去查 hero-source.html / hero-source.css
- **产出**仍是干净可维护的代码，但每个数值可在源码里查证
> 这是"看截图猜"和"查源码定"的根本区别。

---

## 通用提取工具：clone-kit.cjs

不用每次写一次性脚本了——上面所有动作已工程化成一个通用 CLI：**`clone-kit.cjs`**（同目录），只依赖 node + playwright，三系统通用，给个 URL 就跑。

```bash
node clone-kit.cjs <probe|dump|assets|fetch|measure|shot> <url> [options]
```

| 命令 | 对应动作 | 铁律 |
|---|---|---|
| `probe` | 进站+cookie+懒加载+顶层结构+截图 | 起点 |
| `dump` | 区块 DOM树+computed CSS（不传 selector 自动猜 header/hero/footer） | 0 |
| `assets` | 全量资产发现 → 候选 manifest（人删垃圾改名再下） | 3 |
| `fetch` | 按 manifest 下载（Node fetch+Referer，同名加序号） | 3 |
| `measure` | 实测单元素真实样式（`--text` 或 `--selector`） | 0 |
| `shot` | 截任意 URL 供对比 | 4 |

> 详见 **clone-kit用法.md**。设计灵魂：**脚本管「提取真相」，判断（区块怎么拆、图叫什么名）留给人/AI**——不做"一键克隆"，那种换站就崩。
> 已在 KPMG Japan 服务页全命令实测跑通（含 Windows 中文路径、CDN 带 Referer 下载、日文选择器）。

> ⚠️ **改 clone-kit 或写任何 playwright 代码时，对 API/选项/行为没把握就查官方文档（playwright.dev）确认，别靠记忆硬写。** 拿不准的 API 容易写出"看着对、实际静默失败"的代码。

---

## 升级线：从「克隆一个页面」到「提取可迁移的设计系统」

克隆是消费一次性；提取设计系统是沉淀可复用资产——同一套组件换一份 tokens.css 就变品牌。
参照 [open-design](../../../副项目-和Dinreact区分/AIPowerPoint/参考项目/open-design) 的 schema 和文件格式
（它只消费人工写的设计系统，**没有从真站提取的能力——这正是我们补的空白**）。

三件工具（同目录），延续「脚本扒原料、AI 做判断」哲学：

| 工具 | 干什么 |
|---|---|
| `extract-tokens.cjs <url>` | 从 **live URL** 扒 computed 真值：色板(按面积)、字阶、间距、**圆角按组件分桶**、按钮采样、阴影 → `tokens.source.json` |
| `extract-from-code.cjs <file\|dir>` | 从 **代码**（HTML/CSS/JSX/Tailwind）静态解析，不起浏览器 → 同格式 source.json |
| `extract-icons.cjs <url>` | **图标全抽 + 识别来源**：内联 svg 拔代码、svg-img 下载（--download）、字体图标识别哪套库(Material/FA/MDI…)+ 用了哪些名 → `icons.json` + `assets/icons/` |
| `extract-design-system.md` | **归类指令**（AI 读）：把 source.json+icons+组件证据 套 open-design schema，产出 `design-systems/<slug>/`（tokens.css + DESIGN.md + components.html + assets/） |
| `gen-components-manifest.cjs <dir>` | 从 components.html+tokens.css 自动生成 `components.manifest.json`，**校验无未声明 token 引用 + 零裸 hex**（会静默坏的 bug 在这拦） |

流程：`扒原料(URL或代码) → AI 按指令归类 → 产出设计系统`。配色变体/对比度调 open-design 的 `color-expert`，不自造色彩科学。

> **关键判断经验**（已固化进 extract-design-system.md）：
> - 品牌主色看**面积**不看亮度（KPMG 主色是大面积藏青 #00338D，不是更亮的链接蓝）。
> - 圆角**按组件分类**，绝不全站取频次（KPMG 卡片0px/按钮32px、Stripe 卡片0px/按钮4px——"方容器+圆按钮"的对比本身是品牌特征）。按钮圆角**以 buttonSamples 为准**（radiusByRole 会被列表项噪声污染）。
> - 已在 KPMG（藏青/直角）+ Stripe（紫/4px/sohne 字体）两个反差极大的站实测，工具不绑死品牌。

---

## 完成度自检（这才叫"克隆完了"）

- [ ] 铁律0：每个数值都来自 dump/实测，没有一个是肉眼估的
- [ ] 铁律1：每个素材判过本质，图/视频/SVG 都是真实下载，没手画
- [ ] 铁律2：所有图标是拉的真实 SVG，没用文字/CSS 凑
- [ ] 铁律3：全量资产枚举过，逐个下载，无空块
- [ ] 铁律4：和原站同视口并排对比过，差异已回查修正
- [ ] 铁律5：拿不准的值在源码里查证过

> **克隆产物要上线 / 二次开发时，先过"保留红线"**：克隆只复刻视觉，但接进真实产品后，
> 路由/slug、表单字段名、导航文案、品牌 logo、SEO meta、analytics 埋点这些一动就连带打断
> 后端/数据/SEO——**这些绝不能为了视觉随手改**。清单见 [`../frontend-design-pro.md`](../frontend-design-pro.md)
> 第七节"保留红线"，不在这里重复。

---

## ⚠️ 这份补丁还没完，差得多

目前只验证到 **"单区块（Hero）+ 第一屏卡片"的像素级**。site-clone 是要克隆**整页**的，以下还完全没做、待补：

- [ ] **完整导航**：下拉 mega-menu、移动端汉堡菜单、各级菜单内容
- [ ] **所有区块**：Hero 之后的全部 section（不只第一屏）
- [ ] **Footer**：多列链接、版权、社交图标（site-clone 反模式#19 专门强调别忘 footer）
- [ ] **响应式**：768 / 390 两个断点的布局变化（site-clone 要求三视口）
- [ ] **交互逻辑**：tab 切换、轮播、手风琴、modal 的真实行为
- [ ] **滚动驱动动效**：入场动画、视差、sticky header 变化
- [ ] **整页组装**：page 级布局、z-index 层、滚动容器
- [x] **脚本工程化**：~~现在脚本是一次性的~~，已工程化成通用 CLI `clone-kit.cjs`（提取层全覆盖，见上节）
- [ ] **泛用性验证**：目前只测了 PwC/Accenture 两个企业站，需在不同框架/设计体系的站上验证（电商、SaaS、媒体站…）

> 下一步优先级建议：先把"整页"打通（导航+全区块+footer+响应式），再做交互动效，最后工程化成自动工具。
