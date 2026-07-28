// app.jsx — mount the canvas with the 4 design system artboards.

function App() {
  return (
    <DesignCanvas>
      <DCSection
        id="proposals"
        title="智能标书平台 · Design System 提案"
        subtitle="4 个方向 · 同一份标书,4 种气质 · 横向对比"
      >
        <DCArtboard id="archive" label="A · Archive Editorial · 档案" width={1280} height={2280}>
          <ArchiveSystem />
        </DCArtboard>
        <DCArtboard id="statecraft" label="B · Statecraft · 政务" width={1280} height={2440}>
          <StatecraftSystem />
        </DCArtboard>
        <DCArtboard id="schematic" label="C · Schematic · 蓝图" width={1280} height={2280}>
          <SchematicSystem />
        </DCArtboard>
        <DCArtboard id="quartz" label="D · Quartz · 晶宇" width={1280} height={3640}>
          <QuartzSystem />
        </DCArtboard>

        <DCPostIt top={-110} left={60} width={320} rotate={-2}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>查看真实原型 →</div>
          <div style={{ fontSize: 12, lineHeight: 1.55, marginBottom: 10 }}>
            两套设计已经套到 3 个原型页面里。点下面进去看落地效果(底部有"返回设计系统"小标签)。
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <a href="archive/index.html" style={{ display: "block", padding: "8px 10px", background: "oklch(20% 0.015 60)", color: "oklch(98% 0.004 80)", borderRadius: 4, fontSize: 12, textDecoration: "none", fontStyle: "italic", fontFamily: "Source Serif 4, Newsreader, Georgia, serif" }}>
              <span style={{ background: "oklch(55% 0.12 50)", color: "oklch(98% 0.004 80)", padding: "1px 6px", borderRadius: 99, fontFamily: "Geist Mono, monospace", fontStyle: "normal", fontSize: 10, letterSpacing: "0.12em", marginRight: 8 }}>A</span>
              Archive · 档案 →
            </a>
            <a href="schematic/index.html" style={{ display: "block", padding: "8px 10px", background: "#131c2a", color: "#d2e0f0", borderRadius: 2, fontSize: 12, textDecoration: "none", fontFamily: "IBM Plex Mono, ui-monospace, monospace", border: "1px solid #0f6ad6" }}>
              <span style={{ background: "#0f6ad6", color: "white", padding: "1px 6px", borderRadius: 2, fontSize: 10, letterSpacing: "0.12em", marginRight: 8 }}>C</span>
              schematic · 蓝图 →
            </a>
          </div>
        </DCPostIt>
        <DCPostIt top={-110} left={420} width={260} rotate={1.5}>
          每张 artboard 右上角的扩展按钮可以全屏对比。两套同源,但气质完全不同。
        </DCPostIt>
      </DCSection>
    </DesignCanvas>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
