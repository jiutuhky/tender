# Frost 设计系统合规治理

目标：前端完全符合 `.claude/skills/frost-design`（Frost 2 凝光）规范；独立审查通过（≤3 轮迭代）。
基线审查：2026-08-24 四维度并行审查（色彩字体 / 玻璃深度 / 圆角动效 / 图标文案），根因四条：
R1 token 手抄三份且漂移 · R2 第二套玻璃体系（LiquidGlass 手搓 blur 面）· R3 图标集为 Feather 血统非 Phosphor · R4 暗色模式缺席。

## 质量门

`pnpm typecheck` + `pnpm lint` + `pnpm build`，外加：

```bash
python3 .scratch/frost-compliance/check-token-cycles.py
```

该脚本检测自引用与循环自定义属性（`--x: var(--x)`、A→B→A）——这类声明会让 token 计算为
guaranteed-invalid，消费点静默落空，且**只在未被下游作用域覆盖的那个外观里发作**（第 1、2 轮各
踩中一次，分别是两节点环与自环）。改动 token 层后必须跑。

## Token 契约（Wave 1 已落地，所有后续修改必须遵守）

- 规范 token 已在 `frontend/app/globals.css` 顶部逐值同步（colors/radius/motion/typography/elevation）；
  材质 token 在 `frontend/app/frost-materials.css`（`@import` 于 globals.css 首行；逐字同步自 skill `tokens/materials.css`）。
- `frontend/public/frost-lens.js` 由 `app/layout.tsx` 以 next/script 全站加载。
- 历史别名（兼容层，新代码一律用规范名）：
  `--bg→--canvas` `--fg→--label` `--fg-2/--muted→--label-2` `--faint/--pending→--label-3`
  `--border→--separator` `--accent→--blue` `--accent-soft→--blue-soft`
  `--success→--green-text` `--warn→--orange-text` `--danger→--red-text` `--running→--blue`
  `--surface-3→--surface-2` `--font-sans/--font-text/--font-serif→--font-ui`
  `--radius-sm→--r-control(7)` `--radius→--r-window(12)` `--radius-lg→--r-card(14)` `--ease-drawer→--ease-std`
- 圆角坡道：control 7 / field 9 / window 12 / card 14 / panel 18 / lens panel 20 / pill 999px / app icon 22.4%；嵌套同心 inner = outer − padding。
- 动效：120/200/320ms；标准曲线 `var(--ease-std)`=cubic-bezier(.32,.72,0,1)；只动 transform/opacity；入场 ≤8px；无限循环仅 running 态 border beam；reduced-motion 下 token 已全局归零。
- 光是白色；蓝只表达可交互/进行中。语义色只用三对 graphic/text token。
- 玻璃：`.frost-glass--lens|--soft` + `data-thick`，放置矩阵见 skill readme；内容面（文档/列表/表格/composer）恒实底；玻璃不叠玻璃；单屏 lens ≤3（超预算按规范降级为 soft 并注释说明）。
- 图标：统一 `components/ui/icons/index.tsx`，全部 Phosphor regular 256 网格内联（fill="currentColor"，官方 path），禁 emoji/Unicode 图形字符。

## 已备案的有意偏离（审查时视为合规，勿再报）

1. `.cv-trace-doc` 溯源面板 serif（Newsreader + Noto Serif SC）——规范明文豁免，已核实无泄漏。
2. `★` 实质性条款记号——招标文件原生记号（frontend/CONTEXT.md 裁定）。
3. 消息窗 open 档执行流落在玻璃上——CONTEXT.md 与 globals.css 备案的有意例外（composer 仍实底）。
4. `⌘K` 等 macOS 键帽字形与密码 `••••••••` 占位——系统惯例，保留。
5. LiquidGlass（真色散折射）承载 msgwin/agentboard 两块 lens thick 面——CONTEXT.md 定稿决策；治理方向是补齐其规范光学层（illum/specular/rim 停靠点）而非替换。
6. 对话阅读字阶 `--fs-chat-*`——规范 Web note（CJK 正文上浮 1–2px）范围内的产品扩展。
7. 暗色模式：token 层与 `[data-appearance="dark"]` 机制已按规范落地；产品尚未提供切换入口（激活入口属产品决策，不属设计系统合规范围）。
8. `traceMotion.ts` 备案的两条规范解释：面板整幅滑入不受「入场 ≤8px」限制（该限约束淡入漂移）；退场用标准曲线的数学镜像 (1,0,.68,.28)。GSAP 动效一律复用该模块（唯一动效常量模块）。
9. `MessageWindow.tsx` 三档浮窗的 width/height 补间——玻璃 backdrop 不能被 opacity<1 / transform 缩放祖先破坏（缩放会扭曲折射），尺寸补间是玻璃约束下的有意取舍，代码内已注释。
10. KaTeX 字体仅在 `.cv-trace-doc` 溯源作用域内生效（当前唯一产出方为 lib/trace/pipeline.ts），@font-face 虽全局注册但不触发下载；扩展数学渲染到对话区前须重新评估。
11. `WechatWorkIcon` / `DingtalkIcon`（`components/ui/icons/index.tsx`）——第三方品牌标识，须保留各自官方字形，不适用 Phosphor 统一；与 `BrandMark`/`ProseBotIcon` 同属品牌类例外。

## 波次与状态

- [x] Wave 1 token 层：globals.css 规范化（色/圆角/动效/字体/字阶/暗色/别名）、frost-materials.css、frost-lens.js、壁纸 `--wallpaper`、Geist 特性移除、reduced-motion 归零
- [x] Wave 2a icons/index.tsx 重建为 Phosphor regular（官方 path，unpkg @phosphor-icons/core@2.1.1）
- [x] Wave 2b globals.css 全量清扫（圆角/时长/缓动/投影/press/颜色 → token；循环动画收敛；1px 分区线 → contact edge / frost-scroll-edge）
- [x] Wave 2c-g 各路由：projects / knowledge / preview / login+home / workspace tsx
- [x] Wave 3 玻璃收编：手搓 blur 面 → .frost-glass；放置矩阵对齐；玻璃叠玻璃与 opacity 祖先修复；LiquidGlass 光学层补齐
- [x] 质量门 pnpm typecheck + pnpm lint + pnpm build（三项全绿）
- [x] 独立审查第 1 轮（四维度全部不通过）→ 已按结论修订
- [x] 独立审查第 2 轮（四维度不通过，仅 1 个 Critical）→ 已按结论修订
- [x] 独立审查第 3 轮（上限）：Critical/High 归零，C 维度通过；A/B/D 各余 Medium 共 8 条 → 已全部修订


## Wave 2b/3 主线补记（globals.css 与玻璃收编）

- 缓动：`--ease-drawer`/旧 `--ease-out`/裸 ease 全部归 `var(--ease-std)`；时长全部归 `--t-micro/float/panel`。
- 循环动画：仅剩 `cv-beam-spin` 与其 `@supports not` 降级 `cv-beam-breathe`（running 态 border beam，规范唯一豁免）。
  bot 光晕/巡视/浮动、sheen 位移、shimmer、run-ripple、agent-breathe 全部改静态表达，孤儿 keyframes 已清。
- 圆角：全部走坡道 token；lens 面板（msgwin min/open、agentboard）统一 20px，AgentBoard.tsx 的 cornerRadius 同步。
- 投影：自造 box-shadow 全部归 `--elev-1/2/3`；主按钮族改规范渐变 + 顶高光 + elevation，去 `#1979f2/#1571e4/rgba(0,80,190…)` 全族。
- 颜色：语义/中性硬编码归 token；头像渐变对齐品牌三停；行内 code 去红改中性；`.cv-icon-tile` 去蓝底；
  `.rv-nature`/`.cm-error-mark` 去彩色填充与光晕（语义色只落文字与图标）。
- 玻璃：`.topbar`/`.artifact-header`/`.cv-toolbar`/`.cv-viewport-hint`/`.cv-dock-chip`/`.composer-sample-menu`
  的手搓 blur/白边/底色全部让位给 `.frost-glass` 工具类（TSX 侧已挂类）；`.ds-return` 改暗色实底 pill；
  两处 scrim 改纯色调光（玻璃不叠玻璃）；`.cv-actbar` 去 `isolation`；reduced-transparency 块收敛为只处理 LiquidGlass 两面（含补齐 `.cv-agentboard-lg`）。
- chrome 分区线：drawer 头/脚、trace modal 头、trace claim 改 `.5px` 接触边；列表内 hairline 按规范保留。
- press 缩放：统一 `.97`（icon 类 `.92`）。
- LiquidGlass：rim/内环改消费 `--glass-rim`/`--glass-rim-inner`，新增 `.lg-illum` 层承载 `--glass-illum` + `--glass-tint-lens`。

## 第 1 轮独立审查结论与修订（四维度均不通过 → 已修）

**色彩**：`.canvas-pane`/`.cv-card.is-face` 的 token 别名与 :root 兼容别名互指成环（`--label: var(--fg)` × `--fg: var(--label)`），
令 green/orange/red 在整个画布内计算为 invalid —— 别名层整体删除，画布直接消费 :root 单源 token。
子代理头像的黄金角色轮（`ProseBotIcon` hue 分支 + `hashHue`）整套移除，回到唯一品牌渐变。
25 处硬编码 `rgba(0,100,225,α)` → 基于 `--blue` 的 `color-mix`/`--blue-soft`（暗色可跟随）。
遗留 `!important` 分类色块（file-icon 四色、tag 绿橙底、check-row 彩底）删除，让位给各路由已做的中性化。
语义色彩色填充全面中性化：`scPair()`、`.rv-nature`、`.cm-error-mark`、preview 三态图标、projects 的 `--success-soft/--warn-soft` 私造档。
蓝作装饰的三处（`.annotation` 蓝底+蓝左线、`.gen-block` 蓝左线、`.cv-chip` 蓝药丸）改中性 + 发丝线。
中性硬编码（`rgba(60,60,67,α)`、`rgba(29,29,31,α)`、白底等）批量归 token。

**玻璃**：顶栏基础层的 1px 分区线撤除、`background: transparent !important` 改 `none` 以放行玻璃 tint/illum；
`.cv-actbar` 手搓白玻璃（1px 白边 + .78 白底 + `--elev-1` + inset 顶高光）整体让位给工具类并补 `--interactive`；
`.cv-toolbar`/`.artifact-header`/`.doc-toolbar` 按放置矩阵改挂 `.frost-scroll-edge`（渐进模糊代替分区线）；
preview 左栏 `.outline` 玻璃化（Outline.tsx 挂类 + 删实底）；agentboard 投影改 thick 档并补 `data-tweening` 软化（规范 rule 4）；
触控断点的玻璃 hover 白底改为取消高光；Bot 运行环与 `.cv-sheen` 光带去蓝改白（蓝光只授予 border beam）。

**圆角/动效**：卡片族 `!important` 从 window(12) 归 card(14)、`.search input` 归 field(9)；
`.icon-btn` press 全局改 `.92`；坡道外 6px/8px/2px/3px 全部归档或标注装饰细件；
`cv-bot-blink` 420ms → `--t-panel`；播报翻牌位移 19px → `--enter-shift`；
自造 box-shadow 归 elevation；玻璃投影改引用 `--glass-shadow-*`（暗色可换挡）；
6 处只写时长未写缓动的 transition 补 `var(--ease-std)`；孤儿 keyframes / `--sheen-dur` / `will-change` / animationDelay 清理。

**图标/文案**：streamdown 内置控件图标经 `icons` prop 全部覆写为 Phosphor（新增 `SpinnerIcon`=circle-notch）；
`ProseBotIcon` 中停对齐品牌 .55；死导出 `PanelRightClose/OpenIcon` 与镜像工厂删除；`.brand-mark` 旧字母标死规则移除；
API 层 16 处英文技术串改中文陈述（技术细节挂 `cause`）、timeline 兜底与矩阵写错误同步；
eyebrow 的 `text-transform: uppercase` 去除（英文标签 Title Case）；三处中文半角括号改全角；`PHASE_STATUS.running` 改 status-first。

## 第 2 轮独立审查结论与修订（四维度不通过 → 已修）

**Critical（唯一）**：`globals.css:22` `--blue-soft: var(--blue-soft)` 自环——浅色外观下所有蓝色浅染态
计算为 invalid（暗色因用字面量重新声明反而正常，恰好躲开常规排查）。已改回字面值，并新增
`check-token-cycles.py` 静态检查纳入质量门。

**色彩**：眉标族（projects/knowledge/preview/home/globals 共 10 处）、模板缩略装饰线、引用计数、
静态提示语的蓝改中性——蓝只表达可交互与进行中；消息窗半透明填充族、看板行、滚动条、文字底光、
内高光共 12 处硬编码白/灰改 `color-mix` 派生，暗色可跟随。

**玻璃**：`.cv-sheen` 整层撤除——它在 `.frost-glass--soft` 的规范 rim 之上又叠了一圈白环 + 辉光，
是光学栈之外的第六、七层；运行态改由规范 rim 与状态文案表达。内容纸面（`.cv-trace-sheet`/`.doc-page`）
的「1px 描边 + 投影」去掉描边，`--elev-1` 自带 .5px 接触环即为其边。

**圆角/动效**：composer 图标钮 hover 自造双层投影归 `--elev-1`；home composer 的彩色 1.5px 实环去除、
坡道外 `scale(1.004)` 移除。

**图标/文案**：`toolLabel` 的 `TaskCreate/Update/List/Get` 拼接与 default 分支不再直出英文工具名；
中文正文半角括号、`PDF/A`、代码块语言标签强制小写一并修正。

**同形重名图标导出**收敛（80→74）：删除未被消费的 CopySmallIcon/EditIcon/StackIcon/EyeOffIcon/
GearIcon/IdentificationCardIcon，保留仍在消费的一侧。

## 第 3 轮独立审查结论与修订（Critical/High 归零；8 条 Medium 已全修）

第 3 轮是 goal 设定的轮数上限。结论：**C 维度（圆角/动效/深度阶）通过**；A/B/D 三维仍各有 Medium，
均为点状可定位的单行到数行修复，无结构性问题。全部已修：

1. `.cv-bullet` 蓝色实环 → `--label-3`（静态项目符号，装饰不消耗彩色）
2. `CanvasLinks.tsx` 连线与锚点 `var(--blue)` → `--label-3`（纯结构装饰）
3. `knowledge/page.tsx` KPI sparkline 描边去蓝
4. `.annotation::before` 的 `var(--accent) !important` → `--label-2`（该 `!important` 此前压掉了 preview 路由已改好的中性值）
5. `TraceModal.tsx` / `CanvasDrawer.tsx` 的内联 `rgba(29,29,31,.24)` 删除，交回 CSS 的 `color-mix(var(--label) 24%)`，
   两处调光档统一为 24%（暗色可跟随；此前 28% 那条从未生效）
6. `.cv-dock-chip`(9px) / `.cv-viewport-hint`(7px) → `999px`，与同格的 `.cv-actbar` 一致（放置矩阵 pill 栏）
7. `timeline.ts` 子代理占位 `"Subagent task"` / `"general-purpose"` → 「子任务准备中」/「通用子代理」
   （Agent 的 args 是流式的，未闭合前这两个兜底会持续渲染到执行流与看板）
8. `lib/store/workspace.ts` 新增 `toUserMessage()`：中文陈述直接用，纯英文技术串（如 `Failed to fetch`）
   兜底为中文，原始异常只进 console

**连带修完的 Low/观察项**：`MATRIX_ACTION_LABEL` 键名对齐（精确文案此前永不命中）、`toolLabel` 的 Agent
分支改中文描述优先、中文内容上的无效 `text-transform: uppercase` 移除 5 处（会拉散中文字距）、
`.doc-page h3` 蓝色大写标题中性化、`.rv-note` 蓝底 → 中性、滚动条灰阶改 `color-mix` 派生、
私造 `var(--blue) 14%` 浅染档 → 规范 `--blue-soft`。

**审查轮数已用满 3 轮**：第 3 轮列出的阻塞项与观察项已 100% 修订，但这些修订本身未再经独立审查复核。

## 收尾验证 + 深/浅主题切换（本轮）

**收尾验证审查**（第 3 轮 8 条修订的确认）：8/8 已落地、无回归；B/C/D 三维**通过**；
A 维余 6 条 Medium，全是前三轮同一模式的遗漏（静态装饰用蓝），已一并修完：
`.cv-spine-tag` 蓝药丸、`SpineCard`/`CardDetail` 内联蓝图标、`.cv-toolbar-label svg`、
`.composer-selection-icon` 蓝底砖、`.cv-det-state.is-positive`（蓝被当作第 4 个语义色）。

## 深/浅主题切换（新增）

- `lib/appearance.ts`：三档偏好（跟随系统 / 浅色 / 深色）+ 订阅式 store（本页选择 / 系统日夜切换 /
  跨标签页 storage 三个来源统一收敛）+ 首帧脚本 `APPEARANCE_BOOT_SCRIPT`（防 FOUC）。
- `components/shell/AppearanceMenu.tsx`：顶栏图标钮 + 凝玻璃 regular 菜单。
  状态走 `useSyncExternalStore`（服务端快照恒浅色，水合后对齐，无水合不一致）。
  **菜单必须 portal 到 body**：留在霜玻璃顶栏子树里会让 backdrop root 落在顶栏上，
  即「玻璃不叠玻璃」——实测 Chromium 会把嵌套的 backdrop-filter 直接算成 none。
- 挂载点：`TopBar`（home/workspace/knowledge/preview）与 `projects` 顶栏。
- 图标新增 Phosphor `moon`（`MoonIcon`），与 `sun`/`circle-half` 配齐三档。

### 连带修复：全站玻璃在现代 Chrome 上失效

Lightning CSS 会把 `backdrop-filter` 与其 `-webkit-` 前缀按 targets 合并，实测**只留前缀版**；
而 Chrome 151 已移除 `-webkit-backdrop-filter`（`CSS.supports` 返回 false），
于是 `.frost-glass` 整层的磨砂与折射全部失效（计算值 `none`）。两处修复：

1. `package.json` + `.browserslistrc` 增加明确 targets（chrome≥111 / edge≥111 / firefox≥121 / safari≥16.4）
   —— **prod 产物**恢复输出标准属性（已验证）。
2. `app/layout.tsx` 内联 `<style>` 补回标准 `backdrop-filter`（dev 的 Turbopack 用固定 targets，
   读不到 browserslist）。该样式不经 CSS 构建管线，dev/prod 都生效；只补 backdrop-filter，
   其余光学层仍由工具类提供，`frost-materials.css` 保持与设计系统源逐字节一致。

浏览器实证：顶栏 `blur(30px) saturate(1.5)`（霜）、菜单 `url(#frost-lens-regular)`（凝·折射）。
