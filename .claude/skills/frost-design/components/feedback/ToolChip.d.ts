import * as React from "react";

export interface ToolChipProps {
  /** Phosphor icon name (ignored while `running` or `done`). */
  icon?: string;
  label?: React.ReactNode;
  /** Optional trailing monospace datum — a file name, tool id, etc. */
  mono?: React.ReactNode;
  /** Spinning loader + "in progress" reading. */
  running?: boolean;
  /** Green check — completed step. */
  done?: boolean;
  style?: React.CSSProperties;
}

/**
 * The agent execution chip used in the Prose stream to surface a tool call or a
 * completed step (已读取 招标文件.md · 技术需求解析完成). Recessed pill, blue
 * icon, optional mono datum.
 */
export function ToolChip(props: ToolChipProps): JSX.Element;
