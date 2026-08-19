# 反 slop 规范（三家原文，按需深读）

> 本目录是 [`参考资料/`](../README.md) 的"反 AI 味规范"子库：三个高星反 slop skill 的**原文**。
> `frontend-design-pro.md` 第四节已经把**跨场景通用的负面规则**消化成一张自检门——**写功能型界面只过第四节就够**，下面的原文是深审、打磨、或做营销页时才读。
>
> 三家协议都是 **MIT**（各自目录里有 LICENSE），同步于 2026-08-19。上游克隆在 `参考项目/前端与设计/{hallmark,taste-skill,ui-skills}`。

## 谁在什么场景读哪个

| 你在做 | 读 | 为什么是它 |
|---|---|---|
| 界面写完，**要逐条深审**有没有 AI 味 | [`hallmark/references/slop-test.md`](hallmark/references/slop-test.md)（58 道关卡 + 六轴自评） | pro 第四节是它的精简版；要全量过一遍或给审查报告时读原文。**营销专属门（hero / nav / footer / 宏结构 / stamp）对功能型界面跳过** |
| 想知道某条门**为什么**、反例长什么样 | [`hallmark/references/anti-patterns.md`](hallmark/references/anti-patterns.md)、[`interaction-and-states.md`](hallmark/references/interaction-and-states.md)、[`microinteractions.md`](hallmark/references/microinteractions.md) | 门的出处和解释 |
| **改别人写的界面**、快速去 slop | [`ui-skills/baseline-ui/SKILL.md`](ui-skills/baseline-ui/SKILL.md)（间距 / 层级 / 字体 / 小布局一遍过） | 轻量，10 分钟级 |
| 对一个已有产品面做**系统审计**、出修改计划 | [`ui-skills/improve-ui/SKILL.md`](ui-skills/improve-ui/SKILL.md) | 对照它自己的设计证据找问题，不是凭喜好 |
| 专项修：无障碍 / 动效性能 / meta | `ui-skills/fixing-accessibility/`、`ui-skills/fixing-motion-performance/`、`ui-skills/fixing-metadata/` | 各管一件事 |
| 从现有产品 / 网站**写 DESIGN.md** | [`ui-skills/create-design-md/SKILL.md`](ui-skills/create-design-md/SKILL.md) | 跟 `../../克隆skills-OneClickClone/extract-design-system.md` 同类，这个偏"写文档"，那个偏"扒真值" |
| **营销 / 品牌落地页**，要主张、要冲击力 | [`hallmark/SKILL.md`](hallmark/SKILL.md)（宏结构 + 22 主题 + 四个动词 default / audit / redesign / study）或 [`taste-skill/taste-skill/SKILL.md`](taste-skill/taste-skill/SKILL.md)（单文件 87KB 大 prompt） | 这两家的**正面规则**（要大胆、破网格、选宏结构）只对营销页成立。pro 的"主体 + 内容先立住"仍优先，它们是放大器 |
| 营销页要某种固定气质 | `taste-skill/minimalist-skill/`（暖单色编辑风）、`taste-skill/soft-skill/`（高端 agency 软风）、`taste-skill/redesign-skill/`（升级现有站） | Taste 的 11 个变体只拷了这三个最常用的，其余在上游 |

## 目录

```
反slop规范/
├── hallmark/            SKILL.md + references/（22 份 md：slop-test、anti-patterns、typography、color、motion、component-cookbook、themes/、genres/…）；只拷了 md，90MB 资产没拷
├── taste-skill/         taste-skill / minimalist-skill / soft-skill / redesign-skill 四个 SKILL.md
└── ui-skills/           7 个小 skill（baseline-ui、improve-ui、fixing-*、create-design-md、ui-skills-root）+ 上游 README
```

## 跟 pro 的关系（别读反了）

- pro 第四节 = 三家里**负面、跨场景通用**的那部分，已消化、已去重，**功能型界面的默认标准**。
- 本目录 = 原文全量。pro 说"深审见原文"的时候来；**别拿 Hallmark 的"要大胆"去覆盖 pro 的"简洁克制"**——场景不同。
- **两边打架时的裁决**：功能型界面听 pro（Hallmark 的 hero 留白比例、section 间必须有装饰变化之类不适用）；营销页听 Hallmark 的正面规则，**但 pro 第四节 20 条负面门仍然必过**——负面门是底线，正面规则是风格。
- ui-skills 是"写完之后怎么改"，跟 `web-design-guidelines.md`（Vercel 守则）并列，一个管 taste 一个管规范。
