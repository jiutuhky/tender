# Frost Design System — Prose

**Frost (霜)** is the macOS-style design language of **Prose (普珞思)** — an AI-native bid/tender document writing platform (AI 原生标书编制平台) for the Chinese market. Prose is an agent workspace: you give it a tender document (招标文件), and it parses requirements, drafts responses, assembles the bid outline, and pulls from a knowledge base of qualifications, case studies, and résumés.

Frost is deliberately the **opposite pole** of Prose's other brand language, *Archive* (a warm-paper, hairline aesthetic). Where Archive uses warm paper and 1px lines, Frost organizes information with **cold-gray neutrals, glass, light, and depth** — it feels like a native macOS app: quiet, focused, layered.

> **Three stances (Frost 2 · 凝光):**
> 1. *Material is hierarchy.* The interface doesn't separate regions with strokes — it separates them with the **kind and thickness of glass** and the **depth of shadow**. Chrome recedes into glass; the document and the conversation are always the brightest, most solid layer.
> 2. *Light is state.* Glass has a rim, an illumination, a specular that follows the pointer, and — when the agent is running — a beam around its frame. Light says "this can be pressed" and "this is working"; it is white, and never spends the accent.
> 3. *Environment is context.* Glass knows what it sits on: the wallpaper gives it something to refract, and glass landing on a dark region inverts its text instead of going illegible.

## Source

This system was built from two ground-truth artifacts (both in `.design/prototype/frost/`):

- **`brand.html`** — the original Frost brand board (in Simplified Chinese), *"Prose 品牌设计：Frost 霜（macOS 风格设计语言）"*. Tokens, type scale, controls, the app window, dark appearance. Every non-material value here is copied verbatim from it (no rounding to a 4/8 grid — macOS control metrics use odd values like 7, 9, 13).
- **`glass-upgrade.html`** — the *Frost 2 「凝光」* proposal board (2026-08), which replaced the original four frosted grades with the lens / soft material system, the optical layer model, the wallpaper, and the behavioural rules below. All material values are copied from it.

There is **no separate Figma file** — the boards are the whole source.

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

- **Color.** Cold-gray neutral ground (`--canvas #EEF0F3` light, `#161618` dark) with **a single accent — system blue** (`#0064E1` light, `#409CFF` dark). Blue means exactly two things: *interactive* and *in-progress*. Decoration never spends color — and neither does light: rim, illumination and specular are white. Semantic colors ship as **graphic/text pairs** — a saturated value for fills & status dots, a darkened value for legible text on tint (e.g. success `#34C759` graphic / `#1D8F45` text).
- **Type.** **No webfonts.** The system stack resolves to **SF Pro + PingFang SC** on macOS and each platform's native sans elsewhere — zero load cost, always matching the host OS. Tight display tracking (-2.2% on large titles), generous 1.7 line-height on CJK body. Web note: bump CJK body 1–2px (13→14–15) to offset PingFang's small-size stroke density. *Sole sanctioned exception (2026-07, source-trace-preview PRD):* the 溯源预览 source-document panel typesets tender originals in serif — Newsreader + Noto Serif SC, self-hosted via next/font, scoped strictly to `.cv-trace-doc` inside the panel. It renders *documents*, not UI; never extend webfonts beyond that scope, and don't flag that panel as a violation in review.
- **Material (the signature).** Two materials × three thicknesses — see **MATERIALS** below. **凝 lens** refracts what's behind it and carries a rim light; it is for the *control layer* (floating windows, boards, pills, menus, toasts). **霜 soft** is frosted; it is for large *chrome* (top bar, sidebar, drawer, sheet, scrim). Thickness (thin / regular / thick) sets blur, lens strength and shadow together. This is a **Web approximation** of Apple Liquid Glass and HyperOS 4 柔光玻璃 — `backdrop-filter` + an SVG displacement filter + layered light — *not* an official implementation. Honest solid-surface fallback under `prefers-reduced-transparency`.
- **Wallpaper.** A **low-frequency cold-blue wallpaper** (`--wallpaper`: four radials + a linear, mostly light, one deep-blue lobe in a corner) sits behind glass surfaces — the macOS desktop metaphor, tuned so glass has something to refract while solid content stays the brightest thing on screen. Solid content surfaces (`--surface`) never show the wallpaper; only chrome and floating controls do. No images, textures, or photography in the system itself.
- **Depth replaces strokes.** Solid surfaces use three shadow steps (`--elev-1/2/3`), each pairing a soft drop shadow with a **.5px ambient ring** (the contact edge). Glass surfaces use five-part stacks (`--glass-shadow-thin/regular/thick`: ambient, mid, near, all-round haze, contact ring) because lens glass has no base colour — the shadow *is* its edge. Hairline `--separator` dividers exist for lists; chrome meets content on a `.5px` contact edge (`box-shadow: inset … var(--separator)`), never a 1px border, and bars over scrolling content use `.frost-scroll-edge` (progressive blur) instead of a line.
- **Radius.** One continuous-corner ramp, fixed order: control 7 < field 9 < window 12 < card 14 < panel 18; **lens panels take 20** (the rim needs room to turn the corner). Nested corners are **concentric: inner = outer − padding** (menu 12 − 6 = row 6; lens panel 20 − 8 = control 12); pills are 999. The **app icon alone** uses 22.4% (the macOS superellipse) — never a circle or square.
- **Animation.** Answers three questions only — what happened, where from, where to. Durations: micro 120ms / float 200ms / panel 320ms. Standard easing `cubic-bezier(.32,.72,0,1)`. Only `transform` & `opacity` animate (plus the registered `--_spot-a` number on glass); entrance offset ≤ 8px; **no infinite loops** — the running-state border beam is the single sanctioned loop and it stops the moment the state ends. Everything degrades to an instant cut under `prefers-reduced-motion`, which also disables the pointer specular.
- **Hover / press.** Hover is a quiet wash on solids: default buttons → `--surface-2`, plain/ghost → `--blue-soft`, icon buttons → ~9% gray fill, menu rows → full-width **blue**. On glass, hover is *light*: the specular spot fades in under the pointer (`.frost-glass--interactive`). Press is a **scale** (`scale(.97)`, icon buttons `.92`) — and on glass the spot brightens with it. Primary buttons carry a subtle top highlight (inset white) and a downward blue gradient.
- **Cards & surfaces.** White fill, level-1 shadow, 14px radius, no border. Recessed (`inset`) cards use the gray fill + a hairline ring. Larger panels go to 18px radius. Radius and depth scale together. A `Card` can be glass (`material="lens" | "soft"`) — but a glass card is a control surface, never a content container.
- **Transparency & blur — when.** Only on **chrome and floating controls** (top bar, sidebar, drawer, popovers, menus, toasts, pills, the agent's floating message window) so the wallpaper shows through. **Never** on primary content — documents, matrices, lists, tables, and anything you type into (the composer) are always solid and brightest. Glass never stacks on glass (a popover cannot sample the sidebar glass beneath it — give it a solid or wallpaper backdrop).
- **Dark appearance.** Not an inversion: near-black cold-gray canvas (`#161618`), deep-charcoal glass tints, accent lifted to `#409CFF` for contrast, rim and illumination dimmed rather than flipped. Same components, radii, and shadow geometry — only color tokens swap, via `[data-appearance="dark"]`.

---

## MATERIALS (Frost 2 · 凝光)

**Optical stack**, bottom → top — every glass element renders all five:

| # | layer | token | what it does |
|---|---|---|---|
| ⑤ | shadow | `--glass-shadow-{thin,regular,thick}` | ambient + mid + near + all-round haze + .5px contact ring — the edge of a surface that has no base colour |
| ① | tint + lens | `--glass-tint-{lens,soft}`, `--glass-blur-*`, `--glass-lens-*` | `backdrop-filter`: blur + saturate, and on lens glass an SVG displacement that bends the backdrop at the edges (chromatic dispersion on regular/thick, none on thin) |
| ② | illumination | `--glass-illum`, `--glass-spot-alpha` | a fixed top light + a specular spot at `--mx/--my` that follows the pointer on interactive glass |
| ③ | content | — | text and controls in Frost's normal colours; `[data-tone="dark"]` swaps to `--glass-label-on-dark` |
| ④ | rim | `--glass-rim`, `--glass-rim-inner` | 1.5px ring, 135°: top-left catches the light, bottom-right is the internal reflection, flanks keep a thread |

**Matrix** — pick material by *what it is*, thickness by *how much it carries*:

| | thin — pills, chips, icon buttons | regular — popovers, menus, toasts | thick — panels, windows |
|---|---|---|---|
| **凝 lens** (refracts, rim, control layer) | blur 10 · lens 24 · shadow thin | blur 16 · lens 56 · shadow regular | blur 24 · lens 84 · shadow thick |
| **霜 soft** (frosted, hairline, chrome) | blur 30 · tint 60% · shadow thin | blur 30 · tint 60% · shadow regular | blur 30 · tint 60% · shadow thick |

**Placement** in the Prose workspace:

| surface | material |
|---|---|
| top bar · activity rail · sidebar | 霜 · thick, embedded (`--flush`, .5px contact edge) |
| canvas toolbar · artifact header | 霜 · regular + `.frost-scroll-edge` |
| agent message window (open) · agent board | 凝 · thick (radius 20) |
| activity bar · quick commands · dock chips · viewport hint | 凝 · thin, pill, `--interactive` |
| menu · popover · toast · tooltip | 凝 · regular |
| drawer · trace-preview scrim · sheet | 霜 · thick |
| matrix cards · document sheet · composer · item lists | **solid — always** |

**Rules**

1. **Glass is the control layer.** Content is solid; anything you type into is solid even when it sits inside glass.
2. **Glass never stacks on glass.** A surface cannot sample glass beneath it and collapses to a flat plate. Floating over soft chrome → give the floater a solid/wallpaper backdrop; adjacent pills share one container and merge when they meet.
3. **At most three lens faces per screen.** The displacement filter is paid per pixel; large areas are soft; over budget, demote thick → thin to soft.
4. **Transitions run soft.** While a glass shell changes size the lens filter would re-run every frame — swap to soft for the tween (`data-tweening`) and bend again on arrival.
5. **Light is white.** Rim, illumination, specular use white and the ambient colour only; blue remains interactive / in-progress. The running-state beam is the one lit thing that may be blue — it *is* "in progress".
6. **Concentric corners.** inner = outer − padding. Lens panel 20 / padding 8 → controls 12; pills 999.
7. **Legibility floor.** Text on glass ≥ 4.5:1 against the darkest corner of the wallpaper; ambient sensing flips text on dark regions (small elements flip, large panels only adjust); `prefers-reduced-transparency` and the user's 柔和 mode turn lens → soft, and soft → solid.
8. **No new loops.** Specular follows the pointer (event-driven), press brightens for 120ms, merges take 320ms on the standard curve; reduced motion turns the specular off.

**Implementation.** `tokens/materials.css` ships the tokens and utilities: `.frost-wallpaper`; `.frost-glass` + `.frost-glass--lens | --soft`, `data-thick="thin|regular|thick"`, `.frost-glass--interactive`, `.frost-glass--flush`, `[data-tone="dark"]`; `.frost-scroll-edge`. `assets/frost-lens.js` (include once per page) injects the SVG refraction filters, sets `html[data-warp]` on Chromium, `html[data-glass="clear|soft"]` and `html[data-spot]` from media preferences, and writes `--mx/--my` under the pointer. Without the script — or on Safari / Firefox — the same classes render as frosted glass with rim and illumination intact. **Never** put `filter`, `opacity < 1`, `mask`, `mix-blend-mode` or `isolation` on an ancestor of a glass element: it cuts the backdrop off. Ambient sensing (sampling the wallpaper under an element) is app-level; the system only consumes the result via `data-tone` / `FrostLens.setTone()`.

---

## ICONOGRAPHY

- **Icon set: [Phosphor Icons](https://phosphoricons.com/)**, *regular* weight, loaded from CDN: `https://unpkg.com/@phosphor-icons/web@2.1.1/src/regular/style.css`. Used as `<i class="ph ph-{name}"></i>`. This is the exact set and weight the brand board uses — keep to **regular** weight for consistency (don't mix in bold/fill/duotone).
- Common glyphs seen in-product: `sparkle` (agent action), `file-text`, `folder-simple`, `magnifying-glass`, `sidebar-simple`, `paper-plane-tilt` (send), `tree-structure` (outline), `identification-card`, `buildings`, `files`, `caret-right/down`, `check`, `clock-counter-clockwise`, `stack`, `plus-circle`.
- **No emoji, no Unicode pictographs** as icons. Status uses semantic-colored dots/badges.
- **Logo / app icon:** `assets/frost-icon.svg` — three stacked translucent "glass sheets" aggregating bottom-to-top into a finished bid, on a blue superellipse tile with a fixed top-left→bottom-right gradient (`#5FB0FF → #1670EC → #0A3FA8`). Rules: corner radius fixed at 22.4%; gradient never rotated/mirrored; the only decoration allowed is the drop shadow and a thin rim highlight (the Bot avatar in-product shares it). At ≤16px, drop the bottom sheet and body lines, keep the double outline.

---

## INDEX

**Root**
- `styles.css` — the single entry point consumers link (import list only).
- `readme.md` — this guide.
- `SKILL.md` — Agent-Skill front matter for use in Claude Code.
- `assets/frost-icon.svg` — the Prose app icon / logo.
- `assets/frost-lens.js` — refraction filters + pointer specular + mode switches for lens glass (include once per page).

**Tokens** (`tokens/`, all `@import`ed by `styles.css`)
- `colors.css` · `typography.css` · `spacing.css` · `radius.css` · `elevation.css` · `motion.css` · `materials.css` · `base.css`

**Components** (`components/<group>/` — React primitives, `window.FrostDesignSystemProse_5680eb`)
- controls/ — **Button, IconButton, Segmented, Switch, Checkbox**
- forms/ — **Field**
- surfaces/ — **Card** (solid, or `material="lens" | "soft"`), **Window** (soft-glass toolbar)
- feedback/ — **Badge, ToolChip, Toast** (lens), **Tooltip**
- navigation/ — **Menu** (lens), **SidebarItem** (+ SidebarGroup, inside a soft sidebar)
- data/ — **Avatar**

**UI kit** (`ui_kits/`)
- prose/ — the **Prose agent workspace** (`index.html`): macOS window, soft-glass sidebar, agent stream + composer, bid-document outline. Interactive (switch projects, send a message, toggle dark appearance). Composed from the primitives above.

**Foundations** (`guidelines/`) — specimen cards rendered in the Design System tab: color ramps, type scale, spacing, radius, elevation, materials (凝 / 霜 matrix, optical layers), motion, identity.

---

### Caveats
- **Fonts are intentionally system-only.** The compiler will flag `SF Pro Display` / `JetBrains Mono` as having no `@font-face` — that is correct and by design (Frost ships no webfonts). No font upload is needed.
- **Glass is a Web approximation** of Apple Liquid Glass / HyperOS 4 柔光玻璃. Refraction (`backdrop-filter: url()`) only runs on Chromium and only with `assets/frost-lens.js` loaded; Safari and Firefox render the same material without the bend. Solid fallback under reduced transparency.
- **`_ds_bundle.js` is hand-patched** to the Frost 2 class names and Card API (the compiler that produced it isn't checked in); `sourceHashes` in its header are kept in sync with the sources. If you regenerate the bundle, diff it against the current one.
