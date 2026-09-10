import type { MatrixSlots, RunPhase } from "@/lib/store/workspace";
import {
  workspaceFileUrl,
  type DocumentRecord,
  type WorkspaceFile,
} from "@/lib/hagent/api";
import type { MatrixType } from "@/lib/hagent/matrix";
import { emptySource, type CanvasEntity, type CanvasSource } from "./model";
import { documentAssetUrl } from "@/lib/trace/pdf-runtime";

const matrixTitles = {
  basic_info: "项目概要",
  business: "商务要求",
  technical: "技术要求",
  scoring: "评分要点",
};
const groupTitles: Record<string, string> = {
  price: "价格",
  business: "商务",
  technical: "技术",
  other: "其他",
};
const responseTitles: Record<string, string> = {
  compliant: "合规",
  positive_deviation: "正偏离",
  negative_deviation: "负偏离",
};
export const formatSize = (size: number) =>
  size < 1024
    ? `${size} B`
    : size < 1024 * 1024
      ? `${(size / 1024).toFixed(1)} KB`
      : `${(size / 1024 / 1024).toFixed(1)} MB`;
export function fileKind(path: string): CanvasEntity["kind"] {
  const ext = path.split(".").pop()?.toLowerCase() ?? "";
  if (["png", "jpg", "jpeg", "webp", "gif", "avif", "svg"].includes(ext))
    return "image";
  if (["mp4", "webm", "mov", "m4v", "ogv"].includes(ext)) return "video";
  return "document";
}
export function addEntity(
  source: CanvasSource,
  entity: CanvasEntity,
  x: number,
  y: number,
  parentId: string | null = null,
  w = 280,
  h = 374,
) {
  source.entities[entity.id] = entity;
  source.placements[entity.id] = {
    id: entity.id,
    entityId: entity.id,
    x,
    y,
    w,
    h,
    parentId,
  };
}
export function addCollection(
  source: CanvasSource,
  id: string,
  title: string,
  kind: "stack" | "folder",
  x: number,
  y: number,
  parentId: string | null = null,
  color = "white",
) {
  source.collections[id] = { id, title, kind, color };
  source.placements[id] = {
    id,
    entityId: id,
    x,
    y,
    w: kind === "folder" ? 312 : 280,
    h: kind === "folder" ? 266 : 344,
    parentId,
  };
}
/** 老数据缺少条目编号时用内容标识稳定展示，写动作仍要求服务端 item_id。 */
function contentKey(text: string) {
  let hash = 2166136261;
  for (let i = 0; i < text.length; i++)
    hash = Math.imul(hash ^ text.charCodeAt(i), 16777619);
  return (hash >>> 0).toString(36);
}
export function matrixSource(
  slots: MatrixSlots,
  phase: RunPhase,
  hasProject: boolean,
): CanvasSource {
  const source = emptySource();
  if (!hasProject) return source;
  for (const type of Object.keys(matrixTitles) as MatrixType[]) {
    const slot = slots[type];
    if (
      slot.status === "empty" &&
      phase !== "running" &&
      phase !== "loading_results"
    )
      continue;
    const status =
      slot.status === "ready"
        ? "ready"
        : slot.status === "error"
          ? "error"
          : phase === "error"
            ? "interrupted"
            : "working";
    const statusText =
      status === "error"
        ? "解析失败"
        : status === "interrupted"
          ? "解析中断"
          : status === "working"
            ? "正在解析"
            : undefined;
    if (type === "basic_info") {
      const data = slots.basic_info.data;
      addEntity(
        source,
        {
          id: type,
          kind: "summary",
          title: data?.project?.name || data?.project_name || "项目概要",
          subtitle: data?.project?.number ?? undefined,
          body: data?.project?.scope ?? undefined,
          matrixType: type,
          status,
          statusText,
          outline: [
            ...(data?.project?.purchaser?.name
              ? [{ title: data.project.purchaser.name, depth: 0 }]
              : []),
            ...(data?.timeline ?? [])
              .filter((t) => /投标.*截止|截止.*投标/.test(t.event ?? ""))
              .slice(0, 1)
              .map((t) => ({
                title: `${t.event} · ${t.datetime ?? "待确认"}`,
                depth: 0,
              })),
          ],
        },
        380,
        10,
        null,
        312,
        240,
      );
      continue;
    }
    const x = type === "business" ? 380 : 760,
      y = type === "scoring" ? 20 : 440;
    addCollection(source, type, matrixTitles[type], "stack", x, y);
    const collection = source.collections[type]!;
    Object.assign(collection, { matrixType: type, status, statusText });
    const seen = new Map<string, number>();
    if (type === "scoring") {
      const data = slots.scoring.data;
      const ev = data?.evaluation;
      collection.metric =
        typeof ev?.total_score === "number"
          ? `${ev.total_score} 分`
          : undefined;
      collection.subtitle = [
        ["商务", ev?.business_score],
        ["技术", ev?.technical_score],
        ["价格", ev?.price_score],
      ]
        .filter((p) => typeof p[1] === "number")
        .map((p) => `${p[0]} ${p[1]}`)
        .join(" · ");
      const items = [...(data?.items ?? [])].sort((a, b) =>
        `${a.group ?? ""}/${a.subgroup ?? ""}`.localeCompare(
          `${b.group ?? ""}/${b.subgroup ?? ""}`,
          "zh",
        ),
      );
      items.forEach((item, i) => {
        const base =
          item.id || contentKey(`${item.title}/${item.scoring_rule}`);
        const occurrence = seen.get(base) ?? 0;
        seen.set(base, occurrence + 1);
        const id = `scoring:${base}${occurrence ? `:${occurrence}` : ""}`;
        const row = slot.itemRows?.find((r) => r.item_id === item.id);
        addEntity(
          source,
          {
            id,
            kind: "scoring",
            title: item.title || "评分要点",
            body: item.scoring_rule,
            score:
              typeof item.max_score === "number" ? item.max_score : undefined,
            group: [groupTitles[item.group ?? ""] ?? item.group, item.subgroup]
              .filter(Boolean)
              .join(" / "),
            subtitle: item.related_format || undefined,
            sourceRefs: item.source_refs,
            matrixType: type,
            itemId: item.id,
            confirmed: row?.confirmed,
            status: "ready",
            statusText: item.mandatory_gate ? "通过性要求" : undefined,
          },
          (i % 4) * 324,
          Math.floor(i / 4) * 420,
          type,
        );
      });
    } else {
      const data = slots[type].data;
      const reviewed =
        slot.itemRows?.filter(
          (r) => r.confirmed && data?.items?.some((it) => it.id === r.item_id),
        ).length ?? 0;
      collection.subtitle = `${data?.items?.length ?? 0} 项要求${reviewed ? ` · 已核验 ${reviewed} 项` : ""}`;
      (data?.items ?? []).forEach((item, i) => {
        const base =
          item.id || contentKey(`${item.title}/${item.requirement_text}`);
        const occurrence = seen.get(base) ?? 0;
        seen.set(base, occurrence + 1);
        const id = `${type}:${base}${occurrence ? `:${occurrence}` : ""}`;
        const row = slot.itemRows?.find((r) => r.item_id === item.id);
        addEntity(
          source,
          {
            id,
            kind: "requirement",
            title: item.title || "招标要求",
            body: item.requirement_text,
            subtitle: item.evidence_required?.join("、"),
            number:
              item.param_nature || (item.mandatory ? "必须响应" : undefined),
            group: matrixTitles[type],
            sourceRefs: item.source_refs,
            matrixType: type,
            itemId: item.id,
            confirmed: row?.confirmed,
            responseText: row?.response_status
              ? responseTitles[row.response_status]
              : undefined,
            status: "ready",
          },
          (i % 4) * 324,
          Math.floor(i / 4) * 420,
          type,
        );
      });
    }
  }
  return source;
}
export function appendFiles(
  source: CanvasSource,
  projectId: string,
  files: WorkspaceFile[],
  documents: DocumentRecord[],
): CanvasSource {
  const result: CanvasSource = {
    entities: { ...source.entities },
    placements: { ...source.placements },
    collections: { ...source.collections },
    relations: [...source.relations],
  };
  const listed = new Set(files.map((file) => file.path));
  const knownFiles = [
    ...files,
    ...documents
      .filter((doc) => !listed.has(doc.path))
      .map((doc) => ({ path: doc.path, size: 0 })),
  ];
  const visible = knownFiles.filter(
    (f) =>
      !f.path.split("/").some((p) => p.startsWith(".")) &&
      !/^(matrices|artifacts\/matrices)\//.test(f.path) &&
      !/\.(json|jsonl|lock|db)$/i.test(f.path),
  );
  if (visible.length)
    addCollection(result, "materials", "项目资料", "folder", 0, 50);
  const counts = new Map<string, number>();
  const nextPosition = (parent: string) => {
    const n = counts.get(parent) ?? 0;
    counts.set(parent, n + 1);
    return { x: (n % 4) * 350, y: Math.floor(n / 4) * 430 };
  };
  for (const file of visible) {
    const parts = file.path.replace(/^sources\//, "").split("/");
    let parent = "materials";
    for (let i = 0; i < parts.length - 1; i++) {
      const id = `directory:${parts.slice(0, i + 1).join("/")}`;
      if (!result.collections[id]) {
        const p = nextPosition(parent);
        addCollection(result, id, parts[i]!, "folder", p.x, p.y, parent);
      }
      parent = id;
    }
    const pdf = documents.find(
      (doc) => doc.path === file.path && doc.origin_sha256 && doc.has_preview,
    );
    const id = pdf ? `pdf:${pdf.origin_sha256}` : `file:${file.path}`,
      kind = fileKind(file.path),
      pos = nextPosition(parent);
    addEntity(
      result,
      {
        id,
        kind,
        title: pdf ? parts.at(-1)!.replace(/\.md$/i, ".pdf") : parts.at(-1)!,
        path: pdf ? file.path.replace(/\.md$/i, ".pdf") : file.path,
        src: pdf
          ? documentAssetUrl(projectId, pdf.id, "preview")
          : workspaceFileUrl(projectId, file.path),
        downloadSrc: pdf
          ? documentAssetUrl(projectId, pdf.id, "original")
          : undefined,
        size: pdf ? undefined : file.size,
        status: "ready",
        subtitle: pdf
          ? "PDF · 原文已就绪"
          : `${parts.at(-1)?.split(".").pop()?.toUpperCase()} · ${formatSize(file.size)}`,
      },
      pos.x,
      pos.y,
      parent,
      280,
      kind === "image" || kind === "video" ? 210 : 374,
    );
  }
  const byDoc = new Map(
    documents.map((d) => [
      d.id,
      d.origin_sha256 && d.has_preview
        ? `pdf:${d.origin_sha256}`
        : `file:${d.path}`,
    ]),
  );
  for (const entity of Object.values(result.entities))
    for (const ref of entity.sourceRefs ?? []) {
      const to = ref.document_id ? byDoc.get(ref.document_id) : undefined;
      if (to && result.entities[to])
        result.relations.push({
          id: `${entity.id}:source:${to}`,
          from: entity.id,
          to,
          kind: "source",
        });
    }
  result.relations = [
    ...new Map(result.relations.map((r) => [r.id, r])).values(),
  ];
  return result;
}
