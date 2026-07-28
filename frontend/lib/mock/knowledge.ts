export type FileKind = "pdf" | "doc" | "xls" | "zip";
export type TagKind = "technical" | "case" | "template" | "cred";

export interface CaseCard {
  id: string;
  title: string;
  client: string;
  status: "won" | "lost";
  metrics: { label: string; value: string; unit?: string; small?: boolean }[];
  footer: { citeCount?: number; cites?: string; assets?: number };
}

export const CASES: CaseCard[] = [
  {
    id: "P-2025-0712",
    status: "won",
    title: "上海张江绿色数据中心二期改造",
    client: "上海张江高科 · 2025-08 竣工",
    metrics: [
      { label: "合同额", value: "1.04", unit: "亿" },
      { label: "实测 PUE", value: "1.184" },
      { label: "工期", value: "11", unit: "月" },
      { label: "类型", value: "液冷 / 余热" , small: true },
    ],
    footer: { citeCount: 14, assets: 23 },
  },
  {
    id: "P-2025-0441",
    status: "won",
    title: "上海轨道交通 15 号线信号系统升级",
    client: "上海申通地铁 · 2025-06 交付",
    metrics: [
      { label: "合同额", value: "3,400", unit: "万" },
      { label: "MTBF", value: "> 8", unit: "万 h" },
      { label: "工期", value: "9", unit: "月" },
      { label: "类型", value: "CBTC / 信号" , small: true },
    ],
    footer: { citeCount: 9, assets: 18 },
  },
  {
    id: "P-2024-1203",
    status: "won",
    title: "杭州未来科技城智慧园区运维平台",
    client: "杭州未来科技城管委会 · 2024-12 上线",
    metrics: [
      { label: "合同额", value: "2,180", unit: "万" },
      { label: "接入设备", value: "14,200" },
      { label: "工期", value: "14", unit: "月" },
      { label: "类型", value: "IoT / 园区" , small: true },
    ],
    footer: { citeCount: 6, assets: 27 },
  },
  {
    id: "P-2025-0218",
    status: "lost",
    title: "国资委合规审计采购项目",
    client: "国务院国资委 · 2025-04 开标",
    metrics: [
      { label: "投标额", value: "4,800", unit: "万" },
      { label: "评分差距", value: "-6.2" },
      { label: "复盘", value: "已完成" , small: true },
      { label: "类型", value: "审计 / 合规" , small: true },
    ],
    footer: { cites: "复盘报告被引 4 次" },
  },
  {
    id: "P-2024-0906",
    status: "won",
    title: "合肥科大智慧校园边缘计算节点",
    client: "中国科学技术大学 · 2024-09 验收",
    metrics: [
      { label: "合同额", value: "1,620", unit: "万" },
      { label: "节点数", value: "86" },
      { label: "工期", value: "7", unit: "月" },
      { label: "类型", value: "边缘 / 高校" , small: true },
    ],
    footer: { citeCount: 3, assets: 12 },
  },
  {
    id: "P-2024-0517",
    status: "won",
    title: "苏州工业园区数据中心扩建",
    client: "苏州工业园区国资 · 2024-11 交付",
    metrics: [
      { label: "合同额", value: "7,600", unit: "万" },
      { label: "实测 PUE", value: "1.21" },
      { label: "工期", value: "10", unit: "月" },
      { label: "类型", value: "数据中心" },
    ],
    footer: { citeCount: 8, assets: 21 },
  },
];

export interface AssetRow {
  kind: FileKind;
  name: string;
  sub: string;
  tag: TagKind;
  tagLabel: string;
  citations: number;
  fillPct: number;
  date: string;
}

export const ASSETS: AssetRow[] = [
  {
    kind: "pdf",
    name: "液冷系统选型白皮书 v3.2",
    sub: "P / R-2025-03-18 · 38 页 · 12.4 MB",
    tag: "technical",
    tagLabel: "技术白皮书",
    citations: 32,
    fillPct: 92,
    date: "2025-03-18",
  },
  {
    kind: "pdf",
    name: "上海张江二期 · 竣工验收报告",
    sub: "R-07 · 142 页 · 含实测 PUE 曲线 全年",
    tag: "case",
    tagLabel: "项目案例",
    citations: 28,
    fillPct: 82,
    date: "2025-09-04",
  },
  {
    kind: "doc",
    name: "公司综合业绩表 2024Q4",
    sub: "内部 · 含 38 项中标业绩 · 待更新",
    tag: "cred",
    tagLabel: "资质业绩",
    citations: 27,
    fillPct: 78,
    date: "2024-12-30",
  },
  {
    kind: "pdf",
    name: "GB 50174-2017 数据中心设计规范",
    sub: "国家标准 · 最新修订版 · 引用权威",
    tag: "technical",
    tagLabel: "规范标准",
    citations: 21,
    fillPct: 62,
    date: "2017-06-01",
  },
  {
    kind: "xls",
    name: "主要设备品牌目录 · 2026 版",
    sub: "内部 · 含 12 大类 · 授权文件齐全",
    tag: "cred",
    tagLabel: "资质业绩",
    citations: 19,
    fillPct: 56,
    date: "2026-01-08",
  },
  {
    kind: "doc",
    name: "项目经理简历 · 张建华",
    sub: "15 年数据中心经验 · 一级建造师",
    tag: "cred",
    tagLabel: "资质证书",
    citations: 14,
    fillPct: 42,
    date: "2025-11-20",
  },
  {
    kind: "zip",
    name: "余热回收方案模板集",
    sub: "4 套方案 · 含原理图、计算书、案例",
    tag: "template",
    tagLabel: "标书模板",
    citations: 11,
    fillPct: 32,
    date: "2025-06-15",
  },
];

export interface Template {
  name: string;
  meta: string;
  thumb: ("title" | "line" | "short" | "mid" | "accent" | "divider")[];
}

export const TEMPLATES: Template[] = [
  {
    name: "央企综合标书 · 标准版",
    meta: "78 页 · 引用 47 次 · 2025 更新",
    thumb: [
      "title",
      "accent",
      "mid",
      "line",
      "short",
      "divider",
      "mid",
      "line",
      "short",
    ],
  },
  {
    name: "政府采购 · 技术类项目",
    meta: "62 页 · 引用 34 次 · 2025 更新",
    thumb: [
      "title",
      "mid",
      "line",
      "short",
      "divider",
      "accent",
      "mid",
      "short",
      "line",
    ],
  },
  {
    name: "IT 服务类 · 响应书",
    meta: "46 页 · 引用 21 次 · 2024 更新",
    thumb: [
      "title",
      "line",
      "short",
      "divider",
      "mid",
      "line",
      "accent",
      "short",
      "mid",
    ],
  },
  {
    name: "工程施工类 · 投标书",
    meta: "92 页 · 引用 28 次 · 2025 更新",
    thumb: [
      "title",
      "accent",
      "mid",
      "line",
      "short",
      "line",
      "divider",
      "mid",
      "short",
    ],
  },
];

export interface NavEntry {
  label: string;
  count: number;
  active?: boolean;
}

export const NAV_TYPES: NavEntry[] = [
  { label: "全部资料", count: 1284, active: true },
  { label: "历史标书", count: 342 },
  { label: "项目案例", count: 168 },
  { label: "资质证书", count: 57 },
  { label: "技术白皮书", count: 89 },
  { label: "标书模板", count: 24 },
  { label: "专家简历", count: 46 },
];

export const NAV_AGENT: NavEntry[] = [
  { label: "最近被引用", count: 73 },
  { label: "智能体标注", count: 18 },
  { label: "待补充", count: 9 },
];
