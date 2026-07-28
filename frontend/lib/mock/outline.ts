export type SubStatus = "done" | "running" | "todo";

export interface OutlineChapter {
  idx: string;
  name: string;
  stat: string;
  active?: boolean;
  subs: { name: string; status: SubStatus }[];
}

export const OUTLINE: OutlineChapter[] = [
  {
    idx: "01",
    name: "商务响应",
    stat: "11 p",
    subs: [
      { name: "1.1 投标函", status: "done" },
      { name: "1.2 法人资质", status: "done" },
      { name: "1.3 投标保函", status: "done" },
    ],
  },
  {
    idx: "02",
    name: "公司综合实力",
    stat: "9 p",
    subs: [
      { name: "2.1 公司概况", status: "done" },
      { name: "2.2 团队与专家", status: "done" },
      { name: "2.3 历史业绩", status: "done" },
    ],
  },
  {
    idx: "03",
    name: "项目理解与需求响应",
    stat: "14 p",
    subs: [
      { name: "3.1 项目背景解读", status: "done" },
      { name: "3.2 需求逐条响应", status: "done" },
      { name: "3.3 偏离说明", status: "done" },
    ],
  },
  {
    idx: "04",
    name: "绿色技术方案",
    stat: "23 p",
    active: true,
    subs: [
      { name: "4.1 总体技术路线", status: "done" },
      { name: "4.2 液冷子系统设计", status: "running" },
      { name: "4.3 余热回收与利用", status: "todo" },
      { name: "4.4 光储一体化", status: "todo" },
      { name: "4.5 智能运维", status: "todo" },
    ],
  },
  {
    idx: "05",
    name: "实施与交付",
    stat: "12 p",
    subs: [
      { name: "5.1 项目进度计划", status: "todo" },
      { name: "5.2 质量保证", status: "todo" },
      { name: "5.3 运维与培训", status: "todo" },
    ],
  },
  {
    idx: "06",
    name: "报价与服务承诺",
    stat: "9 p",
    subs: [
      { name: "6.1 投标报价表", status: "todo" },
      { name: "6.2 服务承诺", status: "todo" },
    ],
  },
];
