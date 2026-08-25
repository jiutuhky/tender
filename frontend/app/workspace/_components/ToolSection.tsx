"use client";

import type { ToolCall } from "@/lib/hagent/timeline";
import { TableIcon } from "@/components/ui/icons";
import { toolLabel } from "./toolLabel";

// 复用设计稿的 .cm-tool-section / .cm-tool-header / .cm-tool-results / .cm-result 结构，
// 仅把数据源换成真实工具调用。不新增样式类。
export function ToolSection({ call }: { call: ToolCall }) {
  const running = call.status === "running";
  const result = (call.result || "").trim();
  return (
    <div className={`cm-tool-section${running ? " is-running" : ""}`}>
      <div className="cm-tool-header">
        <div className="cm-tool-query">{toolLabel(call)}</div>
        <div className="cm-tool-count">{running ? "运行中" : "已完成"}</div>
        {running && <div className="cm-spinner" />}
      </div>
      {!running && result && (
        <div className="cm-tool-results">
          <div className="cm-result">
            <div className="cm-result-icon">
              <TableIcon aria-hidden="true" />
            </div>
            <div className="cm-result-title">{clip(result)}</div>
            <div className="cm-result-meta">结果</div>
          </div>
        </div>
      )}
    </div>
  );
}

function clip(s: string): string {
  const oneLine = s.replace(/\s+/g, " ").trim();
  return oneLine.length > 160 ? `${oneLine.slice(0, 160)}…` : oneLine;
}
