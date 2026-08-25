/* 冷板液冷循环示意（内容图形）：中性一律冷灰 token，强调线/节点只用 var(--blue)——
   工程示意图不引入第二调色板，热/冷回路以「灰 = 热回水、蓝 = 冷供水」区分层次。 */
export function CoolingDiagram() {
  return (
    <svg viewBox="0 0 800 320" xmlns="http://www.w3.org/2000/svg">
      {/* 服务器机柜 */}
      <g>
        <rect
          x={60}
          y={90}
          width={44}
          height={140}
          rx={3}
          fill="none"
          stroke="var(--label-2)"
          strokeWidth={1.3}
        />
        {[100, 120, 140, 160, 180, 200].map((y) => (
          <rect
            key={`a-${y}`}
            x={66}
            y={y}
            width={32}
            height={16}
            rx={1}
            fill="var(--surface-2)"
          />
        ))}
        <text
          x={82}
          y={255}
          fontFamily="var(--font-ui)"
          fontSize={10}
          fill="var(--label-2)"
          textAnchor="middle"
        >
          机柜 A01
        </text>

        <rect
          x={120}
          y={90}
          width={44}
          height={140}
          rx={3}
          fill="none"
          stroke="var(--label-2)"
          strokeWidth={1.3}
        />
        {[100, 120, 140, 160, 180, 200].map((y) => (
          <rect
            key={`b-${y}`}
            x={126}
            y={y}
            width={32}
            height={16}
            rx={1}
            fill="var(--surface-2)"
          />
        ))}
        <text
          x={142}
          y={255}
          fontFamily="var(--font-ui)"
          fontSize={10}
          fill="var(--label-2)"
          textAnchor="middle"
        >
          机柜 A02
        </text>

        <text
          x={100}
          y={80}
          fontFamily="var(--font-ui)"
          fontSize={10}
          fill="var(--label)"
          textAnchor="middle"
          fontWeight={500}
        >
          IT 负载侧 · 冷板液冷
        </text>
      </g>

      {/* 热回水管路（中性灰） */}
      <path
        d="M 170 140 L 330 140 L 330 95 L 500 95 L 500 140"
        stroke="var(--label-3)"
        strokeWidth={5}
        fill="none"
        strokeLinecap="round"
      />
      <text
        x={330}
        y={85}
        fontFamily="var(--font-ui)"
        fontSize={10}
        fill="var(--label-2)"
        textAnchor="middle"
      >
        热回水 34℃
      </text>

      {/* 冷供水管路（蓝 = 强调的制冷回路） */}
      <path
        d="M 170 180 L 330 180 L 330 230 L 500 230 L 500 185"
        stroke="var(--blue)"
        strokeWidth={5}
        fill="none"
        strokeLinecap="round"
      />
      <text
        x={330}
        y={248}
        fontFamily="var(--font-ui)"
        fontSize={10}
        fill="var(--blue)"
        textAnchor="middle"
      >
        冷供水 25℃
      </text>

      {/* 板式换热器 */}
      <g>
        <rect
          x={485}
          y={115}
          width={80}
          height={90}
          rx={4}
          fill="var(--surface-2)"
          stroke="var(--label-2)"
          strokeWidth={1.3}
        />
        {[140, 160, 180].map((y) => (
          <line
            key={`hx-${y}`}
            x1={495}
            y1={y}
            x2={555}
            y2={y}
            stroke="var(--label-3)"
            strokeWidth={1}
          />
        ))}
        <text
          x={525}
          y={225}
          fontFamily="var(--font-ui)"
          fontSize={10}
          fill="var(--label-2)"
          textAnchor="middle"
        >
          板式换热器
        </text>
      </g>

      <path
        d="M 565 140 L 650 140"
        stroke="var(--label-3)"
        strokeWidth={5}
        fill="none"
        strokeLinecap="round"
      />
      <path
        d="M 565 180 L 650 180"
        stroke="var(--blue)"
        strokeWidth={5}
        fill="none"
        strokeLinecap="round"
      />

      {/* 室外干冷器 */}
      <g>
        <rect
          x={650}
          y={110}
          width={100}
          height={100}
          rx={4}
          fill="var(--surface-2)"
          stroke="var(--label-2)"
          strokeWidth={1.3}
        />
        <g stroke="var(--label-3)" strokeWidth={1}>
          {[660, 670, 680, 690, 700, 710, 720, 730, 740].map((x) => (
            <line key={`fin-${x}`} x1={x} y1={125} x2={x} y2={195} />
          ))}
        </g>
        <text
          x={700}
          y={225}
          fontFamily="var(--font-ui)"
          fontSize={10}
          fill="var(--label-2)"
          textAnchor="middle"
        >
          室外干冷器
        </text>
      </g>
      <text
        x={700}
        y={80}
        fontFamily="var(--font-ui)"
        fontSize={10}
        fill="var(--label)"
        textAnchor="middle"
        fontWeight={500}
      >
        基础设施侧 · 自然冷却 5,840 h/年
      </text>

      {/* 流向箭头：热回路随管路用灰，冷回路用蓝 */}
      <g fill="var(--label-3)">
        <polygon points="490,138 500,142 490,146" />
      </g>
      <g fill="var(--blue)">
        <polygon points="170,178 160,182 170,186" />
      </g>
    </svg>
  );
}
