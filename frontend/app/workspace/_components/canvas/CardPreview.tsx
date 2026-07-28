import { Chip, Dot } from "./bits";
import { dotColor, isMatrixCardType, type CardType, type StatusColor } from "./cardMeta";
import { MatrixCardPreview } from "./matrixViews";
import { BuildingsIcon, FileIcon, IdCardIcon } from "@/components/ui/icons";

// 制品卡正文（紧凑预览）。逐型号还原 .design 原型的 preview()。
// 维持原型的内联排版（一次性微版式 + 动态宽度/色值），token 走画布作用域 CSS 变量。

const KNOWLEDGE_ICON = { idcard: IdCardIcon, buildings: BuildingsIcon, files: FileIcon } as const;

function Bar({ fill, color = "var(--blue)", track = 6 }: { fill: number; color?: string; track?: number }) {
  return (
    <div style={{ flex: 1, height: track, borderRadius: 999, background: "var(--surface-2)", overflow: "hidden" }}>
      <div style={{ width: `${fill * 100}%`, height: "100%", background: color, borderRadius: 999 }} />
    </div>
  );
}

export function CardPreview({ type }: { type: CardType }) {
  // 真实矩阵卡:数据订阅自 store,委托专用预览组件
  if (isMatrixCardType(type)) return <MatrixCardPreview type={type} />;
  switch (type) {
    case "req": {
      const cats: Array<[string, number, number]> = [
        ["功能", 18, 0.9],
        ["性能", 9, 0.5],
        ["接口", 7, 0.4],
        ["安全", 11, 0.62],
      ];
      return (
        <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
          {cats.map(([name, count, ratio]) => (
            <div key={name} style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ width: 30, fontSize: 11, color: "var(--label-2)" }}>{name}</span>
              <Bar fill={ratio} />
              <span
                style={{ width: 18, textAlign: "right", fontSize: 11, fontVariantNumeric: "tabular-nums", color: "var(--label-3)" }}
              >
                {count}
              </span>
            </div>
          ))}
          <div style={{ marginTop: 1, fontSize: 11, color: "var(--label-3)" }}>
            实质性条款 <b style={{ color: "var(--orange-text)" }}>6</b> 项
          </div>
        </div>
      );
    }
    case "matrix": {
      const rows: Array<[string, string, StatusColor]> = [
        ["多物理场耦合", "满足", "green"],
        ["1000万网格规模", "满足", "green"],
        ["PLM 系统接口", "部分", "orange"],
      ];
      return (
        <div>
          <div style={{ display: "flex", fontSize: 10.5, color: "var(--label-3)", paddingBottom: 4 }}>
            <span style={{ flex: 1 }}>需求条目</span>
            <span style={{ width: 42 }}>响应</span>
            <span style={{ width: 26, textAlign: "right" }}>偏离</span>
          </div>
          {rows.map(([item, resp, sc]) => (
            <div
              key={item}
              style={{ display: "flex", alignItems: "center", padding: "5px 0", borderTop: "1px solid var(--separator)", fontSize: 11.5 }}
            >
              <span style={{ flex: 1, color: "var(--label)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {item}
              </span>
              <span style={{ width: 42, color: "var(--label-2)" }}>{resp}</span>
              <span style={{ width: 26, display: "flex", justifyContent: "flex-end" }}>
                <Dot sc={sc} />
              </span>
            </div>
          ))}
          <div style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 7, fontSize: 10.5, color: "var(--blue)" }}>
            生成 32 / 45
            <Bar fill={0.71} track={4} />
          </div>
        </div>
      );
    }
    case "outline": {
      const items: Array<[string, StatusColor]> = [
        ["一  投标函与附录", "green"],
        ["二  商务及报价响应", "green"],
        ["三  技术方案", "blue"],
        ["四  项目实施与服务", "gray"],
        ["五  资质证明材料", "green"],
      ];
      return (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {items.map(([t, sc]) => (
            <div key={t} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11.5, color: "var(--label)" }}>
              <Dot sc={sc} />
              <span style={{ flex: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{t}</span>
            </div>
          ))}
          <div style={{ marginTop: 1, fontSize: 11, color: "var(--label-3)" }}>共 8 章 · 引用 12 处</div>
        </div>
      );
    }
    case "chapter":
      return (
        <div>
          <div style={{ fontSize: 12, fontWeight: 600, color: "var(--label)", marginBottom: 7 }}>3.1  总体技术架构</div>
          {[0.94, 0.99, 0.72].map((w, i) => (
            <div
              key={i}
              style={{ height: 7, borderRadius: 999, background: "var(--surface-2)", width: `${w * 100}%`, marginBottom: 6 }}
            />
          ))}
          <div style={{ display: "flex", gap: 5, marginTop: 4 }}>
            <Chip>业绩 A-203</Chip>
            <Chip>ISO9001</Chip>
            <Chip>+4</Chip>
          </div>
        </div>
      );
    case "knowledge": {
      const rows: Array<[keyof typeof KNOWLEDGE_ICON, string, number]> = [
        ["idcard", "资质证照", 12],
        ["buildings", "业绩案例", 8],
        ["files", "人员简历", 15],
      ];
      return (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {rows.map(([iconKey, label, count]) => {
            const Icon = KNOWLEDGE_ICON[iconKey];
            return (
              <div key={label} style={{ display: "flex", alignItems: "center", gap: 9 }}>
                <span className="cv-knol-icon">
                  <Icon width={13} height={13} />
                </span>
                <span style={{ flex: 1, fontSize: 12, color: "var(--label)" }}>{label}</span>
                <span className="cv-knol-count">{count}</span>
              </div>
            );
          })}
        </div>
      );
    }
    case "chart": {
      const bars: Array<[number, number, StatusColor]> = [
        [0, 0.5, "blue"],
        [0.18, 0.46, "blue"],
        [0.4, 0.4, "green"],
        [0.56, 0.42, "gray"],
      ];
      return (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {bars.map(([left, width, sc], i) => (
            <div key={i} style={{ height: 8, borderRadius: 999, background: "var(--surface-2)", position: "relative" }}>
              <div
                style={{
                  position: "absolute",
                  top: 0,
                  bottom: 0,
                  left: `${left * 100}%`,
                  width: `${width * 100}%`,
                  borderRadius: 999,
                  background: dotColor(sc),
                  opacity: sc === "gray" ? 0.45 : 0.9,
                }}
              />
            </div>
          ))}
          <div style={{ fontSize: 10.5, color: "var(--label-3)", marginTop: 1 }}>实施周期 6 个月 · 4 里程碑</div>
        </div>
      );
    }
    case "deviation": {
      const rows: Array<[string, string, StatusColor]> = [
        ["国产化适配", "正偏离", "blue"],
        ["接口协议版本", "负偏离", "orange"],
        ["响应时限", "无偏离", "green"],
      ];
      return (
        <div>
          {rows.map(([item, label, sc], i) => (
            <div
              key={item}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "6px 0",
                borderTop: i ? "1px solid var(--separator)" : "none",
                fontSize: 11.5,
              }}
            >
              <span style={{ flex: 1, color: "var(--label)" }}>{item}</span>
              <Dot sc={sc} />
              <span style={{ fontSize: 11, color: "var(--label-2)" }}>{label}</span>
            </div>
          ))}
        </div>
      );
    }
    case "assemble":
      return (
        <div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 7, marginBottom: 8 }}>
            <span style={{ fontSize: 24, fontWeight: 700, color: "var(--label)", fontVariantNumeric: "tabular-nums" }}>33%</span>
            <span style={{ fontSize: 11, color: "var(--label-3)" }}>4 / 12 章已编制</span>
          </div>
          <div style={{ height: 6, borderRadius: 999, background: "var(--surface-2)", overflow: "hidden", marginBottom: 9 }}>
            <div style={{ width: "33%", height: "100%", background: "var(--blue)" }} />
          </div>
          <div style={{ fontSize: 11, color: "var(--label-2)" }}>约 1.2 万字 · 待补 资质附件 与 报价表</div>
        </div>
      );
    default:
      return null;
  }
}
