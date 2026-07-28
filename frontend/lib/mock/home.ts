// 首页「统一 Agent 入口」的静态 mock 数据。
// 字段取自 data/ 真实语料（仿真软件开发服务采购项目招标文件）。
// 当前为前端原型；接后端后由 hagent 会话与项目服务替换。

/** 挂上招标文件后为 composer 预填的默认意图 */
export const DEFAULT_INTENT = "解析这份招标文件，生成应答矩阵。";

/** 建议 chips：问答两条 + 建项目一条（accent 强调） */
export const HOME_SUGGESTIONS = [
  "智慧园区类项目，我们有哪些可引用的业绩案例？",
  "对比这两份招标文件的资质要求差异。",
];

/** 自由问答路径的 canned 答复（状态优先叙事，重点名词加粗） */
export const KNOWLEDGE_REPLY = {
  parts: [
    { text: "已在 " },
    { text: "业绩案例库", strong: true },
    { text: " 检索到 " },
    { text: "3 条", strong: true },
    {
      text: " 智慧园区相关业绩：2023 苏州工业园区智慧运维（合同额 2,180 万）、2024 雄安市民服务中心综合运维、2024 临港新片区园区数字化服务。均可直接引用至商务响应。",
    },
  ],
  sources: ["业绩案例库 · 3 条", "合同台账 2023-2024"],
};

/** 最近项目（与 projects 页 PROJECTS 前三条保持一致口径） */
export const HOME_RECENT: Array<{
  name: string;
  status: string;
  progress: number;
  deadline: string;
  href: string;
}> = [
  {
    name: "浦东新区一网通办平台运维",
    status: "撰写中",
    progress: 64,
    deadline: "6 天",
    href: "/workspace",
  },
  {
    name: "智慧园区综合运维服务采购",
    status: "评审中",
    progress: 88,
    deadline: "3 天",
    href: "#",
  },
  {
    name: "实验室设备购置项目",
    status: "草稿",
    progress: 18,
    deadline: "14 天",
    href: "#",
  },
];
