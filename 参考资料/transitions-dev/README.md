# transitions-dev (mirror)

> **The canonical home for this skill is now [`Jakubantalik/transitions.dev`](https://github.com/Jakubantalik/transitions.dev).**
>
> This repository is kept as a backwards-compatible mirror so the
> legacy install command keeps working. New transitions and edits
> land in transitions.dev first; this repo is synced from there.

Production-ready CSS transitions for web apps, packaged as an agent skill.

Twelve drop-in transitions: card resize, number pop-in, notification badge, text swap, dropdown, modal, panel reveal, page slide, icon swap, success check, avatar group hover, error state shake. Each one ships portable CSS namespaced under `t-*` selectors with semantic CSS custom properties — paste the snippet into any project and it just works, no demo markup or framework dependencies.

## Install

Recommended (canonical):

```bash
npx skills add Jakubantalik/transitions.dev
```

Legacy (still works, this repo mirrors the latest skill payload):

```bash
npx skills add Jakubantalik/transitions-dev
```

Works with Cursor, Claude Code, Codex, and any agent that consumes `.cursor/skills/`, `.claude/skills/`, or `.agents/skills/`.

## Invoke

```
/skill transitions-dev
```

Or describe what you want — *"animate the dropdown opening"*, *"slide between two pages"*, *"add a notification badge to the bell icon"*, *"shake the input on validation error"*, *"hover spring on the avatar stack"* — and the agent will pick the right transition, paste the CSS, and wire the documented HTML hooks.

## Live demo

[transitions.dev](https://transitions.dev/) — every transition is interactive on the showcase page, with controls for tuning durations, easings, and distances.

## Maintenance

The skill payload is generated from [`transitions.dev`'s `index.html`](https://github.com/Jakubantalik/transitions.dev) so the skill stays in lockstep with what the showcase site demonstrates. The canonical build now lives in the [transitions.dev repo](https://github.com/Jakubantalik/transitions.dev) at `build/extract.mjs`; this mirror's copy of the build script defaults to a sibling `Essencial/` checkout for the historical layout.

```bash
SOURCE_HTML=/path/to/transitions.dev/index.html npm run build
```

The build script parses `PROTO_TEMPLATES` and the `:root { --pX-* }` block out of the source HTML and re-renders every file under [`skills/transitions-dev/`](skills/transitions-dev). Re-run after editing the source site to keep the skill in sync.

## License

[MIT](LICENSE)
