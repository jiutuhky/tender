/** 工作区预览 = 「窗口 zoom」转场目标：Frost 迷你 macOS 窗口（红绿灯工具栏 +
 *  侧栏骨架 + 项目列表）。初始缩小隐藏（gsap autoAlpha 接管）；登录后从中心
 *  放大铺满屏幕，与随后 router.push 的真实 /home 同为冷灰底，衔接无闪。
 *  纯展示，不接真实数据。 */
export function WorkspacePreview() {
  return (
    <div className="lg-file" aria-hidden="true">
      <div className="lg-win-toolbar">
        <span className="lg-traffic">
          <i className="c" />
          <i className="m" />
          <i className="x" />
        </span>
        <span className="lg-win-title">Prose</span>
        <span className="lg-win-sub">在投项目</span>
      </div>

      <div className="lg-win-body">
        <aside className="lg-win-side">
          <div className="s-item active" />
          <div className="s-item" />
          <div className="s-item" />
          <div className="s-item" />
          <div className="s-item" />
        </aside>

        <main className="lg-win-main">
          <h1>在投项目 · 12 项</h1>
          <div className="sub">欢迎回来。今天有 3 份标书临近截止。</div>
          <div className="lg-wk-list">
            <div className="lg-wk-item">
              <div className="name">
                城市轨交仿真平台采购<small>华东设计院</small>
              </div>
              <div className="lg-wk-bar">
                <i style={{ width: "72%" }} />
              </div>
              <div className="score">A · 91.2</div>
              <div className="due">6 月 14 日</div>
            </div>
            <div className="lg-wk-item">
              <div className="name">
                配电网数字孪生服务<small>南方电网</small>
              </div>
              <div className="lg-wk-bar">
                <i style={{ width: "48%" }} />
              </div>
              <div className="score">B · 84.0</div>
              <div className="due">6 月 18 日</div>
            </div>
            <div className="lg-wk-item">
              <div className="name">
                机房热仿真软件开发<small>中数智算</small>
              </div>
              <div className="lg-wk-bar">
                <i style={{ width: "88%" }} />
              </div>
              <div className="score">A · 93.5</div>
              <div className="due">6 月 20 日</div>
            </div>
            <div className="lg-wk-item">
              <div className="name">
                港口调度系统集成<small>北部湾港</small>
              </div>
              <div className="lg-wk-bar">
                <i style={{ width: "35%" }} />
              </div>
              <div className="score">B · 80.7</div>
              <div className="due">6 月 27 日</div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
