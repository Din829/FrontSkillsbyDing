---
name: frontend-motion-gsap
description: 用 GSAP 给前端写动效的实操方法论（提炼自 GreenSock 官方 gsap-skills 全 8 份）。当要做滚动驱动动画、页面载入编排、React/Vue 动效、或被要求"加动画/微交互"且没指定库时使用。核心：先判断该不该动，再用 transform/opacity 守住 60fps 和无障碍。
---

用中文交流。本文是 [`frontend-design-pro.md`](frontend-design-pro.md) 第三节「动效」的**实操补全**——pro 给原则（该不该动、克制取用），这里给**怎么正确写**。提炼自 GreenSock 官方 [gsap-skills](https://github.com/greensock/gsap-skills)（MIT，8 个 skill 全部通读后取舍）。

> **GSAP 已全部免费**：Webflow 收购后，所有插件（含原 Club 专属的 SplitText/MorphSVG 等）商用免费，`npm install gsap` 即全套，**不要**再生成带 GreenSock auth token 的 `.npmrc`、不要用私有源 `npm.greensock.com`、不要让用户注册 Club——那些是过时信息。

> **本文的取舍**：8 份原文里，**core / timeline / scrolltrigger / react / performance** 是地基，全留并对照 pro 讲透；**plugins / utils** 只留功能型界面和营销页真会用的几个，重创意/游戏的（SVG 变形描边、物理、Pixi…）只给一句索引；**Vue/Svelte** 给精简小节（原则和 React 同构）。**要某个没展开的细节 → 下钻完整原文 [`参考资料/gsap-skills/`](参考资料/gsap-skills/)**（8 份 SKILL.md + 四套可跑示例都在本地），或官方文档。

---

## 零、先问"该不该动"（最重要，别跳过）

动效是放大器，不是默认项。动手前对齐 pro：

- **功能型界面（B端/工具/数据）**：克制。动效只服务于"看清状态变化"，不为炫技。数据/操作密集的界面**宁可不做**。一个让用户分心或卡顿的动画，比没有更糟。
- **营销页 / 创意页 / 有滚动叙事的站**：GSAP 的主场。值得把力气集中在**一次编排好的页面载入** + **滚动驱动的叙事**。
- **底线（任何场景都守）**：只动 `transform`/`opacity`、honor `prefers-reduced-motion`、保证 60fps 不抖。做不到平滑就别做。

**什么时候选 GSAP**：用户要"JS 动画库 / React·Vue 动画 / 滚动驱动动画"又没指定库时，GSAP 是稳妥默认（框架无关、生态全、性能好、内置 ScrollTrigger）。用户已选了别的库就尊重他的选择。**纯 CSS 能干净做到的简单过渡**（hover、单段渐显）就别上 GSAP，CSS 更轻——GSAP 的价值在：序列编排、运行时控制（暂停/反转/跳转）、复杂缓动、滚动驱动、JS 算出来的动态值。

> ⚠️ 写 GSAP 代码时，API/选项拿不准就查官方文档（gsap.com/docs），别凭记忆——容易写出"看着对、静默失败"的代码。

---

## 一、Core：单个动画

```javascript
gsap.to(".box",   { x: 100, duration: 1, ease: "power2.out" });   // 从当前值动到目标值（最常用）
gsap.from(".item",{ opacity: 0, y: 20, stagger: 0.1 });            // 从给定值动到当前值（入场常用）
gsap.fromTo(".box", { opacity: 0 }, { opacity: 1, duration: 0.5 });// 明确起止，不读当前值
gsap.set(".box",  { autoAlpha: 0 });                               // 瞬时设值（duration 0）
```

几个一定要知道的：

- **用 `autoAlpha` 而非 `opacity`**：autoAlpha 在值为 0 时自动设 `visibility:hidden`，元素不占点击、不挡事件；纯 opacity:0 元素还在、会挡住下面的按钮。
- **transform 用 GSAP 别名，别写 raw transform 字符串**：`x`/`y`/`z`(默认 px)、`xPercent`/`yPercent`(按自身百分比，SVG 也能用)、`scale`/`scaleX`/`scaleY`、`rotation`(默认 deg)、`rotationX`/`rotationY`(3D)、`skewX`/`skewY`、`transformOrigin`。别名按固定顺序应用、更快、跨浏览器稳。
- **属性写 camelCase**：`backgroundColor`、`marginTop`，不是 `background-color`。
- **相对值**：`x: "+=20"`、`rotation: "-=30"`，还有 `*=` `/=`。
- **函数式值**（每个元素不同目标）：`x: (i, target, all) => i * 50`，首次渲染时对每个 target 调一次。
- **方向旋转**：旋转值加后缀 `"-170_short"`(最短路径)、`"_cw"`/`"_ccw"`(顺/逆时针)。
- **clearProps**：动画完成后删掉指定 inline 样式（`clearProps: "all"` 或具体属性名），让 CSS class 接管。注意：清任一 transform 相关属性会清掉**整个** transform。
- **能动 CSS 变量**：`{ "--hue": 180 }`。

### stagger（错位）

```javascript
gsap.to(".item", { y: -20, stagger: 0.1 });                        // 每个晚 0.1s
gsap.to(".item", { y: -20, stagger: { amount: 0.3, from: "center" } }); // 总 0.3s，从中间往两边
```
`from` 可选 `"start"/"center"/"end"/"edges"/"random"/(index)`。**一个 tween 配 stagger，别写 N 个带 delay 的 tween**（后者更慢，见性能节）。

### 缓动（ease）

用字符串内置 ease，别瞎编名字：`"power1.out"`(默认手感)、`"power3.inOut"`、`"back.out(1.7)"`(回弹过冲)、`"elastic.out(1, 0.3)"`、`"none"`(线性)。power1→power4 是曲线强度递增。需要自定义曲线才上 CustomEase 插件。

### 页面载入编排 = pro 推荐的"集中一次"

pro 说"把力气集中在一次编排好的页面载入（错位渐显）"。GSAP 做法就是 `from` + `stagger`：

```javascript
gsap.from(".hero > *", { opacity: 0, y: 24, duration: 0.6, stagger: 0.08, ease: "power2.out" });
```

### 控制播放 / 全局默认

返回值存下来才能控制：`const tw = gsap.to(...); tw.pause(); tw.reverse(); tw.progress(0.5); tw.kill();`。
全项目默认：`gsap.defaults({ duration: 0.6, ease: "power2.out" })`。

### immediateRender 的坑（叠 from 时必踩）

`from()`/`fromTo()` 默认 `immediateRender: true`(立即应用起始态，避免闪烁)。**当多个 from/fromTo 动同一元素的同一属性时，后面的要设 `immediateRender: false`**，否则第一个的终态被覆盖、第二个动画看不见。

---

## 二、响应式 + 无障碍：`gsap.matchMedia()`（pro 底线的落地）

honor `prefers-reduced-motion` 和按断点改动画，用一个 API 全包（GSAP 3.11+）。媒体查询不匹配时，这一 run 里建的所有动画和 ScrollTrigger **自动 revert**：

```javascript
const mm = gsap.matchMedia();
mm.add({
  isDesktop:    "(min-width: 800px)",
  isMobile:     "(max-width: 799px)",
  reduceMotion: "(prefers-reduced-motion: reduce)",
}, (ctx) => {
  const { isDesktop, reduceMotion } = ctx.conditions;
  gsap.to(".box", {
    rotation: isDesktop ? 360 : 180,
    duration: reduceMotion ? 0 : 2,    // 用户要求减少动效 → 时长归 0，瞬时到位
  });
  return () => { /* 可选的额外清理 */ };
});
// 卸载时：mm.revert();   ← 杀掉这个 mm 里建的所有动画和 ScrollTrigger
// 第三个参数可传 scope（元素/ref），让 handler 里的选择器只在该根内匹配
```

> 关键：尊重 `prefers-reduced-motion` 是为前庭障碍用户着想，reduceMotion 时 `duration: 0` 或直接跳过动画。**别在 matchMedia 里再嵌 `gsap.context()`**——matchMedia 自己就是 context，清理只用 `mm.revert()`。切换"减少动效"开关后想立即重跑用 `gsap.matchMediaRefresh()`。

---

## 三、Timeline：多步编排

按顺序串、或精确控制每段何时开始。**多步动画用 timeline，别用一堆 delay 串**：

```javascript
const tl = gsap.timeline({ defaults: { duration: 0.5, ease: "power2.out" } });
tl.to(".a", { x: 100 })            // 默认接在上一段之后
  .to(".b", { y: 50 }, "<")        // "<" = 和上一段同时开始
  .to(".c", { opacity: 0 }, "+=0.3")// 上一段结束后再 0.3s
  .addLabel("mid")                  // 加标签，可读、可跳
  .to(".d", { scale: 1.2 }, "mid+=0.2");
```

**位置参数**（第三个参数）三种：绝对时间 `1`(第1秒) / 相对 `"+=0.5"` `"-=0.2"` / 标签 `"mid"`。占位符 `"<"`(与上一段同始)、`">"`(接上一段尾，默认)、`"<0.2"`(上一段开始后 0.2s)。

- `defaults` 让所有子 tween 继承 duration/ease，省重复。
- timeline 总时长由**子动画**自动算出，不是 constructor 里填的 duration。
- **ScrollTrigger 挂在 timeline 上**，不是某个 `.to()` 里（见下节）。
- 可嵌套：`master.add(childTl, 0)`，但**别嵌带 ScrollTrigger 的子 timeline**（ScrollTrigger 只能在顶层）。

---

## 四、ScrollTrigger：滚动驱动（营销页主力 / 克隆叙事站必备）

```javascript
gsap.registerPlugin(ScrollTrigger);   // 用前注册一次（忘了会静默失效）
```

### scrub vs toggleActions（二选一）

```javascript
// scrub：动画进度绑定滚动进度（"滚动驱动"感）
gsap.to(".box", { x: 500, scrollTrigger: {
  trigger: ".box", start: "top center", end: "bottom center",
  scrub: 1,   // true=直接绑；数字=catch-up 延迟秒数，更顺
}});

// toggleActions：进入/离开离散触发（不绑滚动）
gsap.from(".card", { y: 60, opacity: 0, scrollTrigger: {
  trigger: ".card", start: "top 80%",
  toggleActions: "play none none reverse",  // onEnter/onLeave/onEnterBack/onLeaveBack
}});
```

**`scrub` 和 `toggleActions` 别同时用**（同时存在 scrub 赢）。

`start`/`end` 读法：`"触发元素位置 视口位置"`，如 `"top center"`=触发元素的 top 碰到视口 center。也可 `"bottom 80%"`、`"+=300"`、像素值、`"max"`。v3.12+ 可用 `start: "clamp(top bottom)"` 把范围夹在页面内。

### pin（钉住）

```javascript
scrollTrigger: { trigger: ".section", start: "top top", end: "+=1000", pin: true, scrub: 1 }
```
- `pinSpacing` 默认 `true`(加 spacer 防塌陷)，布局另行处理时才设 false。
- **别动被 pin 的元素本身，动它的子元素**。

### 长列表批量入场：`ScrollTrigger.batch()`

比给每个元素单独建 ScrollTrigger 高效，是 IntersectionObserver 的好替代：

```javascript
ScrollTrigger.batch(".card", {
  start: "top 85%",
  onEnter: (els) => gsap.to(els, { opacity: 1, y: 0, stagger: 0.12, overwrite: true }),
  onLeaveBack: (els) => gsap.set(els, { opacity: 0, y: 50, overwrite: true }),
});
```
**回调签名是 `(elements, triggers)`** 两个数组，不是普通 ScrollTrigger 的 `(self)`。batch 里不能传 `trigger`/`scrub`/`snap`/`toggleActions` 等。

### 伪水平滚动（containerAnimation）

官方标准写法——横向位移用 `xPercent: -100 * (区块数 - 1)`，最干净：

```javascript
const sections = gsap.utils.toArray(".container > section");
const scrollTween = gsap.to(".container", {
  xPercent: -100 * (sections.length - 1),
  ease: "none",                      // 必须 none，否则手指和位置不同步（最常见错误）
  scrollTrigger: { trigger: ".container", start: "top top", end: "+=3000", pin: true, scrub: 0.5 },
});
// 基于水平位置再触发别的：引用 containerAnimation
gsap.to(".panel-1", { y: 100, scrollTrigger: {
  containerAnimation: scrollTween, trigger: ".panel-1", start: "left center",
}});
```
注意：用了 `containerAnimation` 的 ScrollTrigger **不能再 pin/snap**；水平 tween 必须 `ease: "none"`。（官方已确认这三点，见 gsap.com/blog/3-8）

### refresh / cleanup（必做）

- **DOM/内容/字体变了** → 主动 `ScrollTrigger.refresh()`(viewport resize 自动刷并 debounce 200ms，但动态内容不会自动刷)。
- **非顺序创建**（异步/动态加载的 ScrollTrigger）要设 `refreshPriority`(页面靠上的数字小)，否则刷新顺序乱、pin 间距算错。
- **SPA/卸载**要 kill：`ScrollTrigger.getAll().forEach(t => t.kill())` 或按 `id` kill。React/Vue 里用对应的清理机制（下两节），别让 ScrollTrigger 跑在已卸载的节点上。
- `markers: true` 开发时看触发线，**生产必须关**。

### 第三方平滑滚动

GSAP 自带 **ScrollSmoother**(见插件节)不需要 proxy。接别家平滑滚动库（Lenis 等）才需要 `ScrollTrigger.scrollerProxy()` + 把 `ScrollTrigger.update` 注册成滚动监听。site-clone 反模式专门提醒过"别忘平滑滚动库"，复刻时注意识别。

---

## 五、React：`useGSAP`（自动清理，必用）

React 里手动管 GSAP 生命周期容易漏清理。官方 `@gsap/react` 的 `useGSAP` 自动 revert：

```javascript
import { useGSAP } from "@gsap/react";
import { useRef } from "react";
gsap.registerPlugin(useGSAP);          // useGSAP 本身是个 plugin，要注册

function Hero() {
  const root = useRef(null);
  useGSAP(() => {
    gsap.from(".item", { opacity: 0, y: 20, stagger: 0.1 });
  }, { scope: root });                 // scope 必传！否则 .item 全页面匹配，污染别的组件
  return <div ref={root}>...</div>;
}
```

- **`scope` 必传**：限定选择器只在这个组件内找。用 ref 指向真实 DOM 节点，别裸用可能跨组件匹配的选择器。
- **依赖变化重跑**：`{ dependencies: [endX], scope: root, revertOnUpdate: true }`，`revertOnUpdate` 让每次重跑前自动 revert 上一轮。
- **事件回调里建的动画 → 用 `contextSafe` 包**（否则不在 context 内、不会被清理，卸载后还在跑且报警告）：

```javascript
useGSAP((context, contextSafe) => {
  const onClick = contextSafe(() => gsap.to(el.current, { rotation: 180 }));
  el.current.addEventListener("click", onClick);
  return () => el.current.removeEventListener("click", onClick);  // 自己加的监听自己清
}, { scope: root });
```

- **没装 @gsap/react** 就用 `gsap.context()` + `useEffect` 兜底：`const ctx = gsap.context(() => {...}, root); return () => ctx.revert();`（**必须**在 return 里 `ctx.revert()`）。
- **SSR（Next.js）**：GSAP 只在浏览器跑，别在服务端渲染阶段执行 `gsap.*`/`ScrollTrigger.*`。useGSAP/useEffect 天然 client-only；顶层 import 没问题，但别在 SSR 期执行动画代码（介意打包体积可在 useEffect 里动态 import）。

---

## 六、Vue / Svelte（少量用到时）

原则和 React **完全同构**，只是生命周期钩子名不同：**mounted 之后建（DOM 已就绪）、unmount 时 `ctx.revert()`、选择器传 scope**。核心就是 `gsap.context(callback, 容器ref)` 把这一组动画圈起来，revert 一把清。

```javascript
// Vue 3 <script setup>
import { onMounted, onUnmounted, ref } from "vue";
import { gsap } from "gsap";
const container = ref(null);
let ctx;
onMounted(() => {
  ctx = gsap.context(() => {
    gsap.from(".item", { autoAlpha: 0, y: 20, stagger: 0.1 });
  }, container.value);                 // 第二参数 = scope
});
onUnmounted(() => ctx?.revert());
// template: <div ref="container">...</div>
```

- **Svelte**：`onMount(() => { const ctx = gsap.context(() => {...}, container); return () => ctx.revert(); })`，用 `bind:this={container}` 拿引用。Svelte 5 生命周期变了但原则一样（mounted 建、destroyed revert）。
- **别**在 setup/顶层同步代码里建动画（DOM 还没有）；插件在 app 级注册一次，别每次 render 注册。
- ScrollTrigger 也被 `gsap.context()` 收纳，`ctx.revert()` 一起清；内容异步加载后记得 `ScrollTrigger.refresh()`(Vue 用 nextTick、Svelte 用 tick 之后)。
- Nuxt 有 SSR + 插件懒加载的额外讲究，需要时查 `参考资料/gsap-skills/skills/gsap-frameworks/SKILL.md` 的 Nuxt 小节（含可跑示例 `examples/nuxt/`）。

---

## 七、性能底线（pro 第三节的"为什么"）

**为什么只动 transform/opacity**：

- `x`/`y`/`scale`/`rotation`/`skew` 和 `opacity` 只改合成层，GPU 处理，**不触发 layout 重排、避开大部分 paint** → 稳 60fps。
- `width`/`height`/`top`/`left`/`margin`/`padding` 触发重排+重绘，最贵，动起来必抖。**能用 transform 表达就别动这些**（GSAP 的 `x`/`y` 默认就走 translate）。

其它要点：

- **`will-change: transform`** 是给浏览器的优化提示，**只在真正会动的元素上加**，别"以防万一"全加——滥用反而拖慢；动完该撤就撤。
- **高频更新**（鼠标跟随）用 `gsap.quickTo()` 复用同一个 tween，别每次 mousemove 新建：
  ```javascript
  const xTo = gsap.quickTo("#cursor", "x", { duration: 0.4, ease: "power3" }),
        yTo = gsap.quickTo("#cursor", "y", { duration: 0.4, ease: "power3" });
  addEventListener("mousemove", e => { xTo(e.pageX); yTo(e.pageY); });
  ```
- **长列表**：用 stagger 而非一堆 delay；虚拟化或只动可见项，别一次建几百个 tween。
- **避免 layout thrashing**：别在循环里交替"读 offsetHeight / 写动画"，先全读再全写。
- **离屏/导航走掉的动画 kill 掉**，别在后台空跑。

---

## 八、插件速查（按"我们用不用得上"分级）

注册：每个插件用前 `gsap.registerPlugin(Flip, SplitText, ...)` 一次（React 在顶层或首个 useGSAP 前）。

**功能型界面 / 营销页真会用的（值得知道）：**

| 插件 | 干什么 | 典型场景 |
|---|---|---|
| **SplitText** | 把文字拆成字/词/行各自成元素，逐单元动 | 标题逐字/逐行入场（营销页常用）。`SplitText.create(".h", {type:"words,chars"})` 后动 `split.chars`。自定义字体要等字体加载完再 split，或用 `autoSplit:true`+`onSplit()`。注意 aria 默认会处理无障碍 |
| **Flip** | 记录布局态→改 DOM→从旧态平滑动到新态（FLIP） | 列表重排、展开/折叠、网格变化。`const s = Flip.getState(".item"); /*改DOM*/ Flip.from(s, {duration:.5})`。功能型界面也常用 |
| **ScrollToPlugin** | 动画式滚动到某位置/元素 | 锚点平滑跳转。`gsap.to(window, {scrollTo:{y:"#sec", offsetY:50}})` |
| **ScrollSmoother** | 整页平滑滚动（需 ScrollTrigger + 特定 DOM 结构） | 营销页惯性平滑滚。GSAP 自带，不需要第三方库 |
| **Draggable**(+InertiaPlugin) | 拖拽/旋转/抛掷，可带惯性 | 滑块、可拖卡片、可重排列表。`Draggable.create(".box",{type:"x,y",bounds:"#c",inertia:true})` |
| **Observer** | 归一化指针/滚轮/触摸输入，识别方向 | 自定义滑动手势，不绑死滚动位置。`Observer.create({target,onUp,onDown,tolerance:10})` |
| **CustomEase** | 自定义缓动曲线（cubic-bezier 或 SVG 路径） | 内置 ease 不够时。`CustomEase.create("name",".17,.67,.83,.67")` |

**重创意 / 游戏 / 可视化的（功能型界面几乎不碰，需要时查官方，别凭记忆写）：**

- **DrawSVG**（描边显隐）、**MorphSVG**（SVG 形状变形/图标互变）、**MotionPath**（沿路径运动）、**Physics2D / PhysicsProps**（物理运动）、**Pixi**（驱动 PixiJS）、**ScrambleText**（乱码/故障文字效果）、**EasePack / CustomWiggle / CustomBounce**（更多花式缓动）、**GSDevTools**（开发期时间轴调试器，别上线）。

> 这一档真要用时看本地 `参考资料/gsap-skills/skills/gsap-plugins/SKILL.md`（完整配置表）或 [官方 plugins 文档](https://gsap.com/docs/v3/Plugins/)——本文不展开是因为我们的场景用不上，不是它们不好。

---

## 九、utils 速查（写滚动映射 / scope 时用）

`gsap.utils.*` 是纯函数，不用注册。**省略最后那个"待处理的值"参数 → 返回一个可复用函数**（同一套配置处理很多值时用，如 mousemove/滚动回调里）：

| util | 干什么 | 例 |
|---|---|---|
| **clamp** | 夹在 min~max | `gsap.utils.clamp(0,100,150)//100` |
| **mapRange** | 一个区间映射到另一个（滚动/进度→动画值） | `mapRange(0,1,0,360,0.5)//180` 进度转角度 |
| **normalize** | 映射到 0~1 | `normalize(0,100,50)//0.5` |
| **interpolate** | 两值间按进度插值（数字/颜色/对象） | `interpolate("#f00","#00f",0.5)` 中间色 |
| **snap** | 吸附到步长或数组最近值 | `snap(10,23)//20` |
| **toArray** | 选择器/NodeList→真数组（可传 scope） | `toArray(".item", container)` |
| **selector** | 返回限定在某容器内的选择器函数 | `const q = gsap.utils.selector(ref); q(".box")` |
| **random** | 区间/数组取随机（注意：复用函数要传 `true` 当末参，不是省略） | `gsap.utils.random(-100,100,5)`；tween 里可写字符串 `"random(-100,100,5)"` 按 target 求值 |

其余（`distribute`/`pipe`/`wrap`/`wrapYoyo`/`getUnit`/`unitize`/`splitColor`/`shuffle`/`distribute`）需要时查官方 HelperFunctions——注意 mapRange/normalize 只处理**数字**，带单位用 getUnit/unitize。

---

## 配套导航

- 动效原则、该不该动、和"简洁清晰"的取舍 → [`frontend-design-pro.md`](frontend-design-pro.md) 第三节。
- 营销页美学（GSAP 的主场气质）→ [`frontend-design.md`](frontend-design.md)。
- 克隆带滚动驱动/视差/pin 的站时，用本文落地那些交互 → [`克隆skills-OneClickClone/site-clone.md`](克隆skills-OneClickClone/site-clone.md)。
- 需要某个插件/工具的完整配置 → **本地完整原文 [`参考资料/gsap-skills/`](参考资料/gsap-skills/)**（plugins/utils/frameworks/timeline 各有独立 SKILL.md + 四套可跑示例；见该目录 `导读.md`），或官方 [gsap.com/docs](https://gsap.com/docs/v3/)。
