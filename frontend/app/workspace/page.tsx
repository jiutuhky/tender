import { AppShell } from "@/components/shell/AppShell";
import { TopBar } from "@/components/shell/TopBar";
import { SearchIcon, BellIcon } from "@/components/ui/icons";
import { CanvasPane } from "./_components/canvas/CanvasPane";
import { ResumeBoot } from "./_components/ResumeBoot";
import { ShortScrollbars } from "./_components/ShortScrollbars";

export default async function WorkspacePage({
  searchParams,
}: {
  searchParams: Promise<{ project?: string; name?: string }>;
}) {
  const { project, name } = await searchParams;
  return (
    <AppShell>
      <TopBar
        crumbs={[
          { label: "工作台" },
          { label: "招标文件解析" },
          { label: "结构化信息提取", current: true },
        ]}
        actions={
          <>
            <button className="icon-btn" title="搜索" type="button">
              <SearchIcon />
            </button>
            <button className="icon-btn" title="通知" type="button">
              <BellIcon />
            </button>
          </>
        }
      />

      <div className="main">
        <section className="center">
          {/* 单列：画布铺满整块工作面，对话（消息浮窗 + 底部输入坞）是画布上的浮层。
              .workspace 这层必须保留——globals.css 里 reduced-motion 与 hover:none
              两大块规则都以它为作用域根。 */}
          <div className="workspace">
            <CanvasPane />
          </div>
        </section>
      </div>

      {project && <ResumeBoot pid={project} name={name} />}
      <ShortScrollbars />
    </AppShell>
  );
}
