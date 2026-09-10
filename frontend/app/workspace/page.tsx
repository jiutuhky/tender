import { Suspense } from "react";
import { AppShell } from "@/components/shell/AppShell";
import { TopBar } from "@/components/shell/TopBar";
import { CanvasPane } from "./_components/canvas/CanvasPane";
import { ResumeBoot } from "./_components/ResumeBoot";
import { ShortScrollbars } from "./_components/ShortScrollbars";

export default async function WorkspacePage({
  searchParams,
}: {
  searchParams: Promise<{ project?: string; name?: string; demo?: string }>;
}) {
  const { name, demo } = await searchParams;
  return (
    <AppShell>
      <TopBar
        crumbs={[
          { label: "项目", href: "/projects" },
          {
            label: demo === "1" ? "标书编制空间" : name || "工作台",
            current: true,
          },
        ]}
      />

      <main className="workspace-page" id="main-content" tabIndex={-1}>
        {/* 单列：画布铺满整块工作面，对话（消息浮窗 + 底部输入坞）是画布上的浮层。
              .workspace 这层必须保留——globals.css 里 reduced-motion 与 hover:none
              两大块规则都以它为作用域根。 */}
        <div className="workspace">
          <CanvasPane key={demo || "project"} demo={demo === "1"} />
        </div>
      </main>

      <Suspense fallback={null}>
        <ResumeBoot />
      </Suspense>
      <ShortScrollbars />
    </AppShell>
  );
}
