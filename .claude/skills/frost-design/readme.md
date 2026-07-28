# Frost Design System — Prose

**Frost (霜)** is the macOS-style design language of **Prose (普珞思)** — an AI-native bid/tender document writing platform (AI 原生标书编制平台) for the Chinese market. Prose is an agent workspace: you give it a tender document (招标文件), and it parses requirements, drafts responses, assembles the bid outline, and pulls from a knowledge base of qualifications, case studies, and résumés.

Frost is deliberately the **opposite pole** of Prose's other brand language, *Archive* (a warm-paper, hairline aesthetic). Where Archive uses warm paper and 1px lines, Frost organizes information with **cold-gray neutrals, translucent material, and depth** — it feels like a native macOS app: quiet, focused, layered.

> **One design stance:** *material is hierarchy*. The interface doesn't separate regions with strokes — it separates them with the **thickness of glass** and the **depth of shadow**. The closer content is to the user, the more solid the material and the deeper the shadow. Chrome (sidebars, toolbars) recedes into translucency; the document and the conversation are always the brightest, most solid layer.

## Source

This system was built from a single ground-truth artifact:

- **`frost/brand.html`** — a complete, self-contained brand specification board (in Simplified Chinese) titled *"Prose 品牌设计：Frost 霜（macOS 风格设计语言）"*. It defines tokens, materials, type scale, controls, the app window, and the dark appearance. Every value in this design system is copied verbatim from it (no rounding to a 4/8 grid — macOS control metrics use odd values like 7, 9, 13).

There was **no separate component codebase or Figma file** — the brand board is the whole source. If you have access, read it for the original prose and rationale.

---

## CONTENT FUNDAMENTALS

Prose's product surface is written in **Simplified Chinese**, in the register of formal Chinese procurement / tender work. Keep UI copy in Chinese; this English guide exists for designers.

- **Domain & register.** The vocabulary is professional-procurement: 招标文件 (tender document), 投标文件 (bid document), 标书 (bid), 技术需求 (technical requirements), 资质证照 (qualifications), 业绩案例 (track record), 实质性条款 (substantive clauses), 技术偏差表 (technical-deviation table). Use the real terms, not generic "document/file" language.
- **Voice — the product narrates, the user commands.** The user speaks in imperatives: *"解析这份招标文件的技术需求，生成技术需求清单。"* ("Parse this tender's technical requirements, generate a requirements list.") The agent reports back in calm, completed-action statements: *"已从第三章提取全部技术需求条目，按功能、性能、接口、安全四类归档。"* ("Extracted all technical-requirement items from Chapter 3, filed under four categories…"). It leads with **已 (already / done)** and **正在 (in progress)** — status-first, not chatty.
- **Tone.** Quiet, precise, understated. Marketing lines are short and human: *"为每一份标书，配一个安静的工作台"* ("A quiet workbench for every bid"). No exclamation marks, no hype, no second-person sales pressure.
- **Casing & punctuation.** Chinese full-width punctuation (，。：「」). Latin/Chinese spacing is loose-natural. Numbers are tabular (`font-variant-numeric: tabular-nums`) and money/quantities sit in monospace. English labels, when present, are Title Case and terse.
- **No emoji.** The brand never uses emoji. Status is carried by semantic-colored dots, badges, and Phosphor icons — never 🟢✅⚠️.
- **Bold for nouns that matter.** Inside agent prose, `**…**` bolds the load-bearing nouns (the four requirement categories, the response counts) — used sparingly, never for emphasis-shouting.

---

## VISUAL FOUNDATIONS

- **Color.** Cold-gray neutral ground (`--canvas #EEF0F3` light, `#161618` dark) with **a single accent — system blue** (`#0064E1` light, `#409CFF` dark). Blue means exactly two things: *interactive* and *in-progress*. Decoration never spends color. Semantic colors ship as **graphic/text pairs** — a saturated value for fills & status dots, a darkened value for legible text on tint (e.g. success `#34C759` graphic / `#1D8F45` text).
- **Type.** **No webfonts.** The system stack resolves to **SF Pro + PingFang SC** on macOS and each platform's native sans elsewhere — zero load cost, always matching the host OS. Tight display tracking (-2.2% on large titles), generous 1.7 line-height on CJK body. Web note: bump CJK body 1–2px (13→14–15) to offset PingFang's small-size stroke density. *Sole sanctioned exception (2026-07, source-trace-preview PRD):* the 溯源预览 source-document panel typesets tender originals in serif — Newsreader + Noto Serif SC, self-hosted via next/font, scoped strictly to `.cv-trace-doc` inside the panel. It renders *documents*, not UI; never extend webfonts beyond that scope, and don't flag that panel as a violation in review.
- **Material (the signature).** Four grades of glass, front-to-back: **sidebar** (blur 60, white 55%), **toolbar** (blur 40, white 68%), **popover** (blur 40, white 75%), **sheet** (blur 24, white 85%). Blur radius = "how far from the user"; white opacity = "how heavy the content it carries". This is a **Web approximation of macOS Vibrancy** (`backdrop-filter` + layered strokes + a top highlight) — *not* an official Apple implementation. Honest solid-surface fallback under `prefers-reduced-transparency`.
- **Backgrounds.** A **cold-blue aurora wallpaper** (layered radial + linear gradients, `--wallpaper`) sits behind glass surfaces — the macOS desktop metaphor. Solid content surfaces (`--surface`) never show the wallpaper; only chrome does. No images, textures, or photography in the system itself.
- **Depth replaces strokes.** Three shadow steps (`--elev-1/2/3`), each pairing a soft drop shadow with a **.5px ambient ring** (the contact edge). Hairline `--separator` dividers exist but regions are mostly distinguished by elevation, not borders.
- **Radius.** One continuous-corner ramp, fixed order: control 7 < field 9 < window 12 < card 14 < panel 18. The **app icon alone** uses 22.4% (the macOS superellipse) — never a circle or square.
- **Animation.** Answers three questions only — what happened, where from, where to. Durations: micro 120ms / float 200ms / panel 320ms. Standard easing `cubic-bezier(.32,.72,0,1)`. Only `transform` & `opacity` animate; entrance offset ≤ 8px; **no infinite loops**. Everything degrades to an instant cut under `prefers-reduced-motion`.
- **Hover / press.** Hover is a quiet wash: default buttons → `--surface-2`, plain/ghost → `--blue-soft`, icon buttons → ~9% gray fill, menu rows → full-width **blue**. Press is a **scale**: buttons `scale(.97)`, icon buttons `scale(.92)`, send button `.92`. Primary buttons carry a subtle top highlight (inset white) and a downward blue gradient.
- **Cards & surfaces.** White fill, level-1 shadow, 14px radius, no border. Recessed (`inset`) cards use the gray fill + a hairline ring. Larger panels go to 18px radius. Radius and depth scale together.
- **Transparency & blur — when.** Only on **chrome and overlays** (sidebar, toolbar, popovers, menus, toasts, sheets) so the wallpaper/底层 content shows through. **Never** on primary content surfaces — the document and the agent stream are always solid and brightest.
- **Dark appearance.** Not an inversion: near-black cold-gray canvas (`#161618`), deep-gray translucent glass, accent lifted to `#409CFF` for contrast. Same components, radii, and shadows — only color tokens swap, via `[data-appearance="dark"]`.

---

## ICONOGRAPHY

- **Icon set: [Phosphor Icons](https://phosphoricons.com/)**, *regular* weight, loaded from CDN: `https://unpkg.com/@phosphor-icons/web@2.1.1/src/regular/style.css`. Used as `<i class="ph ph-{name}"></i>`. This is the exact set and weight the brand board uses — keep to **regular** weight for consistency (don't mix in bold/fill/duotone).
- Common glyphs seen in-product: `sparkle` (agent action), `file-text`, `folder-simple`, `magnifying-glass`, `sidebar-simple`, `paper-plane-tilt` (send), `tree-structure` (outline), `identification-card`, `buildings`, `files`, `caret-right/down`, `check`, `clock-counter-clockwise`, `stack`, `plus-circle`.
- **No emoji, no Unicode pictographs** as icons. Status uses semantic-colored dots/badges.
- **Logo / app icon:** `assets/frost-icon.svg` — three stacked translucent "glass sheets" aggregating bottom-to-top into a finished bid, on a blue superellipse tile with a fixed top-left→bottom-right gradient (`#5FB0FF → #1670EC → #0A3FA8`). Rules: corner radius fixed at 22.4%; gradient never rotated/mirrored; no decoration beyond the drop shadow. At ≤16px, drop the bottom sheet and body lines, keep the double outline.

---

## INDEX

**Root**
- `styles.css` — the single entry point consumers link (import list only).
- `readme.md` — this guide.
- `SKILL.md` — Agent-Skill front matter for use in Claude Code.
- `assets/frost-icon.svg` — the Prose app icon / logo.

**Tokens** (`tokens/`, all `@import`ed by `styles.css`)
- `colors.css` · `typography.css` · `spacing.css` · `radius.css` · `elevation.css` · `motion.css` · `materials.css` · `base.css`

**Components** (`components/<group>/` — React primitives, `window.FrostDesignSystemProse_5680eb`)
- controls/ — **Button, IconButton, Segmented, Switch, Checkbox**
- forms/ — **Field**
- surfaces/ — **Card, Window**
- feedback/ — **Badge, ToolChip, Toast, Tooltip**
- navigation/ — **Menu, SidebarItem** (+ SidebarGroup)
- data/ — **Avatar**

**UI kit** (`ui_kits/`)
- prose/ — the **Prose agent workspace** (`index.html`): macOS window, glass sidebar, agent stream + composer, bid-document outline. Interactive (switch projects, send a message, toggle dark appearance). Composed from the primitives above.

**Foundations** (`guidelines/`) — specimen cards rendered in the Design System tab: color ramps, type scale, spacing, radius, elevation, materials, motion, identity.

---

### Caveats
- **Fonts are intentionally system-only.** The compiler will flag `SF Pro Display` / `JetBrains Mono` as having no `@font-face` — that is correct and by design (Frost ships no webfonts). No font upload is needed.
- **Glass material is a Web approximation** of macOS Vibrancy, with a solid fallback under reduced-transparency. It is not Apple's real material.
