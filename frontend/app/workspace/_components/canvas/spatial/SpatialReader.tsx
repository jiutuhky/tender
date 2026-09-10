"use client";

/* 原生媒体支持浏览器上传 URL、缩放和播放控制。 */
/* eslint-disable @next/next/no-img-element */
import { useEffect, useState } from "react";
import { Response } from "@/components/ai-elements/response";
import { DownloadIcon, FileTextIcon, PenIcon } from "@/components/ui/icons";
import { useWorkspaceStore } from "@/lib/store/workspace";
import type { CanvasEntity, CanvasRelation, Rect } from "@/lib/canvas/model";
import {
  downloadEntity,
  isTextFile,
  readTextPreview,
} from "@/lib/canvas/files";
import { CanvasDrawer } from "../CanvasDrawer";
import { ItemActions, SourceChips, useItemAction } from "../detailShared";
import { useAssetUrl } from "./SpatialCard";

function MatrixItemBody({ entity }: { entity: CanvasEntity }) {
  const type = entity.matrixType!,
    row = useWorkspaceStore((s) =>
      s.matrices[type].itemRows?.find((r) => r.item_id === entity.itemId),
    );
  const actions = useItemAction(type);
  return (
    <div className="sp-entity-reading">
      <div className="sp-reading-kicker">
        {entity.group}
        {entity.score !== undefined && <b>{entity.score} 分</b>}
      </div>
      <h1>{entity.title}</h1>
      <Response>{entity.body ?? "内容尚未提取"}</Response>
      {entity.subtitle && (
        <section>
          <h3>材料与格式要求</h3>
          <p>{entity.subtitle}</p>
        </section>
      )}
      {row && (
        <ItemActions
          row={row}
          busy={actions.busyIds.has(row.item_id)}
          error={actions.errors[row.item_id] ?? null}
          onConfirm={() => actions.confirm(row.item_id)}
          onSetStatus={(status) => actions.setStatus(row.item_id, status)}
        />
      )}
      <section>
        <h3>原文依据</h3>
        <SourceChips
          refs={entity.sourceRefs ?? []}
          itemKey={entity.id}
          claim={{
            matrixType: type,
            itemId: entity.itemId ?? null,
            label: entity.group ?? entity.title,
            title: entity.title,
            requirementText: entity.body ?? "",
          }}
        />
      </section>
      {actions.notice && <p role="status">{actions.notice}</p>}
    </div>
  );
}

function EntityBody({
  entity,
  onEdit,
  onNavigate,
}: {
  entity: CanvasEntity;
  onEdit: (body: string, title: string) => void;
  onNavigate: (id: string) => void;
}) {
  const src = useAssetUrl(entity),
    [loaded, setLoaded] = useState<{ src: string; text: string } | null>(null),
    [error, setError] = useState("");
  const [editing, setEditing] = useState(false),
    [draft, setDraft] = useState(entity.body ?? ""),
    [title, setTitle] = useState(entity.title);
  useEffect(() => {
    if (!src || entity.body || !isTextFile(entity.path ?? entity.title)) return;
    const controller = new AbortController();
    void readTextPreview(src, controller.signal, 512_000, 0)
      .then((text) => setLoaded({ src, text }))
      .catch(() => {
        if (!controller.signal.aborted)
          setError("文档暂时无法读取，请关闭后重试。");
      });
    return () => controller.abort();
  }, [src, entity.body, entity.path, entity.title]);
  const body = entity.body || (loaded?.src === src ? loaded?.text : "");
  const download = () => {
    void downloadEntity(entity).catch(() =>
      setError("文件暂时无法下载，请重试。"),
    );
  };
  return (
    <div
      className={`sp-entity-reading${entity.kind === "image" || entity.kind === "video" ? " sp-media-reading" : ""}`}
    >
      <div className="sp-reading-actions">
        {entity.editable && (
          <button
            onClick={() => {
              if (editing) onEdit(draft, title);
              setEditing(!editing);
            }}
          >
            <PenIcon />
            {editing ? "保存修改" : "编辑内容"}
          </button>
        )}
        {(body || src) && (
          <button onClick={download}>
            <DownloadIcon />
            下载
          </button>
        )}
      </div>
      {error && <p role="alert">{error}</p>}
      {editing ? (
        <div className="sp-note-editor">
          <input
            aria-label="文稿标题"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <textarea
            aria-label="文稿正文"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
          />
          <button
            onClick={() => {
              setDraft(entity.body ?? "");
              setTitle(entity.title);
              setEditing(false);
            }}
          >
            取消编辑
          </button>
        </div>
      ) : entity.kind === "image" && src ? (
        <img className="sp-full-image" src={src} alt={entity.title} />
      ) : entity.kind === "video" && src ? (
        <video className="sp-full-video" src={src} controls playsInline />
      ) : (
        <>
          {(entity.group || entity.score !== undefined) && (
            <div className="sp-reading-kicker">
              {entity.group}
              {entity.score !== undefined && <b>{entity.score} 分</b>}
            </div>
          )}
          <h1>{entity.title}</h1>
          {entity.subtitle && (
            <p className="sp-reading-subtitle">{entity.subtitle}</p>
          )}
          {entity.outline && (
            <nav className="sp-outline-navigation" aria-label="文档目录">
              {entity.outline.map((item, i) => (
                <button
                  key={i}
                  style={{ paddingLeft: 12 + item.depth * 24 }}
                  disabled={!item.entityId}
                  onClick={() => item.entityId && onNavigate(item.entityId)}
                >
                  {item.title}
                </button>
              ))}
            </nav>
          )}
          {body ? (
            <Response>
              {body.startsWith(`# ${entity.title}\n`)
                ? body.slice(entity.title.length + 3).trimStart()
                : body}
            </Response>
          ) : src && /\.pdf$/i.test(entity.path ?? entity.title) ? (
            <iframe className="sp-pdf-reading" src={src} title={entity.title} />
          ) : (
            !entity.outline && (
              <div className="sp-reader-fallback">
                <FileTextIcon />
                <p>
                  {error ||
                    (src && isTextFile(entity.path ?? entity.title)
                      ? "正在读取文档…"
                      : "此格式暂不支持直接预览，可下载后查看。")}
                </p>
              </div>
            )
          )}
        </>
      )}
    </div>
  );
}

export function SpatialReader({
  entity,
  origin,
  relations,
  entities,
  onClose,
  onEdit,
  onNavigate,
}: {
  entity: CanvasEntity;
  origin?: Rect;
  relations: CanvasRelation[];
  entities: Record<string, CanvasEntity>;
  onClose: () => void;
  onEdit: (body: string, title: string) => void;
  onNavigate: (id: string) => void;
}) {
  const type = entity.matrixType ?? "chapter";
  return (
    <CanvasDrawer
      type={type}
      cardType={type}
      title={entity.title}
      subtitle={entity.statusText || entity.group || entity.subtitle}
      onClose={onClose}
      spatial
      origin={origin}
    >
      {entity.matrixType && !entity.itemId ? undefined : (
        <>
          {entity.matrixType ? (
            <MatrixItemBody entity={entity} />
          ) : (
            <EntityBody
              entity={entity}
              onEdit={onEdit}
              onNavigate={onNavigate}
            />
          )}
          {!!relations.length && (
            <section className="sp-reading-relations">
              <h3>关联内容</h3>
              {relations.map((r) => {
                const other = r.from === entity.id ? r.to : r.from;
                return (
                  <button key={r.id} onClick={() => onNavigate(other)}>
                    <span>
                      {r.kind === "source"
                        ? "原文依据"
                        : r.kind === "response"
                          ? "对应要求与章节"
                          : "使用素材"}
                    </span>
                    {entities[other]?.title ?? "关联资料"}
                  </button>
                );
              })}
            </section>
          )}
        </>
      )}
    </CanvasDrawer>
  );
}
