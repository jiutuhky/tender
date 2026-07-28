/* Prose · App — composes the macOS Window with the three columns, the toolbar
   (mode segmented + appearance toggle), all on the cold-blue wallpaper. */
(function () {
  const { Window, IconButton, Segmented, Tooltip } = window.FrostDesignSystemProse_5680eb;
  const { useState } = React;
  const data = window.PROSE_DATA;

  function ProseApp() {
    const [project, setProject] = useState("sim");
    const [appearance, setAppearance] = useState("light");
    const activeName = data.projects.find((p) => p.id === project).name;

    function toggleAppearance() {
      const next = appearance === "light" ? "dark" : "light";
      setAppearance(next);
      document.documentElement.setAttribute("data-appearance", next === "dark" ? "dark" : "");
    }

    return (
      <div
        className="frost-wallpaper"
        style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: 40 }}
      >
        <div style={{ width: "min(1180px, 100%)" }}>
          <Window
            title={activeName}
            subtitle="投标文件"
            actions={
              <>
                <Tooltip label="切换侧栏">
                  <IconButton icon="sidebar-simple" label="切换侧栏" />
                </Tooltip>
                <Tooltip label={appearance === "light" ? "深色外观" : "浅色外观"}>
                  <IconButton
                    icon={appearance === "light" ? "moon" : "sun"}
                    label="切换外观"
                    onClick={toggleAppearance}
                  />
                </Tooltip>
                <Segmented options={["编制", "预览", "对照"]} defaultValue="编制" />
              </>
            }
            style={{ height: 640 }}
          >
            <div style={{ display: "grid", gridTemplateColumns: "216px 1fr 296px", flex: 1, minHeight: 0 }}>
              <window.ProseSidebar data={data} activeProject={project} onSelectProject={setProject} />
              <window.ProseAgentStream data={data} />
              <window.ProseDocOutline data={data} />
            </div>
          </Window>
        </div>
      </div>
    );
  }

  window.ProseApp = ProseApp;
})();
