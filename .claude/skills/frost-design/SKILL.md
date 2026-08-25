---
name: frost-design
description: Use this skill to generate well-branded interfaces and assets for Prose (Frost · 霜 design language, now Frost 2 「凝光」), either for production or throwaway prototypes/mocks/etc. Contains essential design guidelines, colors, type, fonts, glass materials, assets, and UI kit components for prototyping. Frost is a macOS-style language (cold-gray neutrals, single system-blue accent, refracting lens glass for controls + frosted soft glass for chrome, system fonts, Phosphor icons) for an AI-native Chinese-market bid/tender writing platform.
user-invocable: true
---

Read the readme.md file within this skill, and explore the other available files.

If creating visual artifacts (slides, mocks, throwaway prototypes, etc), copy assets out and create static HTML files for the user to view. If working on production code, you can copy assets and read the rules here to become an expert in designing with this brand.

If the user invokes this skill without any other guidance, ask them what they want to build or design, ask some questions, and act as an expert designer who outputs HTML artifacts _or_ production code, depending on the need.

## Quick start
- Link `styles.css` for all tokens (colors, type, spacing, radius, elevation, motion, glass materials). No webfonts — the system stack (SF Pro + PingFang SC) is intentional; never substitute a different family. (Sole sanctioned exception: the 溯源预览 source-document panel renders tender originals in a serif stack — self-hosted Newsreader + Noto Serif SC via next/font, scoped strictly to `.cv-trace-doc`. Do not flag it in review; do not extend it elsewhere.)
- Glass: `.frost-glass.frost-glass--lens` (凝 — refracts, for the control layer) or `.frost-glass.frost-glass--soft` (霜 — frosted, for chrome), `data-thick="thin|regular|thick"`, `--interactive` for clickable pills, `--flush` for embedded bars. Include `assets/frost-lens.js` once per page for the refraction (Chromium) — without it the same material renders frosted. Everything sits on `.frost-wallpaper`.
- Icons: Phosphor Icons, regular weight — `<link rel="stylesheet" href="https://unpkg.com/@phosphor-icons/web@2.1.1/src/regular/style.css">`, used as `<i class="ph ph-{name}"></i>`. No emoji.
- Components live under `components/<group>/` as React primitives; mount them via the compiled bundle (`_ds_bundle.js`, global `window.FrostDesignSystemProse_5680eb`). Each component has a `.prompt.md` with usage.
- The full product surface is in `ui_kits/prose/` — copy it as the starting point for any Prose app view.

## Non-negotiables
- One accent: system blue, for *interactive* and *in-progress* only. Light (rim, illumination, specular) is white — it never spends the accent.
- Material is hierarchy — glass is the control layer floating over the cold-blue wallpaper; content surfaces (documents, matrices, the composer) are solid and brightest. Never blur content; never stack glass on glass; at most three lens faces per screen, the rest is soft.
- Light is state: the specular follows the pointer, press brightens, running state gets the border beam. Event-driven only — no loops.
- Depth (3 shadow steps for solids, 5-part stacks for glass) replaces strokes. Continuous-corner radius ramp (control 7 → panel 18, lens panel 20; icon 22.4%); nested corners are concentric (inner = outer − padding).
- Text on glass stays ≥ 4.5:1; `prefers-reduced-transparency` (or the user's 柔和 mode) turns every lens face soft and every soft face solid.
- Product copy is Simplified Chinese in a formal procurement register; the agent narrates status-first (已… / 正在…). No emoji, no hype.
