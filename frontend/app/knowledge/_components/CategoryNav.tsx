import {
  CasesIcon,
  ClockIcon,
  CredCheckIcon,
  FileIcon,
  GridIcon,
  LayersIcon,
  PenIcon,
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

function SunIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
    </svg>
  );
}

export function CategoryNav() {
  return (
    <aside className="nav-side">
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
