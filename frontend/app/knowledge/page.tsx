import { AppShell } from "@/components/shell/AppShell";
import { TopBar } from "@/components/shell/TopBar";
import { KnowledgeLibrary } from "./_components/KnowledgeLibrary";
import "./styles.css";

export default function KnowledgePage() {
  return <AppShell><TopBar crumbs={[]} /><main className="knowledge-page" id="main-content" tabIndex={-1}><KnowledgeLibrary /></main></AppShell>;
}
