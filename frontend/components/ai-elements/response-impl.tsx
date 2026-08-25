"use client";

import { memo, type ComponentProps } from "react";
import { Streamdown } from "streamdown";
import { code } from "@streamdown/code";
import { cjk } from "@streamdown/cjk";
import {
  RefreshIcon,
  CheckIcon,
  CopyIcon,
  CornersOutIcon,
  DownloadIcon,
  MagnifyingGlassMinusIcon,
  MagnifyingGlassPlusIcon,
  ShareIcon,
  SpinnerIcon,
  XIcon,
} from "@/components/ui/icons";

// 以 ai-elements 的 `Response` 为蓝本：本质是 `memo`(按 children 相等) + `Streamdown` 薄封装。
// 适配本项目无 Tailwind 环境——不使用 ai-elements 的 `cn`，样式全部由 globals.css 里
// `.cm-markdown [data-streamdown="…"]` 选择器接管（streamdown 给每个元素打了语义化 data 属性）。
//
// 插件：
// - @streamdown/code：Shiki 语法高亮（token 走 inline style，无需 Tailwind 也能上色）+ 内置代码块标头/复制按钮。
// - @streamdown/cjk：修正中文场景下 **加粗** / *强调* 的边界处理（招标文件正文以中文为主）。
//
// icons：streamdown 内置控件图标是 Geist 风格 16 网格，与 Frost 的 Phosphor regular 不同源。
// 用 icons 覆写全部十枚，图标依旧只从 components/ui/icons 这一个载体出。

type ResponseProps = ComponentProps<typeof Streamdown>;

export const ResponseImpl = memo(
  function ResponseImpl({ className, ...props }: ResponseProps) {
    return (
      <Streamdown
        className={className ? `cm-markdown ${className}` : "cm-markdown"}
        plugins={{ code, cjk }}
        shikiTheme={["github-light", "github-dark"]}
        icons={{
          CheckIcon,
          CopyIcon,
          DownloadIcon,
          ExternalLinkIcon: ShareIcon,
          Loader2Icon: SpinnerIcon,
          Maximize2Icon: CornersOutIcon,
          RotateCcwIcon: RefreshIcon,
          XIcon,
          ZoomInIcon: MagnifyingGlassPlusIcon,
          ZoomOutIcon: MagnifyingGlassMinusIcon,
        }}
        // Claude 风格：代码块保留「复制」，去掉下载；表格/图表的控件不显示，保持克制。
        controls={{ code: { copy: true, download: false }, table: false, mermaid: false }}
        lineNumbers={false}
        parseIncompleteMarkdown
        {...props}
      />
    );
  },
  // 流式逐 token 重渲时，children 未变则跳过 reparse（ai-elements 原样保留的关键优化）。
  (prev, next) => prev.children === next.children,
);
