import type { ReactNode } from "react";
import "./shell.css";

export function AppShell({ children }: { children: ReactNode }) {
  return <div className="prose-app"><a className="prose-skip" href="#main-content">跳到主要内容</a>{children}</div>;
}
