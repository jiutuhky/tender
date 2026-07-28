"use client";

import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";

// 以 ai-elements 的 `Artifact` 一组组件为蓝本（registry: artifact.tsx）。
// 适配本项目无 Tailwind/shadcn 环境——所有样式由 globals.css 的语义化 className 接管：
//   .artifact / .artifact-header / .artifact-title / .artifact-description
//   .artifact-actions / .artifact-action / .artifact-content / .artifact-close
// 上游 ArtifactAction 的 `icon: LucideIcon` 在本项目换为 `icon?: ReactNode`，
// 因为图标统一从 components/ui/icons 内联 SVG 导入，避免引入 lucide-react 依赖。
//
// 行为与上游对齐：
//   * Artifact* 都是 div/p/button 的薄包装，把额外 className/props 透传。
//   * ArtifactAction 用 button + 内置 aria-label（取自 label || tooltip），
//     无 Tooltip 浮层（本项目暂未提供 Tooltip 组件）—— 用 title 属性当无障碍 fallback。
//   * ArtifactClose 在常驻面板形态下通常不需要，但保留对外导出以保持 API 完整。

function cx(...parts: Array<string | false | undefined | null>): string {
  return parts.filter(Boolean).join(" ");
}

export type ArtifactProps = HTMLAttributes<HTMLDivElement>;

export function Artifact({ className, ...props }: ArtifactProps) {
  return <div className={cx("artifact", className)} {...props} />;
}

export type ArtifactHeaderProps = HTMLAttributes<HTMLDivElement>;

export function ArtifactHeader({ className, ...props }: ArtifactHeaderProps) {
  return <div className={cx("artifact-header", className)} {...props} />;
}

export type ArtifactTitleProps = HTMLAttributes<HTMLParagraphElement>;

export function ArtifactTitle({ className, ...props }: ArtifactTitleProps) {
  return <p className={cx("artifact-title", className)} {...props} />;
}

export type ArtifactDescriptionProps = HTMLAttributes<HTMLParagraphElement>;

export function ArtifactDescription({ className, ...props }: ArtifactDescriptionProps) {
  return <p className={cx("artifact-description", className)} {...props} />;
}

export type ArtifactActionsProps = HTMLAttributes<HTMLDivElement>;

export function ArtifactActions({ className, ...props }: ArtifactActionsProps) {
  return <div className={cx("artifact-actions", className)} {...props} />;
}

export type ArtifactActionProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  /** 悬浮提示文本（无 Tooltip 浮层，用 title 属性承载）。 */
  tooltip?: string;
  /** 屏幕阅读器标签；未设置时回退到 tooltip。 */
  label?: string;
  /** 图标节点；未提供时回退到 children。 */
  icon?: ReactNode;
};

export function ArtifactAction({
  tooltip,
  label,
  icon,
  children,
  className,
  type = "button",
  ...props
}: ArtifactActionProps) {
  const ariaLabel = label ?? tooltip;
  return (
    <button
      className={cx("artifact-action", className)}
      type={type}
      title={tooltip}
      aria-label={ariaLabel}
      {...props}
    >
      {icon ?? children}
    </button>
  );
}

export type ArtifactCloseProps = ButtonHTMLAttributes<HTMLButtonElement>;

export function ArtifactClose({ className, children, type = "button", ...props }: ArtifactCloseProps) {
  return (
    <button
      className={cx("artifact-action", "artifact-close", className)}
      type={type}
      aria-label="关闭"
      {...props}
    >
      {children ?? (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} aria-hidden="true">
          <path d="M6 6l12 12M18 6l-12 12" />
        </svg>
      )}
    </button>
  );
}

export type ArtifactContentProps = HTMLAttributes<HTMLDivElement>;

export function ArtifactContent({ className, ...props }: ArtifactContentProps) {
  return <div className={cx("artifact-content", className)} {...props} />;
}
