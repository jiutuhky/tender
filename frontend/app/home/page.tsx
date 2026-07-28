import { AppShell } from "@/components/shell/AppShell";
import { TopBar } from "@/components/shell/TopBar";
import { BellIcon, SearchIcon } from "@/components/ui/icons";
import { HomeExperience } from "./_components/HomeExperience";
import "./styles.css";

// 登录后的首屏：统一 Agent 入口（自由问答 + 拖入招标文件创建项目）。
export default function HomePage() {
  return (
    <AppShell>
      <TopBar
        crumbs={[{ label: "首页", current: true }]}
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
          <HomeExperience />
        </section>
      </div>
    </AppShell>
  );
}
