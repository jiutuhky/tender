import { AppShell } from "@/components/shell/AppShell";
import { TopBar } from "@/components/shell/TopBar";
import { HomeExperience } from "./_components/HomeExperience";
import "./styles.css";

export default function HomePage() {
  return <AppShell><TopBar crumbs={[{ label: "首页", current: true }]} /><main className="home-page" id="main-content" tabIndex={-1}><HomeExperience /></main></AppShell>;
}
