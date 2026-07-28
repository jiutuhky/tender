import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

const stroke: Partial<IconProps> = {
  fill: "none",
  stroke: "currentColor",
};

export function SearchIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6} {...props}>
      <circle cx="11" cy="11" r="7" />
      <path d="M21 21l-4.35-4.35" />
    </svg>
  );
}

export function BellIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6} {...props}>
      <path d="M18 8a6 6 0 1 0-12 0c0 7-3 8-3 8h18s-3-1-3-8" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  );
}

export function PauseIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6} {...props}>
      <rect x="6" y="5" width="4" height="14" rx="1" />
      <rect x="14" y="5" width="4" height="14" rx="1" />
    </svg>
  );
}

export function CopyIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6} {...props}>
      <rect x="9" y="9" width="13" height="13" rx="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}

export function PlusIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.8} {...props}>
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}

export function UploadIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6} {...props}>
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12" />
    </svg>
  );
}

export function ShareIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6} {...props}>
      <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8" />
      <path d="M16 6l-4-4-4 4M12 2v13" />
    </svg>
  );
}

export function DownloadIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.8} {...props}>
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" />
    </svg>
  );
}

export function EditIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 16 16" {...stroke} strokeWidth={1.5} {...props}>
      <path d="M11 2l3 3-8 8H3v-3l8-8z" />
    </svg>
  );
}

export function CopySmallIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 16 16" {...stroke} strokeWidth={1.5} {...props}>
      <rect x="5" y="5" width="9" height="9" rx="1.5" />
      <path d="M11 5V3a1 1 0 00-1-1H3a1 1 0 00-1 1v7a1 1 0 001 1h2" />
    </svg>
  );
}

export function ResultBadgeIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 16 16" {...stroke} strokeWidth={1.6} {...props}>
      <path d="M2 4h12v9H2zM2 7h12" />
    </svg>
  );
}

export function GridIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6} {...props}>
      <rect x="3" y="3" width="7" height="7" />
      <rect x="14" y="3" width="7" height="7" />
      <rect x="3" y="14" width="7" height="7" />
      <rect x="14" y="14" width="7" height="7" />
    </svg>
  );
}

export function FileIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6} {...props}>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
    </svg>
  );
}

export function CasesIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6} {...props}>
      <path d="M20 7h-9M14 17H5M5 7a3 3 0 1 0 6 0 3 3 0 0 0-6 0zM13 17a3 3 0 1 0 6 0 3 3 0 0 0-6 0z" />
    </svg>
  );
}

export function CredCheckIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6} {...props}>
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14M22 4L12 14.01l-3-3" />
    </svg>
  );
}

export function PenIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6} {...props}>
      <path d="M12 20h9M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
    </svg>
  );
}

export function TemplateIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6} {...props}>
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <path d="M9 3v18M3 9h18" />
    </svg>
  );
}

export function UsersIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6} {...props}>
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  );
}

export function ClockIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6} {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 3" />
    </svg>
  );
}

export function LayersIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6} {...props}>
      <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
    </svg>
  );
}

export function ArrowRightIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.8} {...props}>
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  );
}

export function ChevronIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 12 12" {...stroke} strokeWidth={1.8} {...props}>
      <path d="M3 4.5l3 3 3-3" />
    </svg>
  );
}

export function ChevronLeftIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 16 16" {...stroke} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M10 3l-5 5 5 5" />
    </svg>
  );
}

export function ChevronRightIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 16 16" {...stroke} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M6 3l5 5-5 5" />
    </svg>
  );
}

// 右侧面板收起：边框 + 实心右栏 + 箭头指向右（收起方向）。
export function PanelRightCloseIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" {...props}>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M15 4v16" />
      <path d="M10 9l3 3-3 3" />
    </svg>
  );
}

// 右侧面板展开：箭头指向左（展开方向）。
export function PanelRightOpenIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" {...props}>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M15 4v16" />
      <path d="M13 9l-3 3 3 3" />
    </svg>
  );
}

export function EyeIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 16 16" {...stroke} strokeWidth={1.4} {...props}>
      <path d="M1.5 8s2.5-4.5 6.5-4.5S14.5 8 14.5 8 12 12.5 8 12.5 1.5 8 1.5 8z" />
      <circle cx="8" cy="8" r="2" />
    </svg>
  );
}

export function EyeOffIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 16 16" {...stroke} strokeWidth={1.4} {...props}>
      <path d="M6.5 3.7A6.6 6.6 0 0 1 8 3.5C12 3.5 14.5 8 14.5 8a12 12 0 0 1-2 2.6M3.5 5.4A12.5 12.5 0 0 0 1.5 8S4 12.5 8 12.5c.6 0 1.2-.07 1.7-.2" />
      <path d="M6.6 6.6a2 2 0 0 0 2.8 2.8" />
      <path d="M2 2l12 12" />
    </svg>
  );
}

export function WechatWorkIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 16 16" fill="currentColor" {...props}>
      <path d="M5.8 2.2C3 2.2.7 4 .7 6.3c0 1.3.7 2.5 1.9 3.3l-.5 1.6 1.9-.9c.6.2 1.2.3 1.8.3.2 0 .4 0 .5-.03A4 4 0 0 1 6 9.5c0-2.3 2.2-4.1 5-4.1.2 0 .4 0 .6.03C11.2 3.5 8.7 2.2 5.8 2.2zM3.7 5.4a.7.7 0 1 1 0-1.4.7.7 0 0 1 0 1.4zm4.2 0a.7.7 0 1 1 0-1.4.7.7 0 0 1 0 1.4z" />
      <path d="M15.3 9.5c0-1.9-1.9-3.4-4.3-3.4S6.7 7.6 6.7 9.5c0 1.9 1.9 3.4 4.3 3.4.5 0 1-.07 1.5-.2l1.6.8-.4-1.3c1-.7 1.6-1.7 1.6-2.7zM9.7 9a.6.6 0 1 1 0-1.2.6.6 0 0 1 0 1.2zm2.6 0a.6.6 0 1 1 0-1.2.6.6 0 0 1 0 1.2z" />
    </svg>
  );
}

export function DingtalkIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 16 16" fill="currentColor" {...props}>
      <path d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1zm3.4 5.4l-1.5 3.4h1.2l-2.7 3.8L9 10.4H7.8l1.6-2.5c-.6 0-1.5-.2-2.6-1 0 0 .8.2 1.6 0 .9-.2 1.5-.7 1.5-.7L8 5.3l3.4 1.1z" />
    </svg>
  );
}

export function SsoIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 16 16" {...stroke} strokeWidth={1.4} {...props}>
      <path d="M8 1.5l5.5 2.5v4.5c0 3-2.2 5.5-5.5 6-3.3-.5-5.5-3-5.5-6V4l5.5-2.5z" />
      <path d="M5.5 8l2 2 3-3.5" />
    </svg>
  );
}

// 工具调用块的头图标：开口扳手。与 SparkIcon 同尺寸（viewBox 32），
// 静态 SVG；激活态由外层 `.cm-tools-spark.is-active` 的 CSS pulse 提供。
export function WrenchIcon(props: IconProps) {
  return (
    <svg
      viewBox="0 0 32 32"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <path d="M22.2 6.4a5.2 5.2 0 0 0-6.8 6.8L7 21.6a1.6 1.6 0 0 0 0 2.26l1.14 1.14a1.6 1.6 0 0 0 2.26 0l8.4-8.4a5.2 5.2 0 0 0 6.8-6.8l-2.94 2.94-2.66-.34-.34-2.66z" />
    </svg>
  );
}

// `animated` 控制是否渲染 SMIL `<animate>` 子元素。SMIL 动画无法用 CSS 暂停，
// 所以「静态」靠直接不渲染动画元素实现——图标定格为静态原子图形（轨道虚线 + 电子停在起点）。
// 默认 true：不传 prop 的调用方（如登录页 logo）行为不变；思考块按需传 animated={active}。
export function SparkIcon({ animated = true, ...props }: IconProps & { animated?: boolean }) {
  const orbit = (rx: number, dash: string, opacity: number, dur: string, to: string) => (
    <ellipse
      cx="16"
      cy="16"
      rx={rx}
      ry="4.2"
      stroke="currentColor"
      strokeWidth="1.2"
      strokeLinecap="round"
      pathLength={100}
      strokeDasharray={dash}
      opacity={opacity}
    >
      {animated && (
        <animate attributeName="stroke-dashoffset" dur={dur} from="0" to={to} repeatCount="indefinite" />
      )}
    </ellipse>
  );
  return (
    <svg viewBox="0 0 32 32" fill="none" {...props}>
      <g transform="rotate(28 16 16)">
        {orbit(11.5, "55 45", 0.15, "1.2s", "-100")}
        {orbit(11.5, "28 72", 0.35, "1.2s", "-100")}
        {orbit(11.5, "8 92", 0.75, "1.2s", "-100")}
        <circle r="1.5" fill="currentColor" cx={animated ? undefined : 27.5} cy={animated ? undefined : 16}>
          {animated && (
            <animateMotion
              dur="1.2s"
              begin="-0.096s"
              repeatCount="indefinite"
              path="M 27.5 16 A 11.5 4.2 0 1 1 4.5 16 A 11.5 4.2 0 1 1 27.5 16"
            />
          )}
        </circle>
      </g>
      <g transform="rotate(-28 16 16)">
        {orbit(11.5, "55 45", 0.15, "1.6s", "100")}
        {orbit(11.5, "28 72", 0.35, "1.6s", "100")}
        {orbit(11.5, "8 92", 0.75, "1.6s", "100")}
        <circle r="1.5" fill="currentColor" cx={animated ? undefined : 4.5} cy={animated ? undefined : 16}>
          {animated && (
            <animateMotion
              dur="1.6s"
              begin="-1.504s"
              repeatCount="indefinite"
              path="M 4.5 16 A 11.5 4.2 0 1 0 27.5 16 A 11.5 4.2 0 1 0 4.5 16"
            />
          )}
        </circle>
      </g>
      <circle cx="16" cy="16" r="5" fill="currentColor" />
    </svg>
  );
}

export function BracesIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6} {...props}>
      <path d="M8 4H7a2 2 0 0 0-2 2v3.5c0 1-.6 2-1.8 2.5 1.2.5 1.8 1.5 1.8 2.5V18a2 2 0 0 0 2 2h1" />
      <path d="M16 4h1a2 2 0 0 1 2 2v3.5c0 1 .6 2 1.8 2.5-1.2.5-1.8 1.5-1.8 2.5V18a2 2 0 0 1-2 2h-1" />
    </svg>
  );
}

export function MinusIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.8} {...props}>
      <path d="M5 12h14" />
    </svg>
  );
}

// 缩放-适应：四角取景框。
export function FrameIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M3 8V5a2 2 0 0 1 2-2h3M16 3h3a2 2 0 0 1 2 2v3M21 16v3a2 2 0 0 1-2 2h-3M8 21H5a2 2 0 0 1-2-2v-3" />
    </svg>
  );
}

// 消息浮窗「放大」：四角向外（对照 Phosphor corners-out）。
export function CornersOutIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M15 3h6v6M21 3l-7 7M9 21H3v-6M3 21l7-7" />
    </svg>
  );
}

// 消息浮窗「还原」：四角向内（对照 Phosphor corners-in）。
export function CornersInIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M20 10h-6V4M14 10l7-7M4 14h6v6M10 14l-7 7" />
    </svg>
  );
}

// HUD「合成」：两支汇流向下。
export function MergeIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M5 4v5a4 4 0 0 0 4 4h6M19 4v5a4 4 0 0 1-4 4M12 13v7M9 17l3 3 3-3" />
    </svg>
  );
}

// 评分维度：柱状图。
export function ChartBarIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M3 21h18M6 21V11M11 21V6M16 21V14" />
    </svg>
  );
}

// 技术维度：齿轮。
export function GearIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" {...props}>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  );
}

// ===== 工作台画布（大纲视图）专用图标 =====

// 制品卡：技术需求清单（带项目符号的清单）
export function ListDashesIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M8 6h13M8 12h13M8 18h13" />
      <path d="M3.5 6h.01M3.5 12h.01M3.5 18h.01" />
    </svg>
  );
}

// 制品卡：应答矩阵（表格）
export function TableIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" {...props}>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M3 9.5h18M3 14.5h18M9 4v16" />
    </svg>
  );
}

// 制品卡：技术偏差表（双行）
export function RowsIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" {...props}>
      <rect x="3" y="4.5" width="18" height="6.5" rx="1.5" />
      <rect x="3" y="13" width="18" height="6.5" rx="1.5" />
    </svg>
  );
}

// 制品卡 / 主轴：投标大纲（组织树）
export function TreeStructureIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" {...props}>
      <rect x="8.5" y="3" width="7" height="5" rx="1.5" />
      <rect x="2" y="16" width="7" height="5" rx="1.5" />
      <rect x="15" y="16" width="7" height="5" rx="1.5" />
      <path d="M12 8v3M5.5 16v-2.5a1 1 0 0 1 1-1h11a1 1 0 0 1 1 1V16" />
    </svg>
  );
}

// 制品卡：投标文件·成稿（多文档）
export function FilesIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M16 5h1a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2v-1" />
      <rect x="3" y="3" width="11" height="14" rx="2" />
    </svg>
  );
}

// 工具栏：重置画布（逆时针）
export function RefreshCcwIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M3 12a9 9 0 1 0 2.6-6.4L3 8" />
      <path d="M3 3v5h5" />
    </svg>
  );
}

// 抽屉：重新生成（顺时针双箭头）
export function RefreshIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M21 12a9 9 0 1 1-2.6-6.4L21 8" />
      <path d="M21 3v5h-5" />
    </svg>
  );
}

// 抽屉 / 原文面板：关闭（X）
export function XIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.7} strokeLinecap="round" {...props}>
      <path d="M6 6l12 12M18 6L6 18" />
    </svg>
  );
}

// 抽屉：更多（横向三点）
export function DotsThreeIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" {...props}>
      <circle cx="5" cy="12" r="1.6" />
      <circle cx="12" cy="12" r="1.6" />
      <circle cx="19" cy="12" r="1.6" />
    </svg>
  );
}

// 首页统一入口：添加招标文件（回形针）
export function PaperclipIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M17.6 8l-7.2 7.2a2.1 2.1 0 003 3l7.3-7.4a4.5 4.5 0 00-6.4-6.4l-7.3 7.4a6.9 6.9 0 009.7 9.7l5.5-5.5" />
    </svg>
  );
}

// 画布底部 composer：发送（上箭头）
export function ArrowUpIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M12 19V5M6 11l6-6 6 6" />
    </svg>
  );
}

// 知识库素材：资质证照
export function IdCardIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" {...props}>
      <rect x="2" y="5" width="20" height="14" rx="2" />
      <circle cx="8" cy="11" r="2" />
      <path d="M5 16c0-1.7 1.3-3 3-3s3 1.3 3 3" />
      <path d="M14 10h5M14 13.5h4" />
    </svg>
  );
}

// 知识库素材：业绩案例（楼宇）
export function BuildingsIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M3 21h18" />
      <path d="M4 21V8h7v13M13 21V3h7v18" />
      <path d="M7 12h.01M7 15.5h.01M16 7h.01M16 11h.01M16 15h.01" />
    </svg>
  );
}

// 成稿章节：进行中（半填充圆）
export function CircleHalfIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 3a9 9 0 0 1 0 18z" fill="currentColor" stroke="none" />
    </svg>
  );
}

// 成稿章节：待补（虚线圆）
export function CircleDashedIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6} strokeDasharray="3 3.4" {...props}>
      <circle cx="12" cy="12" r="9" />
    </svg>
  );
}

/** Frost 品牌标：三页层叠玻璃纸 squircle（多色填充，不走 currentColor） */
export function BrandMark(props: IconProps) {
  return (
    <svg viewBox="0 0 120 120" aria-hidden="true" {...props}>
      <defs>
        <linearGradient id="frost-mark-grad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#5fb0ff" />
          <stop offset=".55" stopColor="#1670ec" />
          <stop offset="1" stopColor="#0a3fa8" />
        </linearGradient>
      </defs>
      <rect width="120" height="120" rx="27" fill="url(#frost-mark-grad)" />
      <rect x="26" y="36" width="68" height="48" rx="8" fill="#ffffff" opacity=".5" />
      <rect x="22" y="25" width="76" height="52" rx="9" fill="#ffffff" />
      <rect x="34" y="38" width="40" height="5" rx="2.5" fill="#1670ec" />
      <rect x="34" y="50" width="52" height="4" rx="2" fill="#9cc4f5" />
      <rect x="34" y="60" width="46" height="4" rx="2" fill="#9cc4f5" />
    </svg>
  );
}
