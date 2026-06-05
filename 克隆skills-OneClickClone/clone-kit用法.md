# clone-kit 用法

`clone-kit.cjs` —— site-clone 的通用提取工具。一个文件，6 个子命令，只依赖 node + playwright，三系统通用。

> **定位**：脚本只管「提取真相」，判断（区块怎么拆、哪张图叫什么名、组件怎么写）留给人/AI。这是 site-clone「先 dump 再写」纪律的工具化，不是"一键克隆"——那种东西换个站就崩。

---

## 一次性准备

```bash
npm i playwright
# 浏览器没下过才需要：npx playwright install chromium
```

工具在任意目录运行，**输出落在当前工作目录**下的 `_clone-<hostname>/`。所以：先 `cd` 到你的克隆项目根目录，再调用工具的绝对路径。

```bash
# 若 playwright 装在别处，用 NODE_PATH 指过去（同一台机器一次设定即可）
export NODE_PATH=/path/to/node_modules        # Windows: $env:NODE_PATH="C:\...\node_modules"
KIT=/path/to/clone-kit.cjs
```

---

## 6 个命令

```
node clone-kit.cjs <command> <url> [options]
```

| 命令 | 干什么 | 产出 |
|---|---|---|
| `probe <url>` | 进站+cookie+滚动懒加载+顶层结构+首屏/全页截图 | `artifacts/topology.json` + `shots/` |
| `dump <url> [--selector S]` | 区块 DOM树+computed CSS 深抽 | `artifacts/section-<名>.json` |
| `assets <url>` | 全量资产发现 → 下载候选表 | `artifacts/assets-raw.json` + `asset-manifest.json` |
| `fetch <url> [--manifest F]` | 按 manifest 下载（Node fetch+Referer） | `public/images/` |
| `measure <url> (--selector S \| --text T)` | 实测单元素真实样式（回查用） | `artifacts/measure-<名>.json` + 打印 |
| `shot <url> [--out F]` | 截任意 URL（克隆站对比用） | `shots/shot-<vw>.png` |

### 通用选项

| 选项 | 默认 | 说明 |
|---|---|---|
| `--vw <n>` / `--vh <n>` | 1440 / 900 | 视口尺寸。多视口对比：`--vw 768`、`--vw 390` |
| `--out <dir\|file>` | 各命令默认 | 覆盖输出位置 |
| `--outdir <dir>` | `_clone-<hostname>` | 覆盖输出根目录 |
| `--locale <s>` | ja-JP | 语言 |
| `--headed` | 关 | 有头模式（调试看浏览器） |
| `--no-consent` | 关 | 不自动点 cookie 同意 |
| `--wait <ms>` | 2500 | 进站后额外等待 |
| `--timeout <ms>` | 60000 | 导航超时 |
| `--depth <n>` | 5 | dump 的 DOM 递归深度 |
| `--viewport` | 关 | （shot/dump 用）只截首屏，不截全页 |

---

## 典型流程（对应 site-clone 各阶段）

```bash
cd my-clone-project   # 输出会落在这里

# 1) 勘察：能不能进、什么结构、首屏长啥样（铁律0 的起点）
node $KIT probe https://target.com/page

# 2) dump 真相：默认抓 header/hero/footer；要别的区块就指定 selector
node $KIT dump https://target.com/page
node $KIT dump https://target.com/page --selector ".hero-section"

# 3) 资产：先发现生成候选表
node $KIT assets https://target.com/page
#    → 打开 asset-manifest.json，删垃圾(广告/重复/powered_by)、给图改语义名(hero-banner.jpg)

# 4) 下载：按改好的 manifest 下（带 Referer，绕 CDN 拒绝）
node $KIT fetch https://target.com/page

# 5) 写代码时回查：拿不准的值实测，别肉眼估（铁律0）
node $KIT measure https://target.com/page --text "監査・保証業務"
node $KIT measure https://target.com/page --selector "h1.title"

# 6) 对比：克隆站起 dev server 后，同视口截图并排对差（铁律4）
node $KIT shot http://localhost:3000/ --vw 1440
node $KIT shot http://localhost:3000/ --vw 390
```

---

## 设计要点（为什么这样而不那样）

- **assets/fetch 两段式**：`assets` 只产「候选表」，命名是从 URL 猜的、还附了 alt/尺寸。**人过一遍删垃圾改名**再 `fetch`。哪张是 hero、叫什么名——这是判断，不交给脚本。
- **选择器全走参数 + 默认兜底**：`dump`/`measure` 不传选择器时用内置猜测（header/含h1的块/footer），要精确就 `--selector`。默认能用、需要时能压死。
- **跨平台**：路径全相对 `cwd` 推导，零写死绝对路径。Windows 中文目录截图权限坑（0x5）已内置规避——截图先写系统临时目录再搬过去。
- **fetch 同名加序号**：manifest 里重名项不会静默覆盖（自动 `logo-2.svg`），人工去重前的保险。

## 已知限制（不是 bug，是边界）

- **`measure` 的 `rect` 仅供参考**：命中包裹文字的 inline/折叠元素时可能是 `0×0`。**样式值（颜色/字号/间距）始终准确**——那才是 measure 的核心用途；要尺寸看 `dump` 的 `rect` 或 `probe` 的 topology。
- **内容结构提取（卡片/列表的文字）不做全自动**：每个站 DOM 和 class 命名都不同，靠通用选择器猜命中率看运气。需要逐条文字时，用 `dump` 抓那个区块的树，人/AI 从树里读——比瞎猜选择器靠谱。
- **只做提取层**：不生成组件、不拆区块、不组装页面。那些是 site-clone 方法论 + 人的活。
