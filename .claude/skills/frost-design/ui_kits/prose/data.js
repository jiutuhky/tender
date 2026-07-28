/* Prose UI kit — mock data. Assigned to window for the babel-scoped kit files. */
window.PROSE_DATA = {
  projects: [
    { id: "sim",   icon: "folder-simple", name: "仿真软件开发服务采购" },
    { id: "park",  icon: "folder-simple", name: "智慧园区运维服务" },
    { id: "lab",   icon: "folder-simple", name: "实验室设备购置" },
  ],
  knowledge: [
    { id: "qual", icon: "identification-card", name: "资质证照", count: 12 },
    { id: "case", icon: "buildings",           name: "业绩案例", count: 38 },
    { id: "cv",   icon: "files",               name: "人员简历", count: 24 },
  ],
  // The opening agent conversation for the active project.
  thread: [
    { role: "user", text: "解析这份招标文件的技术需求，生成技术需求清单。" },
    {
      role: "agent",
      chips: [
        { icon: "file-text", label: "已读取", mono: "招标文件.md" },
        { done: true, label: "技术需求解析完成" },
      ],
      text: "已从第三章提取全部技术需求条目，按 **功能、性能、接口、安全** 四类归档，并标出了需要逐条响应的实质性条款。偏差项已同步到右侧大纲的「技术偏差表」，可以逐项确认。",
    },
  ],
  // Canned follow-up the fake agent "produces" when you send a message.
  reply: {
    role: "agent",
    chips: [
      { running: true, label: "正在比对需求条目" },
      { done: true, label: "技术偏差表已生成" },
    ],
    text: "已将技术需求清单与现有产品能力逐条比对：**完全响应 18 项、部分响应 5 项、偏差 3 项**。三处偏差均已附上替代方案说明，建议在投标前与技术负责人确认。",
  },
  outline: [
    { label: "投标函及附录", lvl: 1 },
    { label: "法定代表人授权书", lvl: 1 },
    { label: "商务响应", lvl: 1 },
    { label: "技术方案", lvl: 1, active: true, open: true, children: [
      { label: "技术需求响应", badge: "已生成", badgeTone: "green" },
      { label: "技术偏差表", badge: "草稿", badgeTone: "neutral" },
      { label: "实施与验收方案" },
    ]},
    { label: "资质证明材料", lvl: 1 },
    { label: "报价表", lvl: 1 },
  ],
  suggestions: ["生成技术偏差表", "插入资质证照", "核对报价表"],
};
