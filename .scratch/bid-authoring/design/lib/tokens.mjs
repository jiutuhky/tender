// Frost 2「凝光」token 与共享样式 —— 值逐条取自 .claude/skills/frost-design/tokens/*.css
// 与 frontend/app/globals.css 的 workspace 段（.topbar / .cv-* / .composer），不做 4/8 网格取整。
export const TOKENS_CSS = `
    body { margin: 0; }
    a { color: #0064e1; } a:hover { color: #0052bc; }
    * { box-sizing: border-box; }
    .wrap {
      --canvas: #eef0f3; --surface: #ffffff; --surface-2: #f5f6f8; --surface-3: #eceef1;
      --label: #1d1d1f; --label-2: #55555e; --label-3: #6b6b76;
      --separator: rgba(60, 60, 67, .12);
      --blue: #0064e1; --blue-press: #0052bc; --blue-soft: rgba(0, 100, 225, .10);
      --green: #34c759; --green-text: #1d8f45;
      --orange: #ff9500; --orange-text: #b25e00;
      --red: #ff3b30; --red-text: #d70015;
      --r-control: 7px; --r-field: 9px; --r-window: 12px; --r-card: 14px; --r-panel: 18px;
      --elev-1: 0 1px 2px rgba(18, 24, 38, .10), 0 0 0 .5px rgba(18, 24, 38, .07);
      --elev-2: 0 10px 30px rgba(18, 24, 38, .12), 0 2px 8px rgba(18, 24, 38, .06), 0 0 0 .5px rgba(18, 24, 38, .05);
      --elev-3: 0 28px 80px rgba(12, 18, 32, .26), 0 8px 24px rgba(12, 18, 32, .12), 0 0 0 .5px rgba(12, 18, 32, .10);
      --t-micro: 120ms; --t-float: 200ms; --t-panel: 320ms; --ease-std: cubic-bezier(.32, .72, 0, 1);
      --wallpaper:
        radial-gradient(900px 560px at 8% -6%,   #ffffff 0%, rgba(255, 255, 255, 0) 55%),
        radial-gradient(760px 520px at 96% 2%,   #bfdcfb 0%, rgba(191, 220, 251, 0) 58%),
        radial-gradient(1000px 720px at 88% 104%, #1b56c9 0%, rgba(27, 86, 201, 0) 60%),
        radial-gradient(620px 460px at 22% 92%,  #7fb3ea 0%, rgba(127, 179, 234, 0) 60%),
        linear-gradient(160deg, #eef3fa 0%, #d9e6f6 50%, #9dbfe6 100%);
      --glass-tint-lens: rgba(255, 255, 255, .06);
      --glass-tint-soft: rgba(247, 249, 253, .60);
      --glass-illum: linear-gradient(180deg, rgba(255, 255, 255, .28) 0%, rgba(255, 255, 255, 0) 42%);
      --glass-rim-base: rgba(255, 255, 255, .50); --glass-rim-catch: rgba(255, 255, 255, .92); --glass-rim-echo: rgba(255, 255, 255, .55);
      --glass-shadow-thin: 0 6px 16px rgba(16, 24, 40, .12), 0 1px 3px rgba(16, 24, 40, .10), 0 0 0 .5px rgba(16, 24, 40, .16);
      --glass-shadow-regular: 0 18px 44px rgba(16, 24, 40, .16), 0 8px 18px rgba(16, 24, 40, .12), 0 2px 5px rgba(16, 24, 40, .09), 0 0 14px rgba(16, 24, 40, .07), 0 0 0 .5px rgba(16, 24, 40, .18);
      --glass-shadow-thick: 0 32px 72px rgba(16, 24, 40, .18), 0 12px 28px rgba(16, 24, 40, .14), 0 2px 6px rgba(16, 24, 40, .10), 0 0 20px rgba(16, 24, 40, .08), 0 0 0 .5px rgba(16, 24, 40, .20);
      --cv-ground:
        radial-gradient(920px 640px at 10% -12%, rgba(255, 255, 255, .62), rgba(255, 255, 255, 0) 62%),
        radial-gradient(820px 560px at 94% 110%, rgba(0, 100, 225, .07), rgba(0, 100, 225, 0) 60%),
        radial-gradient(700px 520px at 78% 4%, rgba(96, 152, 232, .06), rgba(96, 152, 232, 0) 58%);
      --cv-grid-dot: color-mix(in srgb, var(--label-3) 16%, transparent);
      --font: -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", "HarmonyOS Sans SC", "Noto Sans SC", "Microsoft YaHei", system-ui, sans-serif;
      --mono: "SF Mono", ui-monospace, Menlo, Consolas, monospace;
      position: absolute; inset: 0; overflow: hidden;
      background: var(--wallpaper);
      color: var(--label);
      font-family: var(--font);
      font-size: 13px; line-height: 1.5;
      -webkit-font-smoothing: antialiased;
      font-variant-numeric: tabular-nums;
    }
    .wrap[data-appearance="dark"] {
      --canvas: #161618; --surface: #1e1e22; --surface-2: #2a2a30; --surface-3: #33333a;
      --label: #f5f5f7; --label-2: #a8a8b3; --label-3: #8a8a95;
      --separator: rgba(255, 255, 255, .10);
      --blue: #409cff; --blue-press: #1f7fe0; --blue-soft: rgba(64, 156, 255, .16);
      --green-text: #30d158; --orange-text: #ff9f0a; --red-text: #ff453a;
      --elev-1: 0 1px 2px rgba(0, 0, 0, .40), 0 0 0 .5px rgba(255, 255, 255, .08);
      --elev-2: 0 10px 30px rgba(0, 0, 0, .46), 0 2px 8px rgba(0, 0, 0, .30), 0 0 0 .5px rgba(255, 255, 255, .08);
      --elev-3: 0 28px 80px rgba(0, 0, 0, .60), 0 8px 24px rgba(0, 0, 0, .34), 0 0 0 .5px rgba(255, 255, 255, .10);
      --wallpaper:
        radial-gradient(900px 560px at 8% -6%,   #2a3140 0%, rgba(42, 49, 64, 0) 55%),
        radial-gradient(760px 520px at 96% 2%,   #1e3a66 0%, rgba(30, 58, 102, 0) 58%),
        radial-gradient(1000px 720px at 88% 104%, #1b56c9 0%, rgba(27, 86, 201, 0) 60%),
        radial-gradient(620px 460px at 22% 92%,  #234a7d 0%, rgba(35, 74, 125, 0) 60%),
        linear-gradient(160deg, #17181c 0%, #171c26 50%, #142744 100%);
      --glass-tint-lens: rgba(20, 22, 28, .10); --glass-tint-soft: rgba(34, 36, 42, .64);
      --glass-rim-base: rgba(255, 255, 255, .09); --glass-rim-catch: rgba(255, 255, 255, .34); --glass-rim-echo: rgba(255, 255, 255, .20);
      --glass-illum: linear-gradient(180deg, rgba(255, 255, 255, .10) 0%, rgba(255, 255, 255, 0) 42%);
      --glass-shadow-thin: 0 6px 16px rgba(0, 0, 0, .34), 0 1px 3px rgba(0, 0, 0, .30), 0 0 0 .5px rgba(255, 255, 255, .10);
      --glass-shadow-regular: 0 18px 44px rgba(0, 0, 0, .42), 0 8px 18px rgba(0, 0, 0, .30), 0 2px 5px rgba(0, 0, 0, .24), 0 0 0 .5px rgba(255, 255, 255, .10);
      --glass-shadow-thick: 0 32px 72px rgba(0, 0, 0, .50), 0 12px 28px rgba(0, 0, 0, .34), 0 2px 6px rgba(0, 0, 0, .26), 0 0 0 .5px rgba(255, 255, 255, .10);
      --cv-ground:
        radial-gradient(920px 640px at 10% -12%, rgba(255, 255, 255, .05), rgba(255, 255, 255, 0) 62%),
        radial-gradient(820px 560px at 94% 110%, rgba(64, 156, 255, .10), rgba(64, 156, 255, 0) 60%),
        radial-gradient(700px 520px at 78% 4%, rgba(96, 152, 232, .07), rgba(96, 152, 232, 0) 58%);
      --cv-grid-dot: color-mix(in srgb, var(--label-3) 22%, transparent);
      color-scheme: dark;
    }

    /* ---- 玻璃（Web 近似：无 frost-lens.js 即为霜化 + 棱光，与规范一致） ---- */
    .glass { position: relative; border: 0; color: var(--label);
      background: var(--glass-illum), var(--glass-tint-lens);
      -webkit-backdrop-filter: blur(16px) saturate(150%); backdrop-filter: blur(16px) saturate(150%);
      box-shadow: var(--glass-shadow-regular); border-radius: var(--r-card); }
    .glass::after { content: ""; position: absolute; inset: 0; border-radius: inherit; pointer-events: none;
      box-shadow: inset 0 0 0 1px var(--glass-rim-base), inset 1.5px 1.5px 0 -.5px var(--glass-rim-catch), inset -1.5px -1.5px 0 -.5px var(--glass-rim-echo); }
    .glass.is-thin { -webkit-backdrop-filter: blur(10px) saturate(150%); backdrop-filter: blur(10px) saturate(150%); box-shadow: var(--glass-shadow-thin); }
    .glass.is-thick { -webkit-backdrop-filter: blur(24px) saturate(150%); backdrop-filter: blur(24px) saturate(150%); box-shadow: var(--glass-shadow-thick); }
    .glass.is-soft { background: var(--glass-illum), var(--glass-tint-soft); -webkit-backdrop-filter: blur(30px) saturate(150%); backdrop-filter: blur(30px) saturate(150%); }
    .glass.is-soft::after { box-shadow: inset 0 0 0 1px var(--glass-rim-base); }
    .glass.is-flush { border-radius: 0; box-shadow: none; }
    .glass.is-flush::after { display: none; }

    /* ---- 应用外壳：顶栏（霜·thick·flush）+ 画布窗口 ---- */
    .topbar { position: absolute; left: 0; right: 0; top: 0; height: 52px; z-index: 20; display: flex; align-items: center; gap: 16px; padding: 0 20px; user-select: none; box-shadow: inset 0 -.5px 0 var(--separator); }
    .brand { display: flex; align-items: center; gap: 10px; font-weight: 600; letter-spacing: -.01em; font-size: 15px; }
    .brand-mark { width: 22px; height: 22px; display: grid; place-items: center; }
    .brand-mark svg { width: 22px; height: 22px; display: block; }
    .topbar-divider { width: 1px; height: 18px; background: color-mix(in srgb, var(--label-3) 18%, transparent); margin: 0 4px; }
    .breadcrumb { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--label-2); flex: 1; min-width: 0; }
    .breadcrumb .crumb-current { color: var(--label); font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .breadcrumb-sep { color: var(--label-3); }
    .nav-tabs { display: flex; padding: 2px; gap: 2px; background: color-mix(in srgb, var(--separator) 75%, transparent); border-radius: var(--r-field); }
    .nav-tabs a { display: inline-flex; align-items: center; height: 28px; padding: 0 18px; border-radius: var(--r-control); font-size: 13px; font-weight: 500; color: var(--label-2); text-decoration: none; }
    .nav-tabs a.active { background: var(--surface); color: var(--label); font-weight: 600; box-shadow: var(--elev-1); }
    .topbar-actions { display: flex; align-items: center; gap: 10px; }
    .icon-btn { display: grid; place-items: center; width: 32px; height: 32px; border: 0; background: transparent; color: var(--label-2); border-radius: var(--r-control); cursor: pointer; }
    .icon-btn:hover { background: color-mix(in srgb, var(--separator) 67%, transparent); }
    .avatar { width: 28px; height: 28px; border-radius: 50%; display: grid; place-items: center; background: var(--surface-2); color: var(--label-2); font-size: 11px; font-weight: 600; box-shadow: var(--elev-1); }
    .main { position: absolute; left: 0; right: 0; top: 52px; bottom: 0; padding: 12px 14px 14px; }
    .center { position: relative; width: 100%; height: 100%; background: var(--surface); border-radius: var(--r-window); overflow: hidden; box-shadow: var(--elev-2); display: flex; flex-direction: column; }

    /* ---- 画布工具栏（霜·regular + 渐进模糊边） ---- */
    .cv-toolbar { position: relative; z-index: 4; flex: 0 0 auto; display: flex; align-items: center; gap: 12px; min-height: 52px; padding: 10px 16px; }
    .cv-toolbar::before { content: ""; position: absolute; inset: 0 0 -22px 0; z-index: -1; pointer-events: none;
      background: linear-gradient(180deg, var(--surface) 0%, color-mix(in srgb, var(--surface) 70%, transparent) 55%, transparent 100%);
      -webkit-mask: linear-gradient(#000 45%, transparent); mask: linear-gradient(#000 45%, transparent); }
    .cv-toolbar-label { display: inline-flex; align-items: center; gap: 7px; font-size: 13px; font-weight: 600; color: var(--label); flex: 0 0 auto; }
    .cv-toolbar-label svg { color: var(--label-3); }
    .cv-toolbar-sub { font-size: 12px; color: var(--label-3); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .cv-toolbar-sub b { font-weight: 600; color: var(--label-2); }
    .cv-toolbar-sub .is-warn { color: var(--orange-text); font-weight: 600; }
    .cv-toolbar-sub .is-fatal { color: var(--red-text); font-weight: 600; }
    .cv-toolbar-spacer { flex: 1; }
    .cv-zoom { display: inline-flex; align-items: center; gap: 2px; background: var(--surface); border-radius: var(--r-field); padding: 2px; box-shadow: var(--elev-1); }
    .cv-zoom button { display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px; border: 0; background: transparent; color: var(--label-2); border-radius: var(--r-control); cursor: pointer; }
    .cv-zoom-lvl { min-width: 42px; text-align: center; font-size: 12px; color: var(--label); }
    .cv-tool-btn { display: inline-flex; align-items: center; justify-content: center; width: 32px; height: 32px; border: 0; background: var(--surface); color: var(--label-2); border-radius: var(--r-control); box-shadow: var(--elev-1); cursor: pointer; }

    /* ---- 按钮（macOS 白底默认 / 蓝色主按钮 / 幽灵） ---- */
    .btn { display: inline-flex; align-items: center; justify-content: center; gap: 6px; height: 32px; padding: 0 13px; border: 0; border-radius: var(--r-control); font-family: inherit; font-size: 12.5px; font-weight: 600; color: var(--label); background: var(--surface); box-shadow: var(--elev-1); cursor: pointer; white-space: nowrap; }
    .btn:hover { background: var(--surface-2); }
    .btn:active { transform: scale(.97); }
    .btn.is-primary { color: #ffffff; background: linear-gradient(180deg, color-mix(in srgb, var(--blue) 92%, #fff) 0%, var(--blue) 100%); box-shadow: inset 0 1px 0 rgba(255,255,255,.28), var(--elev-1); }
    .btn.is-primary:hover { background: var(--blue-press); }
    .btn.is-primary:disabled { opacity: .45; cursor: not-allowed; }
    .btn.is-ghost { background: transparent; box-shadow: none; color: var(--label-2); }
    .btn.is-ghost:hover { background: var(--blue-soft); color: var(--blue); }
    .btn.is-sm { height: 26px; padding: 0 10px; font-size: 11.5px; }
    .btn svg { flex: 0 0 auto; }
    .btn .n { font-weight: 600; color: var(--label-3); margin-left: 2px; }
    .btn.is-primary .n { color: rgba(255,255,255,.75); }

    /* ---- 画布视口 ---- */
    .canvas-viewport { position: relative; flex: 1; min-height: 0; overflow: hidden;
      background-color: var(--surface-2);
      background-image: radial-gradient(circle, var(--cv-grid-dot) 1px, transparent 1.5px), var(--cv-ground);
      background-size: 24px 24px, auto, auto, auto; background-repeat: repeat, no-repeat, no-repeat, no-repeat; }
    .cv-viewport-hint { position: absolute; left: 16px; top: 16px; z-index: 6; padding: 5px 9px; border-radius: 999px; color: var(--label-3); font-size: 10.5px; line-height: 1.3; pointer-events: none; }
    .cv-world { position: absolute; left: 0; top: 0; }
    .cv-links { position: absolute; left: 0; top: 0; overflow: visible; pointer-events: none; }

    /* ---- 制品卡壳 + 矩阵卡面四行语法 ---- */
    .cv-card { position: absolute; background: var(--surface); border-radius: var(--r-card); box-shadow: var(--elev-1); overflow: hidden; user-select: none; }
    .cv-card.is-face { padding: 13px 14px 14px; width: 232px; }
    .cv-card.is-dim { box-shadow: var(--elev-1); }
    .cv-face-head { display: flex; align-items: center; gap: 7px; margin-bottom: 11px; }
    .cv-face-head > svg { color: var(--label-3); flex: 0 0 auto; }
    .cv-face-name { flex: 1; min-width: 0; font-size: 12px; font-weight: 600; color: var(--label); letter-spacing: -.005em; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .cv-face-state { flex: 0 0 auto; font-size: 11px; color: var(--label-3); white-space: nowrap; }
    .cv-face-hero { display: flex; align-items: baseline; gap: 5px; min-width: 0; }
    .cv-face-hero b { flex: 0 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 27px; font-weight: 600; line-height: 1.1; letter-spacing: -.028em; color: var(--label); }
    .cv-face-hero span { flex: 1 1 auto; min-width: 0; font-size: 11.5px; color: var(--label-3); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .cv-face-hero.is-warn b { color: var(--orange-text); }
    .cv-face-stack { display: flex; gap: 2px; height: 4px; margin: 11px 0 9px; }
    .cv-face-stack i { display: block; height: 100%; min-width: 2px; border-radius: 999px; background: color-mix(in srgb, var(--label) 14%, transparent); }
    .cv-face-stack i.s1 { background: color-mix(in srgb, var(--label) 52%, transparent); }
    .cv-face-stack i.s2 { background: color-mix(in srgb, var(--label) 34%, transparent); }
    .cv-face-stack i.s3 { background: color-mix(in srgb, var(--label) 22%, transparent); }
    .cv-face-stack i.s4 { background: color-mix(in srgb, var(--label) 14%, transparent); }
    .cv-face-stack i.rest { background: color-mix(in srgb, var(--label) 8%, transparent); }
    .cv-face-stack i.done { background: var(--green); }
    .cv-face-stack i.run { background: var(--blue); }
    .cv-face-sig { display: flex; align-items: center; gap: 10px; min-width: 0; font-size: 11.5px; color: var(--label-2); }
    .cv-face-sig > span { --sig: var(--label-3); display: inline-flex; align-items: baseline; gap: 5px; min-width: 0; white-space: nowrap; }
    .cv-face-sig > span::before { content: ""; width: 5px; height: 5px; border-radius: 999px; background: var(--sig); flex: 0 0 auto; transform: translateY(-2px); }
    .cv-face-sig b { font-weight: 600; color: var(--sig); }
    .cv-face-sig .is-mand { --sig: var(--orange-text); }
    .cv-face-sig .is-fatal { --sig: var(--red-text); }
    .cv-face-sig .is-ok { --sig: var(--green-text); }
    .cv-face-sig .is-run { --sig: var(--blue); }
    .cv-face-sig .is-note { display: block; color: var(--label-3); overflow: hidden; text-overflow: ellipsis; }
    .cv-face-sig .is-note::before { display: none; }
    .cv-face-thread { position: absolute; left: 14px; right: 14px; top: 0; height: 2px; border-radius: 999px; background: linear-gradient(90deg, var(--blue) 62%, var(--blue-soft) 62%); }

    /* ---- 章节卡（骨架）：四行语法 + 子节行；健康度徽只在缺口时亮 ---- */
    .ch-col-head { position: absolute; display: flex; align-items: baseline; gap: 8px; font-size: 11px; font-weight: 600; color: var(--label-3); letter-spacing: .04em; white-space: nowrap; }
    .ch-col-head b { font-size: 12px; font-weight: 700; color: var(--label-2); letter-spacing: 0; }
    .ch-card { position: absolute; width: 236px; background: var(--surface); border-radius: var(--r-card); box-shadow: var(--elev-1); overflow: hidden; user-select: none; }
    .ch-card.is-selected { box-shadow: var(--elev-2), 0 0 0 2px var(--blue); }
    .ch-card.is-running { box-shadow: var(--elev-2); }
    .ch-face { padding: 11px 14px 9px; }
    .ch-face .cv-face-head { margin-bottom: 9px; }
    .ch-rows { padding: 0 6px 6px; box-shadow: inset 0 .5px 0 var(--separator); }
    .ch-row { display: flex; align-items: center; gap: 7px; height: 22px; padding: 0 8px; border-radius: 6px; font-size: 11.5px; color: var(--label-2); }
    .ch-row.is-active { background: var(--blue-soft); color: var(--label); font-weight: 600; }
    .ch-row.is-wait { color: var(--label); }
    .ch-row-t { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .ch-row-s { flex: 0 0 auto; font-size: 10.5px; color: var(--label-3); }
    .ch-row-s.is-warn { color: var(--orange-text); font-weight: 600; }
    .ch-row-s.is-fatal { color: var(--red-text); font-weight: 600; }
    .ch-row-s.is-blue { color: var(--blue); font-weight: 600; }
    .dot { display: inline-block; width: 6px; height: 6px; border-radius: 999px; background: var(--label-3); flex: 0 0 auto; }
    .dot.g { background: var(--green); } .dot.b { background: var(--blue); } .dot.o { background: var(--orange); } .dot.r { background: var(--red); } .dot.k { background: color-mix(in srgb, var(--label-3) 45%, transparent); }
    .dot.ring { background: transparent; box-shadow: inset 0 0 0 1.5px var(--blue); }
    .h-badges { display: flex; gap: 8px; margin-top: 6px; font-size: 11px; line-height: 1.3; }
    .h-badge { display: inline-flex; align-items: center; gap: 4px; color: var(--label-3); }
    .h-badge b { font-weight: 600; }
    .h-badge.is-warn { color: var(--orange-text); } .h-badge.is-fatal { color: var(--red-text); }
    .h-badge svg { width: 12px; height: 12px; }

    /* ---- 浮层：Bot 消息窗（min 档 332×56，lens·thick，圆角 20） ---- */
    .cv-msgwin { position: absolute; left: 14px; top: 14px; z-index: 9; width: 332px; height: 56px; border-radius: 20px; display: flex; align-items: center; padding: 10px; padding-left: 57px; }
    .cv-msgwin.is-open { width: 404px; height: 552px; flex-direction: column; align-items: stretch; }
    .cv-msgwin-bot { position: absolute; left: 10px; top: 10px; width: 36px; height: 36px; border-radius: 22.4%; }
    .cv-msgwin-bot svg { display: block; width: 100%; height: 100%; }
    .cv-msgwin-bot.is-busy::after { content: ""; position: absolute; inset: -5px; border-radius: 30%; box-shadow: 0 0 0 1.5px rgba(255,255,255,.7), 0 0 18px rgba(255,255,255,.55); pointer-events: none; }
    .cv-msgwin-ticker { flex: 1; min-width: 0; font-size: 12.5px; color: var(--label-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .cv-msgwin-ticker b { font-weight: 600; color: var(--label); }
    .cv-msgwin-caret { flex: 0 0 auto; color: var(--label-3); margin-left: 6px; }
    .cv-msgwin-head { display: flex; align-items: flex-start; gap: 8px; min-height: 36px; padding-bottom: 2px; }
    .cv-msgwin-title { flex: 1; min-width: 0; display: grid; gap: 1px; }
    .cv-msgwin-name { font-size: 13px; font-weight: 600; line-height: 1.35; letter-spacing: -.012em; color: var(--label); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .cv-msgwin-sub { display: flex; align-items: center; gap: 6px; font-size: 11px; color: var(--label-2); }
    .cv-msgwin-btn { display: grid; place-items: center; width: 26px; height: 26px; border: 0; border-radius: var(--r-control); background: transparent; color: var(--label-2); cursor: pointer; }
    .cv-msgwin-btn:hover { background: color-mix(in srgb, var(--label) 9%, transparent); }
    .cv-msgwin-stream { flex: 1; min-height: 0; overflow: auto; display: flex; flex-direction: column; gap: 12px; padding: 8px 2px 4px 0; }
    .cm-user { align-self: flex-end; max-width: 86%; padding: 9px 13px; border-radius: var(--r-card); background: var(--blue); color: #ffffff; font-size: 13px; line-height: 1.6; }
    .cm-agent { display: flex; flex-direction: column; gap: 8px; font-size: 13px; line-height: 1.7; color: var(--label); }
    .cm-agent p { margin: 0; }
    .cm-agent b { font-weight: 600; }
    .cm-thinking { display: grid; grid-template-columns: 20px 1fr auto; column-gap: 6px; align-items: center; font-size: 12.5px; color: var(--label-2); }
    .cm-thinking svg { color: var(--blue); justify-self: center; }
    .cm-thinking .chev { color: var(--label-3); transform: rotate(-90deg); }
    .cm-tool { display: flex; align-items: center; gap: 8px; min-height: 22px; font-size: 12px; color: var(--label-2); padding-left: 26px; }
    .cm-tool .cnt { margin-left: auto; font-size: 11px; color: var(--label-3); }
    .cm-tool.is-running { color: var(--label); }
    .plan-card { border-radius: var(--r-window); background: color-mix(in srgb, var(--surface) 72%, transparent); box-shadow: inset 0 0 0 .5px var(--separator); padding: 11px 12px; display: flex; flex-direction: column; gap: 8px; }
    .plan-card-h { display: flex; align-items: baseline; gap: 8px; font-size: 12.5px; font-weight: 700; }
    .plan-card-h span { margin-left: auto; font-size: 11px; font-weight: 500; color: var(--label-3); }
    .plan-list { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--label-2); }
    .plan-list div { display: flex; align-items: baseline; gap: 7px; }
    .plan-list .n { width: 16px; color: var(--label-3); flex: 0 0 auto; }
    .plan-list .m { margin-left: auto; color: var(--label-3); font-size: 11px; white-space: nowrap; }
    .plan-actions { display: flex; flex-direction: column; gap: 5px; }
    .plan-actions .opt { display: flex; align-items: center; gap: 8px; height: 30px; padding: 0 10px; border-radius: var(--r-control); background: var(--surface); box-shadow: var(--elev-1); font-size: 12px; font-weight: 600; color: var(--label); }
    .plan-actions .opt.is-primary { color: #fff; background: var(--blue); }
    .plan-actions .opt small { margin-left: auto; font-weight: 500; font-size: 11px; color: var(--label-3); }
    .plan-actions .opt.is-primary small { color: rgba(255,255,255,.75); }
    .plan-done { display: inline-flex; align-items: center; gap: 6px; font-size: 11.5px; color: var(--green-text); font-weight: 600; }

    /* ---- 浮层：子代理看板（右上，300 宽，lens 面板 20） ---- */
    .cv-agentboard { position: absolute; top: 14px; right: 14px; z-index: 9; width: 300px; border-radius: 20px; padding: 11px 11px 10px; display: flex; flex-direction: column; }
    .cv-agentboard-head { padding: 0 2px 8px; font-size: 11px; font-weight: 500; color: var(--label-2); letter-spacing: .04em; }
    .cv-agentboard-list { display: flex; flex-direction: column; gap: 6px; }
    .cv-agentboard-row { display: flex; align-items: center; gap: 9px; padding: 7px 9px; border-radius: var(--r-window); background: color-mix(in srgb, var(--surface) 62%, transparent); box-shadow: inset 0 0 0 .5px var(--separator); }
    .cv-agentboard-row.is-done { opacity: .72; }
    .cv-agentboard-avatar { flex: 0 0 auto; width: 24px; height: 24px; }
    .cv-agentboard-avatar svg { display: block; width: 24px; height: 24px; }
    .cv-agentboard-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
    .cv-agentboard-line1 { display: flex; align-items: center; gap: 8px; }
    .cv-agentboard-desc { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; font-weight: 600; color: var(--label); letter-spacing: -.005em; }
    .cv-agentboard-state { flex: 0 0 auto; display: inline-flex; align-items: center; gap: 5px; font-size: 11px; color: var(--label-3); }
    .cv-agentboard-state .dot { width: 5px; height: 5px; }
    .cv-agentboard-sum { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 11px; color: var(--label-3); }

    /* ---- 浮层：输入坞（底部 18px，宽 min(680, 86%)） ---- */
    .cv-dock { position: absolute; left: 0; right: 0; bottom: 18px; z-index: 8; display: flex; flex-direction: column; align-items: center; gap: 10px; }
    .cv-dock > * { width: min(680px, 86%); }
    .cv-dockbar { display: flex; justify-content: center; gap: 8px; min-height: 32px; }
    .cv-dock-chip { display: inline-flex; align-items: center; gap: 6px; height: 32px; padding: 0 13px; border-radius: 999px; font-size: 12.5px; font-weight: 600; color: var(--label); }
    .cv-dock-chip svg { color: var(--blue); flex: 0 0 auto; }
    .cv-actbar { display: inline-flex; align-items: center; gap: 8px; max-width: 100%; height: 32px; padding: 0 12px; border-radius: 999px; color: var(--label-2); font-size: 12.5px; }
    .cv-actbar .dot { width: 7px; height: 7px; }
    .cv-actbar-text { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .cv-actbar-text b { font-weight: 600; color: var(--label); }
    .cv-actbar svg.chev { color: var(--label-3); transform: rotate(-90deg); }
    .composer { position: relative; background: var(--surface); border-radius: var(--r-card); box-shadow: var(--elev-2); min-height: 104px; padding: 14px 14px 46px; }
    .composer-ph { font-size: 14px; color: var(--label-3); line-height: 1.5; }
    .composer-actions { position: absolute; left: 12px; right: 12px; bottom: 8px; display: flex; gap: 6px; align-items: center; }
    .composer-actions .act { display: inline-flex; align-items: center; gap: 4px; height: 28px; padding: 4px 8px; font-size: 11px; font-weight: 500; color: var(--label-2); border-radius: var(--r-control); background: var(--surface-2); }
    .composer-send { margin-left: auto; display: inline-flex; align-items: center; gap: 5px; height: 28px; padding: 4px 12px; border-radius: var(--r-control); color: #fff; background: var(--blue); font-size: 11.5px; font-weight: 600; box-shadow: inset 0 1px 0 rgba(255,255,255,.28); }

    /* ---- 右侧抽屉（548，实底，elev-3；头 16/18，.5px 接触边） ---- */
    .cv-drawer { position: absolute; inset: 0; z-index: 30; display: flex; justify-content: flex-end; }
    .cv-drawer-scrim { position: absolute; inset: 0; background: color-mix(in srgb, var(--label) 24%, transparent); }
    .cv-drawer-main { position: relative; z-index: 1; width: 548px; height: 100%; display: flex; flex-direction: column; background: var(--surface); box-shadow: var(--elev-3); }
    .cv-drawer-head { display: flex; align-items: center; gap: 11px; padding: 16px 18px; box-shadow: inset 0 -.5px 0 var(--separator); flex: 0 0 auto; }
    .cv-drawer-head > svg { flex: 0 0 auto; color: var(--label-3); }
    .cv-drawer-titlebox { flex: 1; min-width: 0; }
    .cv-drawer-title { font-size: 14.5px; font-weight: 700; color: var(--label); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .cv-drawer-sub { font-size: 11px; color: var(--label-3); margin-top: 1px; }
    .cv-drawer-close { display: grid; place-items: center; width: 32px; height: 32px; flex: 0 0 auto; border: 0; background: var(--surface-2); color: var(--label-2); border-radius: var(--r-control); }
    .cv-drawer-body { flex: 1; min-height: 0; overflow: auto; padding: 18px 20px; }
    .cv-drawer-foot { flex: 0 0 auto; display: flex; align-items: center; gap: 8px; padding: 12px 18px; box-shadow: inset 0 .5px 0 var(--separator); }
    .cv-drawer-foot .note { flex: 1; font-size: 11.5px; color: var(--label-3); }
    .seg { display: flex; gap: 2px; width: max-content; max-width: 100%; padding: 2px; border-radius: var(--r-field); background: color-mix(in srgb, var(--separator) 67%, transparent); }
    .seg button, .seg span { border: 0; background: transparent; font-size: 12px; font-weight: 600; color: var(--label-2); padding: 4px 11px; border-radius: var(--r-control); cursor: pointer; white-space: nowrap; font-family: inherit; }
    .seg .is-active { background: var(--surface); color: var(--label); box-shadow: var(--elev-1); }
    .seg .s-n { color: var(--label-3); font-weight: 600; margin-left: 4px; }
    .gh { display: flex; align-items: baseline; gap: 8px; padding: 18px 0 5px; }
    .gh b { font-size: 12px; font-weight: 700; letter-spacing: -.005em; }
    .gh .n { font-size: 11px; color: var(--label-3); }
    .gh .r { margin-left: auto; font-size: 11px; font-weight: 600; color: var(--label-3); }
    .gh.is-fatal b { color: var(--red-text); } .gh.is-warn b { color: var(--orange-text); }
    .gh svg { width: 13px; height: 13px; align-self: center; }
    .row { display: flex; align-items: flex-start; gap: 10px; padding: 10px 0; border-top: 1px solid var(--separator); }
    .row.is-first { border-top: 0; }
    .row-no { flex: 0 0 auto; min-width: 16px; font-size: 11px; color: var(--label-3); padding-top: 2px; }
    .row-main { flex: 1; min-width: 0; }
    .row-t { display: flex; align-items: baseline; gap: 7px; font-size: 12.5px; font-weight: 500; color: var(--label); }
    .row-t .star { color: var(--orange-text); font-weight: 700; font-size: 11px; }
    .row-d { margin-top: 3px; font-size: 12px; line-height: 1.7; color: var(--label-3); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
    .row-f { display: flex; align-items: center; flex-wrap: wrap; gap: 6px 8px; margin-top: 6px; }
    .chip { display: inline-flex; align-items: center; gap: 4px; font-size: 10.5px; font-weight: 600; color: var(--label-3); box-shadow: inset 0 0 0 .5px var(--separator); padding: 2.5px 9px; border-radius: 999px; white-space: nowrap; }
    .chip.is-blue { color: var(--blue); box-shadow: none; background: var(--blue-soft); }
    .chip svg { width: 11px; height: 11px; }
    .row-side { flex: 0 0 auto; display: flex; align-items: center; gap: 6px; padding-top: 2px; }
    .mark { display: inline-flex; align-items: baseline; gap: 5px; font-size: 11px; color: var(--label-2); white-space: nowrap; }
    .mark::before { content: ""; width: 5px; height: 5px; border-radius: 999px; background: var(--sig, var(--label-3)); flex: 0 0 auto; transform: translateY(-2px); }
    .mark.is-risk { --sig: var(--red); } .mark.is-warn { --sig: var(--orange); } .mark.is-ok { --sig: var(--green); } .mark.is-run { --sig: var(--blue); }
    .act { display: inline-flex; align-items: center; gap: 4px; height: 24px; padding: 0 9px; border-radius: var(--r-control); font-size: 11px; font-weight: 600; color: var(--label-2); background: var(--surface-2); white-space: nowrap; }
    .act.is-primary { color: #fff; background: var(--blue); }
    .act.is-ghost { background: transparent; color: var(--label-3); }

    /* ---- 溯源预览同构：写作台的舞台 + 纸面 ---- */
    .stage { position: absolute; inset: 0; z-index: 30; display: flex; flex-direction: column; background: var(--surface); }
    .stage-head { display: flex; align-items: center; gap: 11px; padding: 12px 18px; box-shadow: inset 0 -.5px 0 var(--separator); flex: 0 0 auto; }
    .stage-body { flex: 1; min-height: 0; display: flex; }
    .paper-stage { flex: 1; min-width: 0; overflow: auto; display: flex; flex-direction: column; align-items: center; padding: 28px 36px 56px; background: var(--surface-3); }
    .sheet { width: min(760px, 100%); padding: 56px 72px 72px; background: var(--surface); border-radius: var(--r-window); box-shadow: var(--elev-1); font-size: 14px; line-height: 1.85; color: var(--label); }
    .sheet h2 { font-size: 18px; font-weight: 700; margin: 0 0 6px; letter-spacing: -.012em; }
    .sheet h3 { font-size: 14.5px; font-weight: 700; margin: 22px 0 6px; }
    .sheet p { margin: 0 0 12px; text-align: justify; }
    .sheet table { width: 100%; border-collapse: collapse; font-size: 12.5px; margin: 6px 0 14px; }
    .sheet th, .sheet td { border: 1px solid color-mix(in srgb, var(--label) 22%, transparent); padding: 5px 8px; text-align: left; vertical-align: top; }
    .sheet th { background: var(--surface-2); font-weight: 600; }
    .anchor { display: inline-flex; align-items: center; gap: 3px; vertical-align: baseline; margin: 0 2px; padding: 0 6px; height: 17px; border-radius: 999px; font-size: 10.5px; font-weight: 600; color: var(--blue); background: var(--blue-soft); white-space: nowrap; }
    .anchor.is-missing { color: var(--orange-text); background: transparent; box-shadow: inset 0 0 0 .5px var(--separator); }
    .sel { background: var(--blue-soft); box-shadow: 0 0 0 2px var(--blue-soft); border-radius: 2px; }
    .brief { flex: 0 0 372px; display: flex; flex-direction: column; background: var(--surface); box-shadow: inset .5px 0 0 var(--separator); }
    .brief-body { flex: 1; min-height: 0; overflow: auto; padding: 14px 18px 18px; }

    /* ---- 就地协商弹层（lens·regular） ---- */
    .pop { position: absolute; z-index: 40; width: 300px; border-radius: var(--r-card); padding: 8px; display: flex; flex-direction: column; gap: 6px; }
    .pop-row { display: flex; align-items: center; gap: 6px; height: 30px; padding: 0 8px; border-radius: 6px; font-size: 12px; font-weight: 500; color: var(--label); }
    .pop-row:hover { background: var(--blue); color: #fff; }
    .pop-row svg { color: var(--label-3); }
    .pop-input { display: flex; align-items: center; gap: 8px; height: 32px; padding: 0 10px; border-radius: var(--r-field); background: var(--surface); box-shadow: var(--elev-1); font-size: 12px; color: var(--label-3); }

    /* ---- 面板/表单（导出） ---- */
    .sheet-modal { position: absolute; z-index: 40; left: 50%; top: 50%; transform: translate(-50%, -50%); width: 760px; background: var(--surface); border-radius: var(--r-panel); box-shadow: var(--elev-3); display: flex; flex-direction: column; overflow: hidden; }
    .field { display: flex; flex-direction: column; gap: 5px; }
    .field label { font-size: 11px; font-weight: 600; color: var(--label-3); letter-spacing: .02em; }
    .select { display: flex; align-items: center; gap: 8px; height: 32px; padding: 0 10px; border-radius: var(--r-field); background: var(--surface); box-shadow: var(--elev-1); font-size: 12.5px; }
    .select svg { margin-left: auto; color: var(--label-3); }
    .kv { display: grid; grid-template-columns: auto 1fr; gap: 4px 14px; font-size: 12px; }
    .kv dt { color: var(--label-3); } .kv dd { margin: 0; color: var(--label); }
    .stepper { display: inline-flex; align-items: center; height: 28px; border-radius: var(--r-control); background: var(--surface-2); }
    .stepper span { min-width: 36px; text-align: center; font-size: 12.5px; font-weight: 600; }
    .stepper i { display: grid; place-items: center; width: 28px; height: 28px; color: var(--label-2); font-style: normal; }
    .check { display: flex; align-items: center; gap: 8px; font-size: 12.5px; }
    .check i { width: 18px; height: 18px; border-radius: 5px; display: grid; place-items: center; box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--label-3) 50%, transparent); font-style: normal; }
    .check i.on { background: var(--blue); box-shadow: none; color: #fff; }

    .hide { display: none !important; }
`;
