// Shared icons + the "thinking spark" — the brand's signature motion
// (re-used from Thinking Logo Explorations v3 and index.html)

const I = {
  mail: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
      <rect x="2" y="3.5" width="12" height="9" rx="1.5"/>
      <path d="M2.5 4.5l5.5 4.5 5.5-4.5"/>
    </svg>
  ),
  lock: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
      <rect x="3" y="7" width="10" height="7" rx="1.5"/>
      <path d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2"/>
    </svg>
  ),
  eye: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
      <path d="M1.5 8s2.5-4.5 6.5-4.5S14.5 8 14.5 8 12 12.5 8 12.5 1.5 8 1.5 8z"/>
      <circle cx="8" cy="8" r="2"/>
    </svg>
  ),
  arrow: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 8h10M9 4l4 4-4 4"/>
    </svg>
  ),
  check: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 8.5l3 3 7-7"/>
    </svg>
  ),
  building: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
      <path d="M3 14V4l5-2 5 2v10"/>
      <path d="M1 14h14"/>
      <path d="M6 7h.01M10 7h.01M6 10h.01M10 10h.01"/>
    </svg>
  ),
  shield: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
      <path d="M8 1.5l5.5 2v4c0 3-2.2 5.6-5.5 7-3.3-1.4-5.5-4-5.5-7v-4l5.5-2z"/>
    </svg>
  ),
  search: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
      <circle cx="7" cy="7" r="4.5"/>
      <path d="M13.5 13.5l-3-3"/>
    </svg>
  ),
  edit: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
      <path d="M11 2l3 3-8 8H3v-3l8-8z"/>
    </svg>
  ),
  clock: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
      <circle cx="8" cy="8" r="6"/>
      <path d="M8 4.5V8l2.2 1.5"/>
    </svg>
  ),
  doc: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
      <path d="M3.5 1.5h6L13 5v9a.5.5 0 0 1-.5.5h-9a.5.5 0 0 1-.5-.5v-12a.5.5 0 0 1 .5-.5z"/>
      <path d="M9 1.5V5h4"/>
    </svg>
  ),
  sparkLogo: (size = 24) => (
    <svg viewBox="0 0 32 32" fill="none" style={{ width: size, height: size }}>
      <g transform="rotate(28 16 16)">
        <ellipse cx="16" cy="16" rx="11.5" ry="4.2" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" pathLength="100" strokeDasharray="55 45" opacity=".15">
          <animate attributeName="stroke-dashoffset" dur="1.2s" from="0" to="-100" repeatCount="indefinite"/>
        </ellipse>
        <ellipse cx="16" cy="16" rx="11.5" ry="4.2" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" pathLength="100" strokeDasharray="28 72" opacity=".35">
          <animate attributeName="stroke-dashoffset" dur="1.2s" from="0" to="-100" repeatCount="indefinite"/>
        </ellipse>
        <ellipse cx="16" cy="16" rx="11.5" ry="4.2" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" pathLength="100" strokeDasharray="8 92" opacity=".75">
          <animate attributeName="stroke-dashoffset" dur="1.2s" from="0" to="-100" repeatCount="indefinite"/>
        </ellipse>
        <circle r="1.5" fill="currentColor">
          <animateMotion dur="1.2s" begin="-0.096s" repeatCount="indefinite"
            path="M 27.5 16 A 11.5 4.2 0 1 1 4.5 16 A 11.5 4.2 0 1 1 27.5 16"/>
        </circle>
      </g>
      <g transform="rotate(-28 16 16)">
        <ellipse cx="16" cy="16" rx="11.5" ry="4.2" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" pathLength="100" strokeDasharray="55 45" opacity=".15">
          <animate attributeName="stroke-dashoffset" dur="1.6s" from="0" to="100" repeatCount="indefinite"/>
        </ellipse>
        <ellipse cx="16" cy="16" rx="11.5" ry="4.2" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" pathLength="100" strokeDasharray="28 72" opacity=".35">
          <animate attributeName="stroke-dashoffset" dur="1.6s" from="0" to="100" repeatCount="indefinite"/>
        </ellipse>
        <ellipse cx="16" cy="16" rx="11.5" ry="4.2" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" pathLength="100" strokeDasharray="8 92" opacity=".75">
          <animate attributeName="stroke-dashoffset" dur="1.6s" from="0" to="100" repeatCount="indefinite"/>
        </ellipse>
        <circle r="1.5" fill="currentColor">
          <animateMotion dur="1.6s" begin="-1.504s" repeatCount="indefinite"
            path="M 4.5 16 A 11.5 4.2 0 1 0 27.5 16 A 11.5 4.2 0 1 0 4.5 16"/>
        </circle>
      </g>
      <circle cx="16" cy="16" r="5" fill="currentColor"/>
    </svg>
  ),
  wechatWork: (
    <svg viewBox="0 0 16 16" fill="currentColor">
      <path d="M5.8 2.2C3 2.2.7 4 .7 6.3c0 1.3.7 2.5 1.9 3.3l-.5 1.6 1.9-.9c.6.2 1.2.3 1.8.3.2 0 .4 0 .5-.03A4 4 0 0 1 6 9.5c0-2.3 2.2-4.1 5-4.1.2 0 .4 0 .6.03C11.2 3.5 8.7 2.2 5.8 2.2zM3.7 5.4a.7.7 0 1 1 0-1.4.7.7 0 0 1 0 1.4zm4.2 0a.7.7 0 1 1 0-1.4.7.7 0 0 1 0 1.4z"/>
      <path d="M15.3 9.5c0-1.9-1.9-3.4-4.3-3.4S6.7 7.6 6.7 9.5c0 1.9 1.9 3.4 4.3 3.4.5 0 1-.07 1.5-.2l1.6.8-.4-1.3c1-.7 1.6-1.7 1.6-2.7zM9.7 9a.6.6 0 1 1 0-1.2.6.6 0 0 1 0 1.2zm2.6 0a.6.6 0 1 1 0-1.2.6.6 0 0 1 0 1.2z"/>
    </svg>
  ),
  dingtalk: (
    <svg viewBox="0 0 16 16" fill="currentColor">
      <path d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1zm3.4 5.4l-1.5 3.4h1.2l-2.7 3.8L9 10.4H7.8l1.6-2.5c-.6 0-1.5-.2-2.6-1 0 0 .8.2 1.6 0 .9-.2 1.5-.7 1.5-.7L8 5.3l3.4 1.1z"/>
    </svg>
  ),
  sso: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
      <path d="M8 1.5l5.5 2.5v4.5c0 3-2.2 5.5-5.5 6-3.3-.5-5.5-3-5.5-6V4l5.5-2.5z"/>
      <path d="M5.5 8l2 2 3-3.5"/>
    </svg>
  ),
};

window.I = I;
