export function CoolingDiagram() {
  return (
    <svg viewBox="0 0 800 320" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="hot" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0%" stopColor="oklch(70% 0.12 40)" />
          <stop offset="100%" stopColor="oklch(60% 0.14 35)" />
        </linearGradient>
        <linearGradient id="cold" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0%" stopColor="oklch(65% 0.10 240)" />
          <stop offset="100%" stopColor="oklch(60% 0.13 245)" />
        </linearGradient>
      </defs>

      {/* Server racks */}
      <g>
        <rect
          x={60}
          y={90}
          width={44}
          height={140}
          rx={3}
          fill="none"
          stroke="oklch(30% 0.02 60)"
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
            fill="oklch(92% 0.008 80)"
          />
        ))}
        <text
          x={82}
          y={255}
          fontFamily="system-ui"
          fontSize={10}
          fill="oklch(40% 0.015 60)"
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
          stroke="oklch(30% 0.02 60)"
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
            fill="oklch(92% 0.008 80)"
          />
        ))}
        <text
          x={142}
          y={255}
          fontFamily="system-ui"
          fontSize={10}
          fill="oklch(40% 0.015 60)"
          textAnchor="middle"
        >
          机柜 A02
        </text>

        <text
          x={100}
          y={80}
          fontFamily="system-ui"
          fontSize={10}
          fill="oklch(30% 0.02 60)"
          textAnchor="middle"
          fontWeight={500}
        >
          IT 负载侧 · 冷板液冷
        </text>
      </g>

      {/* Hot pipes */}
      <path
        d="M 170 140 L 330 140 L 330 95 L 500 95 L 500 140"
        stroke="url(#hot)"
        strokeWidth={5}
        fill="none"
        strokeLinecap="round"
      />
      <text
        x={330}
        y={85}
        fontFamily="system-ui"
        fontSize={10}
        fill="oklch(50% 0.10 40)"
        textAnchor="middle"
      >
        热回水 34℃
      </text>

      {/* Cold pipes */}
      <path
        d="M 170 180 L 330 180 L 330 230 L 500 230 L 500 185"
        stroke="url(#cold)"
        strokeWidth={5}
        fill="none"
        strokeLinecap="round"
      />
      <text
        x={330}
        y={248}
        fontFamily="system-ui"
        fontSize={10}
        fill="oklch(50% 0.10 240)"
        textAnchor="middle"
      >
        冷供水 25℃
      </text>

      {/* Heat exchanger */}
      <g>
        <rect
          x={485}
          y={115}
          width={80}
          height={90}
          rx={4}
          fill="oklch(98% 0.005 60)"
          stroke="oklch(30% 0.02 60)"
          strokeWidth={1.3}
        />
        {[140, 160, 180].map((y) => (
          <line
            key={`hx-${y}`}
            x1={495}
            y1={y}
            x2={555}
            y2={y}
            stroke="oklch(50% 0.02 60)"
            strokeWidth={1}
          />
        ))}
        <text
          x={525}
          y={225}
          fontFamily="system-ui"
          fontSize={10}
          fill="oklch(30% 0.02 60)"
          textAnchor="middle"
        >
          板式换热器
        </text>
      </g>

      <path
        d="M 565 140 L 650 140"
        stroke="url(#hot)"
        strokeWidth={5}
        fill="none"
        strokeLinecap="round"
      />
      <path
        d="M 565 180 L 650 180"
        stroke="url(#cold)"
        strokeWidth={5}
        fill="none"
        strokeLinecap="round"
      />

      {/* Dry cooler */}
      <g>
        <rect
          x={650}
          y={110}
          width={100}
          height={100}
          rx={4}
          fill="oklch(96% 0.006 80)"
          stroke="oklch(30% 0.02 60)"
          strokeWidth={1.3}
        />
        <g stroke="oklch(50% 0.02 60)" strokeWidth={1}>
          {[660, 670, 680, 690, 700, 710, 720, 730, 740].map((x) => (
            <line key={`fin-${x}`} x1={x} y1={125} x2={x} y2={195} />
          ))}
        </g>
        <text
          x={700}
          y={225}
          fontFamily="system-ui"
          fontSize={10}
          fill="oklch(30% 0.02 60)"
          textAnchor="middle"
        >
          室外干冷器
        </text>
      </g>
      <text
        x={700}
        y={80}
        fontFamily="system-ui"
        fontSize={10}
        fill="oklch(30% 0.02 60)"
        textAnchor="middle"
        fontWeight={500}
      >
        基础设施侧 · 自然冷却 5,840 h/年
      </text>

      <g fill="oklch(50% 0.10 40)">
        <polygon points="490,138 500,142 490,146" />
      </g>
      <g fill="oklch(50% 0.10 240)">
        <polygon points="170,178 160,182 170,186" />
      </g>
    </svg>
  );
}
