---
name: frost-design
description: Use this skill to generate well-branded interfaces and assets for Prose (Frost · 霜 design language), either for production or throwaway prototypes/mocks/etc. Contains essential design guidelines, colors, type, fonts, assets, and UI kit components for prototyping. Frost is a macOS-style language (cold-gray neutrals, single system-blue accent, translucent glass material, system fonts, Phosphor icons) for an AI-native Chinese-market bid/tender writing platform.
user-invocable: true
---

Read the README.md file within this skill, and explore the other available files.

If creating visual artifacts (slides, mocks, throwaway prototypes, etc), copy assets out and create static HTML files for the user to view. If working on production code, you can copy assets and read the rules here to become an expert in designing with this brand.

If the user invokes this skill without any other guidance, ask them what they want to build or design, ask some questions, and act as an expert designer who outputs HTML artifacts _or_ production code, depending on the need.

## Quick start
- Link `styles.css` for all tokens (colors, type, spacing, radius, elevation, motion, glass materials). No webfonts — the system stack (SF Pro + PingFang SC) is intentional; never substitute a different family. (Sole sanctioned exception: the 溯源预览 source-document panel renders tender originals in a serif stack — self-hosted Newsreader + Noto Serif SC via next/font, scoped strictly to `.cv-trace-doc`. Do not flag it in review; do not extend it elsewhere.)
- Icons: Phosphor Icons, regular weight — `<link rel="stylesheet" href="https://unpkg.com/@phosphor-icons/web@2.1.1/src/regular/style.css">`, used as `<i class="ph ph-{name}"></i>`. No emoji.
- Components live under `components/<group>/` as React primitives; mount them via the compiled bundle (`_ds_bundle.js`, global `window.FrostDesignSystemProse_5680eb`). Each component has a `.prompt.md` with usage.
- The full product surface is in `ui_kits/prose/` — copy it as the starting point for any Prose app view.

## Non-negotiables
- One accent: system blue, for *interactive* and *in-progress* only.
- Material is hierarchy — chrome is translucent glass over the cold-blue wallpaper; content surfaces are solid and brightest. Never blur content.
- Depth (3 shadow steps) replaces strokes. Continuous-corner radius ramp (control 7 → panel 18; icon 22.4%).
- Product copy is Simplified Chinese in a formal procurement register; the agent narrates status-first (已… / 正在…). No emoji, no hype.
