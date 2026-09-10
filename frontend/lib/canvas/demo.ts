import { addCollection, addEntity } from "./adapters";
import { emptySource, type CanvasSource } from "./model";

/** 独立验收场景，所有业务对象都由演示适配器提供。 */
export function demoSource(
  mode: "complete" | "working" | "partial" | "stress" = "complete",
): CanvasSource {
  const source = emptySource();
  addCollection(
    source,
    "materials",
    "项目资料",
    "folder",
    0,
    25,
    null,
    "white",
  );
  source.collections.materials!.subtitle = "招标文件与企业素材";
  addEntity(
    source,
    {
      id: "brief",
      kind: "summary",
      title: "智慧园区数字化建设",
      subtitle: "公开招标 · 技术与服务",
      body: "以统一的数据底座连接园区设施、运营服务与日常管理，让每一项建设要求都有清楚的应答。",
      outline: [
        { title: "采购人 · 城市建设发展中心", depth: 0 },
        { title: "投标截止 · 2026 年 10 月 16 日", depth: 0 },
      ],
    },
    385,
    0,
    null,
    312,
    252,
  );
  addEntity(
    source,
    {
      id: "tender",
      kind: "document",
      title: "智慧园区建设招标文件",
      subtitle: "招标文件 · Markdown",
      body: "# 智慧园区数字化建设\n\n## 采购需求\n\n建设统一的园区运营管理平台，整合设备接入、数据治理、可视化与移动服务。\n\n## 技术评审\n\n总体设计应完整、可实施，明确各系统间的边界与接口，并说明可靠性保障措施。\n\n## 实施与服务\n\n供应商应提供分阶段实施计划、项目团队和持续服务机制。",
    },
    0,
    0,
    "materials",
  );
  addCollection(
    source,
    "qualifications",
    "企业资质",
    "folder",
    350,
    0,
    "materials",
    "blue",
  );
  addEntity(
    source,
    {
      id: "qualification",
      kind: "document",
      title: "企业能力与项目经验",
      subtitle: "企业资料",
      body: "# 企业能力与项目经验\n\n## 交付能力\n\n提供系统咨询、软件研发、集成实施与运维支持。\n\n## 项目经验\n\n园区平台建设、数据治理与企业数字化服务。",
    },
    0,
    0,
    "qualifications",
  );
  addEntity(
    source,
    {
      id: "reference-image",
      kind: "image",
      title: "空间与设备参考",
      src: "/canvas-demo/desk.webp",
      subtitle: "项目参考图",
    },
    700,
    0,
    "materials",
    300,
    225,
  );
  addEntity(
    source,
    {
      id: "reference-video",
      kind: "video",
      title: "设备运行演示",
      src: "/canvas-demo/clock.mp4",
      subtitle: "参考视频",
    },
    1050,
    0,
    "materials",
    280,
    280,
  );
  addCollection(source, "scoring", "评分要点", "stack", 790, 20);
  Object.assign(source.collections.scoring!, {
    metric: "100 分",
    subtitle: "技术 60 · 商务 20 · 价格 20",
  });
  const scores = [
    [
      "总体技术方案",
      "技术 / 方案设计",
      18,
      "根据对项目需求的理解、架构设计的完整性与可实施性综合评审。\n\n说明系统边界、数据流转与关键技术选型，给出可靠性保障措施。",
      "技术文件 · 总体设计",
    ],
    [
      "实施与交付计划",
      "技术 / 项目实施",
      12,
      "评审实施步骤、进度安排、资源投入以及风险应对措施。\n\n各阶段应有明确的里程碑与验收成果。",
      "技术文件 · 实施计划",
    ],
    [
      "服务保障能力",
      "技术 / 持续服务",
      10,
      "根据服务响应机制、人员配置与问题处理闭环综合评审。",
      "技术文件 · 服务方案",
    ],
    [
      "相关项目经验",
      "商务 / 履约能力",
      20,
      "提供与本项目建设内容相关的业绩证明材料，说明实施范围与交付成果。",
      "商务文件 · 项目业绩",
    ],
  ] as const;
  const count = mode === "stress" ? 200 : scores.length;
  for (let i = 0; i < count; i++) {
    const row = scores[i % scores.length]!;
    addEntity(
      source,
      {
        id: `score-${i}`,
        kind: "scoring",
        title: row[0],
        group: row[1],
        score: row[2],
        body: row[3],
        subtitle: row[4],
        confirmed: i === 0,
      },
      (i % 4) * 324,
      Math.floor(i / 4) * 420,
      "scoring",
    );
    source.relations.push({
      id: `source-${i}`,
      from: `score-${i}`,
      to: "tender",
      kind: "source",
    });
  }
  addEntity(
    source,
    {
      id: "outline",
      kind: "outline",
      title: "投标文件大纲",
      subtitle: "技术文件",
      outline: [
        { title: "一、项目理解与建设目标", depth: 0, entityId: "chapter-0" },
        { title: "二、总体技术方案", depth: 0, entityId: "chapter-1" },
        { title: "2.1 系统总体架构", depth: 1, entityId: "chapter-1" },
        { title: "2.2 数据与接口设计", depth: 1, entityId: "chapter-2" },
        { title: "三、项目实施计划", depth: 0, entityId: "chapter-2" },
        { title: "四、服务与保障", depth: 0, entityId: "chapter-3" },
      ],
    },
    1170,
    5,
  );
  addEntity(
    source,
    {
      id: "note",
      kind: "note",
      title: "编制备忘",
      body: "先核对评分标准，再组织每章的应答。\n\n• 架构图与技术方案保持一致\n• 业绩证明放入商务文件\n• 每个里程碑都要有交付物",
      editable: true,
    },
    20,
    410,
    null,
    285,
    275,
  );
  addEntity(
    source,
    {
      id: "site-image",
      kind: "image",
      title: "设备工作台参考",
      src: "/canvas-demo/desk.webp",
    },
    390,
    400,
    null,
    280,
    330,
  );
  addCollection(source, "chapters", "技术方案", "stack", 815, 465);
  source.collections.chapters!.subtitle = "4 个章节 · 连续编写";
  ["项目理解与建设目标", "总体技术方案", "项目实施计划", "服务与保障"].forEach(
    (title, i) => {
      addEntity(
        source,
        {
          id: `chapter-${i}`,
          kind: "chapter",
          title,
          number: `0${i + 1}`,
          subtitle: "技术文件 · 草稿",
          editable: true,
          body: `# ${title}\n\n## ${i === 1 ? "设计原则" : "目标与范围"}\n\n围绕智慧园区的建设目标，以统一规划、分步实施为原则，将业务能力与技术架构协同组织。\n\n建立清楚的责任边界，确保每个阶段的成果可验证、可交付。\n\n## ${i === 1 ? "系统总体架构" : "实施要点"}\n\n采用分层架构，连接设备接入、数据服务与应用层。通过标准接口实现各业务系统的信息共享。\n\n- 明确各子系统的职责与边界\n- 形成一致的数据标准与接口约定\n- 建立交付质量与持续改进机制`,
          status:
            mode === "working" && i > 0
              ? "working"
              : mode === "partial" && i === 2
                ? "error"
                : "ready",
          statusText:
            mode === "working" && i > 0
              ? "正在编写"
              : mode === "partial" && i === 2
                ? "生成中断"
                : undefined,
        },
        (i % 4) * 324,
        0,
        "chapters",
      );
      source.relations.push({
        id: `response-${i}`,
        from: `chapter-${i}`,
        to: `score-${i}`,
        kind: "response",
      });
    },
  );
  source.relations.push({
    id: "image-reference",
    from: "chapter-1",
    to: "site-image",
    kind: "reference",
  });
  if (mode !== "working")
    addEntity(
      source,
      {
        id: "final",
        kind: "final",
        title: "技术投标文件",
        subtitle: "汇编草稿 · Markdown",
        body:
          "# 技术投标文件\n\n## 智慧园区数字化建设\n\n" +
          Object.values(source.entities)
            .filter((e) => e.kind === "chapter")
            .map((e) => e.body)
            .join("\n\n"),
      },
      1170,
      455,
      null,
      254,
      338,
    );
  if (mode === "stress")
    for (let i = 0; i < 95; i++)
      addEntity(
        source,
        {
          id: `asset-${i}`,
          kind: i % 3 ? "document" : "image",
          title: `项目资料 ${i + 1}`,
          body: "项目交付资料与证明文件。",
          src: i % 3 ? undefined : "/canvas-demo/desk.webp",
        },
        (i % 4) * 324,
        (Math.floor(i / 4) + 1) * 420,
        "materials",
      );
  return source;
}
