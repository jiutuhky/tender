import {
  CasesIcon,
  ClockIcon,
  CredCheckIcon,
  FileIcon,
  GridIcon,
  LayersIcon,
  PenIcon,
  SunIcon,
  TemplateIcon,
  UsersIcon,
} from "@/components/ui/icons";
import { NAV_AGENT, NAV_TYPES } from "@/lib/mock/knowledge";

const TYPE_ICONS = [
  GridIcon,
  FileIcon,
  CasesIcon,
  CredCheckIcon,
  PenIcon,
  TemplateIcon,
  UsersIcon,
];
const AGENT_ICONS = [ClockIcon, LayersIcon, SunIcon];

export function CategoryNav() {
  return (
    /* 嵌入式霜玻璃 chrome：当前被 .page-wrap 实底浮窗包裹（globals.css），壁纸不可透，
       玻璃类按放置矩阵先行标注；contact edge 见 styles.css .page-wrap .nav-side */
    <aside
      className="nav-side frost-glass frost-glass--soft frost-glass--flush"
      data-thick="thick"
    >
      <h5>资料类型</h5>
      {NAV_TYPES.map((entry, i) => {
        const Icon = TYPE_ICONS[i] ?? GridIcon;
        return (
          <div
            key={entry.label}
            className={`nav-item${entry.active ? " active" : ""}`}
          >
            <Icon />
            {entry.label}
            <span className="count">{entry.count.toLocaleString()}</span>
          </div>
        );
      })}

      <h5>智能体入口</h5>
      {NAV_AGENT.map((entry, i) => {
        const Icon = AGENT_ICONS[i] ?? SunIcon;
        return (
          <div key={entry.label} className="nav-item">
            <Icon />
            {entry.label}
            <span className="count">{entry.count}</span>
          </div>
        );
      })}
    </aside>
  );
}
