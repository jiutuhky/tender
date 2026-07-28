# SmolVM Ops Console — 设计稿

**受众**:后端 SRE / 运维,盯着看沙箱机群健康度。**不是**给产品用户的页面。
**定位**:cockpit 密度、克制、一眼看清「机群是否健康、容量是否吃紧、有没有在冒烟」;视觉与平台 **Prose · Frost(霜)** 设计系统一致。

> 这是运维仪表盘,不是落地页。视觉对齐 Frost:冷灰中性 + 单一系统蓝、玻璃材质做层级、深度代替描边、连续圆角、系统字体栈。默认浅色(与平台一致),提供 Frost 暗色外观切换。字段标识一律简体中文。

## 1. 交付形态(为什么这样选)

- **单文件 `index.html`**:纯 vanilla JS + 内联 CSS,零构建、零 npm 依赖。**Frost token 内联**(颜色/字体/间距/圆角/深度/玻璃)以保持单文件自包含。图标用 Frost 指定的 Phosphor(regular,CDN);缺网时优雅降级(状态用 CSS 语义点承载,不依赖图标字体)。
- **由 hagent server 在 `/ops-console` 提供**:同源 → 免 CORS;API key 在页面里填,走 Bearer。
- **与 `frontend/` 产品工程零耦合**:文件在后端仓库(`src/hagent/server/ops_console/`),不 import 产品前端任何东西,不共享构建。
- **数据来自新增只读 API `/ops/*`**:绝不改状态(只读),与产品 `/sessions` `/messages` 路由分离。

## 2. 数据映射(全部来自现有运行时,非 mock)

| 面板 | 真实来源 |
| --- | --- |
| 生效 provider / 降级链结果 | `preflight_sandbox_kind()` 结果(app 装配时定) |
| 池:size / idle / leased / min / max / 补货熔断 | `SandboxPool.stats()`(新增只读方法) |
| 内存/CPU 准入 | `AdmissionLedger` 的 `mem_capacity_mib` / `mem_in_use_mib` / `cpu_capacity` / `cpu_in_use`(不超卖,spec D7) |
| supervisor 三循环存活 | reaper / health / metrics 线程 `is_alive()` |
| 机群每台沙箱 | `SmolVMManager.list_vms()`(过滤 `hagent-` 前缀)× sessions 表(`sandbox_state`/`node`/`sandbox_snapshot_id`/`last_activity_at`)× 最近一条 `metrics` 事件(CPU/RSS)× `/proc/<pid>` 活性 |
| 会话状态分布 | sessions 表按 `sandbox_state` 聚合 |
| 事件流 | `sandbox_events` 表(created/adopted/paused/resumed/evicted/orphaned/health_fail/reaped/create_failed/metrics/snapshotted/restored/restore_failed),倒序 |

轮询:前端每 N 秒拉 `GET /ops/state`(聚合快照,一次往返)+ `GET /ops/events?limit=`(事件尾)。默认 5s,可在页面切 2s/5s/15s/暂停。

## 3. 信息架构(按 SRE 关注优先级自上而下)

```
┌─ 顶栏 ─────────────────────────────────────────────────────────┐
│ SmolVM Ops · provider=smolvm · ● live · 更新于 12:04:07 · [2s|5s|15s|❚❚] · ⚙ 连接 │
├─ 健康 KPI 条(6 tile,语义色)──────────────────────────────────┤
│ 在租沙箱  暖池 idle/min  内存准入 %  CPU 准入  补货熔断  supervisor 循环 │
├─ 左:容量仪表 ────────────────┬─ 右:会话状态分布 ─────────────┤
│ 内存 in-use / reserved-cap 条  │ running/paused/snapshotted/     │
│ CPU  in-use / overcommit-cap 条│ orphaned/error 计数             │
├─ 机群表(核心,全宽)──────────────────────────────────────────┤
│ session · vm_id · state · node · pid(活?) · CPU% · RSS · idle · snap │
│  (可按列排序;行点开 → 该 VM 的近况 + 事件筛选)                    │
├─ 事件流(全宽,尾随)──────────────────────────────────────────┤
│ 12:04:03  health_fail  hagent-a1b2..  session … 连续探活失败,杀重建   │
│ 12:03:58  snapshotted  hagent-c3d4..  idle 超阈值,已休眠到快照       │
│  (按 kind/severity 上色;可筛 kind、可筛某 session)                 │
└────────────────────────────────────────────────────────────────┘
```

## 4. 视觉系统(对齐 Frost)

- **材质做层级**:唯一半透明层是顶部**玻璃工具栏**(`--mat-toolbar-*`,承 wallpaper);内容面板一律**实心** `--surface`(白/暗灰)+ 深度阴影,永不模糊内容(Frost 铁律)。浅色下 body 铺**冷蓝极光 wallpaper**(macOS 桌面隐喻),内容面板浮于其上。
- **强调色锁**:系统蓝 `--blue #0064E1`(暗色 `#409CFF`)只用于**交互 + 进行中**(选中的刷新档、主按钮、创建中状态)。**语义状态**是独立一套 graphic/text 对:健康 `--green`、告警 `--orange`、故障 `--red`,状态用语义色点承载(Frost 允许)。蓝不花在装饰上。
- **深度代替描边**:三级阴影 `--elev-1/2/3` + .5px 环;区域靠深度分隔,行间才用 hairline `--separator`,不给每行加双边框。
- **形状锁**:Frost 连续圆角 ramp——control 7 < field 9 < card 14 < panel 18;徽章用 pill。
- **字体**:零文本 Web 字体,Frost 系统栈(SF Pro + PingFang SC);数字 `tabular-nums`,数字/虚拟机 id/时间用等宽 `--font-mono`,便于对齐。
- **外观**:默认浅色(与平台一致);顶栏切换到 Frost 暗色外观(`[data-appearance="dark"]`,仅换色 token,组件/圆角/阴影不变),偏好存 localStorage。
- **中文**:字段标识、状态、事件名全部简体中文(状态 `已失联/运行中/游离虚拟机…`、事件 `已创建/健康失败/已休眠…`);vm_id/session_id 等标识符保留原样。

## 5. 交互与状态(全周期,非只画成功态)

- **加载**:骨架块占位(与最终布局同形),不用转圈。
- **空**:「当前无在租沙箱」——并说明 provider=none 时本页无数据、如何切 smolvm。
- **错误**:连接失败 → 顶部内联红条 + 重试按钮 + 提示查 API base/key;不弹 toast 轰炸。
- **反馈**:刷新时顶栏时间戳轻闪;新事件进流时该行淡入(reduced-motion 下关闭)。
- **live 指示**:● 呼吸点(仅此一处动效;`prefers-reduced-motion` 下变静态实心点)。
- **对比度**:语义色在暗底上均过 WCAG AA;徽章文字与底色对比达标。

## 6. 动效预算(Frost:micro 120 / float 200 / panel 320,`cubic-bezier(.32,.72,0,1)`,**无无限循环**)

| 动效 | 理由(一句话) | reduced-motion |
| --- | --- | --- |
| 刷新时间戳一次性闪 | 反馈「刚拉到新数据」 | 关闭 |
| 新事件行入场(≤8px 位移淡入) | 提示「有新事件到达」 | 关闭,直接出现 |
| 容量条宽度过渡 | 反馈用量变化 | 关闭过渡 |
| 按钮 press `scale(.97)` | 触感 | 保留(瞬时) |

live 指示是**静态**语义色点(绿=已连接/橙=已暂停/红=已断开),不做呼吸循环(Frost 禁无限循环)。骨架占位为静态灰块,不做 shimmer 循环。无滚动劫持、无 marquee、无视差。

## 7. 安全边界

- `/ops/*` **只读**:不提供 stop/kill/evict 等破坏性操作(避免误触把线上 VM 干掉;运维要动手走 `hagent sandbox` CLI,有二次确认)。
- 与产品路由同一 `require_api_key`:`HAGENT_API_KEY` 未设(dev)时开放;设了则 Bearer 必需。
- 页面本身(静态壳)可无鉴权拉取(无数据);数据端点鉴权。

## 8. 未来接口预留(不在本次实现)

metrics 时序 sparkline(每 VM CPU/RSS 近 N 点)已在 `/ops/state` 的 per-sandbox 结构里留了 `metrics` 字段位;真正的时序图待 metrics 事件累积后再画。破坏性操作(受控 evict/snapshot)若要做,须走独立带确认的写端点,不混进只读 API。
