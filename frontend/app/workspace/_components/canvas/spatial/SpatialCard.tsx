"use client";

/* 原生媒体元素用于画布的动态尺寸预览与本地导入文件。 */
/* eslint-disable @next/next/no-img-element */
import {
  memo,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
} from "react";
import { gsap } from "gsap";
import {
  ArrowRightIcon,
  CheckIcon,
  FileTextIcon,
  FolderSimpleIcon,
  LayersIcon,
  PauseIcon,
  SparkleIcon,
  WarningIcon,
} from "@/components/ui/icons";
import {
  type CanvasCollection,
  type CanvasEntity,
  type CanvasPlacement,
} from "@/lib/canvas/model";
import { isTextFile, loadLocalFile, readTextPreview } from "@/lib/canvas/files";
import { getPdfThumbnail } from "@/lib/canvas/pdf-thumbnails";

export function useAssetUrl(entity: CanvasEntity) {
  const [local, setLocal] = useState<{ id: string; url: string } | null>(null);
  useEffect(() => {
    if (!entity.src?.startsWith("local:")) return;
    let cancelled = false,
      url: string | undefined;
    void loadLocalFile(entity.src.slice(6))
      .then((blob) => {
        if (cancelled || !blob) return;
        url = URL.createObjectURL(blob);
        setLocal({ id: entity.id, url });
      })
      .catch(() => {});
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [entity.id, entity.src]);
  return entity.src?.startsWith("local:")
    ? local?.id === entity.id
      ? local.url
      : undefined
    : entity.src;
}

function PdfThumbnail({ url, identity }: { url: string; identity?: string }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [failed, setFailed] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    void getPdfThumbnail(url, controller.signal, identity)
      .then((preview) => {
        if (controller.signal.aborted || !canvas.current) return;
        canvas.current.width = preview.width;
        canvas.current.height = preview.height;
        canvas.current.getContext("2d")?.drawImage(preview, 0, 0);
      })
      .catch(() => {
        if (!controller.signal.aborted) setFailed(url);
      });
    return () => controller.abort();
  }, [url, identity]);
  return failed === url ? (
    <div className="sp-document-mark" aria-label="预览暂不可用">
      <FileTextIcon />
    </div>
  ) : (
    <canvas
      ref={canvas}
      width={0}
      height={0}
      className="sp-pdf-thumbnail"
      aria-label="文档首页预览"
    />
  );
}

export function PaperText({ text }: { text: string }) {
  return (
    <div className="sp-paper-copy">
      {text
        .split("\n")
        .filter(Boolean)
        .slice(0, 16)
        .map((line, i) =>
          /^#{1,3}\s/.test(line) ? (
            <h4 key={i}>{line.replace(/^#+\s*/, "")}</h4>
          ) : (
            <p key={i}>{line.replace(/\*\*/g, "")}</p>
          ),
        )}
    </div>
  );
}

export const EntityFace = memo(function EntityFace({
  entity,
  preview = false,
  onMediaSize,
}: {
  entity: CanvasEntity;
  preview?: boolean;
  onMediaSize?: (width: number, height: number) => void;
}) {
  const url = useAssetUrl(entity),
    video = useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = useState(false),
    [text, setText] = useState<{ url: string; body: string } | null>(null),
    [broken, setBroken] = useState(false);
  useEffect(() => {
    if (
      !url ||
      !isTextFile(entity.path ?? entity.title) ||
      entity.body ||
      preview
    )
      return;
    const controller = new AbortController();
    void readTextPreview(url, controller.signal)
      .then((body) => setText({ url, body }))
      .catch(() => {});
    return () => controller.abort();
  }, [url, entity.body, entity.path, entity.title, preview]);
  useEffect(() => {
    const element = video.current;
    if (!element) return;
    const pause = () => {
      element.pause();
      setPlaying(false);
    };
    window.addEventListener("pointerdown", pause, true);
    window.addEventListener("blur", pause);
    return () => {
      window.removeEventListener("pointerdown", pause, true);
      window.removeEventListener("blur", pause);
    };
  }, []);
  const body = entity.body || (text?.url === url ? text?.body : "");
  if (entity.kind === "image" || entity.kind === "video")
    return (
      <div className="sp-media-face">
        {url && !broken ? (
          entity.kind === "image" ? (
            <img
              src={url}
              alt={entity.title}
              draggable={false}
              onError={() => setBroken(true)}
              onLoad={(e) =>
                onMediaSize?.(
                  e.currentTarget.naturalWidth,
                  e.currentTarget.naturalHeight,
                )
              }
            />
          ) : (
            <video
              ref={video}
              src={url}
              muted
              playsInline
              preload="metadata"
              onLoadedMetadata={(e) =>
                onMediaSize?.(
                  e.currentTarget.videoWidth,
                  e.currentTarget.videoHeight,
                )
              }
              onError={() => setBroken(true)}
              onPause={() => setPlaying(false)}
            />
          )
        ) : (
          <div className="sp-media-fallback">
            <FileTextIcon />
            <span>{broken ? "预览暂不可用" : "正在载入素材"}</span>
          </div>
        )}
        {entity.kind === "video" && !preview && url && (
          <button
            className="sp-play"
            aria-label={playing ? "暂停视频" : "播放视频"}
            onClick={(e) => {
              e.stopPropagation();
              if (playing) video.current?.pause();
              else
                void video.current
                  ?.play()
                  .then(() => setPlaying(true))
                  .catch(() => {});
            }}
          >
            {playing ? <PauseIcon /> : <ArrowRightIcon />}
          </button>
        )}
        {!preview && <span className="sp-media-caption">{entity.title}</span>}
      </div>
    );
  return (
    <div className={`sp-paper-face face-${entity.kind}`}>
      <div className="sp-paper-meta">
        <span>
          {entity.group ||
            (
              {
                summary: "项目概览",
                scoring: "评审标准",
                requirement: "招标要求",
                outline: "目录",
                chapter: "章节",
                final: "投标文件",
                document: "文档",
                note: "笔记",
              } as Record<string, string>
            )[entity.kind]}
        </span>
        {entity.number && <span>{entity.number}</span>}
        {entity.confirmed && <CheckIcon aria-label="已核验" />}
      </div>
      <h2>{entity.title}</h2>
      {typeof entity.score === "number" && (
        <div className="sp-score-value">
          {entity.score}
          <span>分</span>
        </div>
      )}
      {entity.kind === "final" && (
        <div className="sp-document-mark">
          <FileTextIcon />
        </div>
      )}
      {entity.outline && (
        <div className="sp-outline-preview">
          {entity.outline.slice(0, 7).map((item, i) => (
            <div key={i} style={{ paddingLeft: item.depth * 16 }}>
              <span>{item.title}</span>
              {entity.kind === "outline" && <i />}
            </div>
          ))}
        </div>
      )}
      {body && (
        <PaperText
          text={
            body.startsWith(`# ${entity.title}\n`)
              ? body.slice(entity.title.length + 3).trimStart()
              : body
          }
        />
      )}
      {!body &&
        entity.kind === "document" &&
        url &&
        /\.pdf$/i.test(entity.path ?? entity.title) &&
        !preview && <PdfThumbnail url={url} identity={entity.src} />}
      {!body &&
        entity.kind === "document" &&
        (!url || !/\.(pdf|md|txt|csv)$/i.test(entity.path ?? entity.title)) && (
          <div className="sp-document-mark">
            <FileTextIcon />
          </div>
        )}
      <div className="sp-paper-footer">
        <span>
          {entity.statusText ||
            entity.subtitle ||
            (entity.kind === "chapter" && body
              ? `${body.replace(/\s/g, "").length} 字 · 草稿`
              : "")}
        </span>
        {entity.status === "working" ? (
          <SparkleIcon />
        ) : entity.status === "error" || entity.status === "interrupted" ? (
          <WarningIcon />
        ) : entity.responseText ? (
          <span>{entity.responseText}</span>
        ) : null}
      </div>
    </div>
  );
});

interface CardProps {
  placement: CanvasPlacement;
  entity?: CanvasEntity;
  collection?: CanvasCollection;
  members: Array<{
    placement: CanvasPlacement;
    entity?: CanvasEntity;
    collection?: CanvasCollection;
  }>;
  count: number;
  selected: boolean;
  dimmed: boolean;
  onOpen: (id: string, keyboard?: boolean) => void;
  onFocus: (id: string) => void;
  editing?: boolean;
  onSaveNote: (id: string, title: string, body: string) => void;
  onCancelEdit: () => void;
  onMediaSize: (id: string, width: number, height: number) => void;
}

function NoteEditor({
  entity,
  save,
  cancel,
}: {
  entity: CanvasEntity;
  save: (title: string, body: string) => void;
  cancel: () => void;
}) {
  const [title, setTitle] = useState(entity.title),
    [body, setBody] = useState(entity.body ?? ""),
    cancelled = useRef(false);
  return (
    <div
      className="sp-inline-note"
      data-no-gesture
      onBlur={(e) => {
        if (!cancelled.current && !e.currentTarget.contains(e.relatedTarget))
          save(title, body);
      }}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          e.stopPropagation();
          cancelled.current = true;
          cancel();
        }
        if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
          e.preventDefault();
          save(title, body);
        }
      }}
    >
      <input
        aria-label="笔记标题"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
      />
      <textarea
        autoFocus
        aria-label="笔记正文"
        placeholder="写下你的想法…"
        value={body}
        onChange={(e) => setBody(e.target.value)}
      />
      <button onClick={() => save(title, body)}>
        完成 <CheckIcon />
      </button>
    </div>
  );
}

export const SpatialCard = memo(function SpatialCard({
  placement: p,
  entity,
  collection,
  members,
  count,
  selected,
  dimmed,
  onOpen,
  onFocus,
  editing,
  onSaveNote,
  onCancelEdit,
  onMediaSize,
}: CardProps) {
  const root = useRef<HTMLDivElement>(null);
  const mediaSizeChanged = useCallback(
    (width: number, height: number) => onMediaSize(p.id, width, height),
    [p.id, onMediaSize],
  );
  const memberKey = JSON.stringify(
    members.map((member) => member.placement.id),
  );
  const previousMembers = useRef<string[]>(JSON.parse(memberKey));
  const previousCount = useRef(count);
  useLayoutEffect(() => {
    const element = root.current?.querySelector(".sp-card-material");
    if (!element || matchMedia("(prefers-reduced-motion: reduce)").matches)
      return;
    const context = gsap.context(() => {
      gsap.from(element, {
        autoAlpha: 0,
        y: 6,
        duration: 0.22,
        ease: "power2.out",
        clearProps: "opacity,visibility,transform",
      });
    });
    return () => context.revert();
  }, []);
  useLayoutEffect(() => {
    const old = new Set(previousMembers.current),
      ids: string[] = JSON.parse(memberKey);
    const context = gsap.context(() => {
      if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
      for (const id of ids)
        if (!old.has(id)) {
          const paper = root.current?.querySelector(
            `.sp-folder-paper[data-motion-id="${CSS.escape(id)}"]`,
          );
          if (paper)
            gsap.from(paper, {
              y: "-=55",
              autoAlpha: 0,
              duration: 0.5,
              ease: "power3.out",
              clearProps: "transform,opacity,visibility",
            });
        }
      if (previousCount.current !== count) {
        const label = root.current?.querySelector(".sp-folder-count");
        if (label)
          gsap.fromTo(
            label,
            { y: 3, autoAlpha: 0.35 },
            { y: 0, autoAlpha: 1, duration: 0.22 },
          );
      }
    });
    previousMembers.current = ids;
    previousCount.current = count;
    return () => context.revert();
  }, [memberKey, count]);
  const kind = collection?.kind ?? entity?.kind ?? "document",
    title = collection?.title ?? entity?.title;
  return (
    <div
      ref={root}
      data-placement={p.id}
      data-motion-id={p.id}
      data-kind={kind}
      className={`sp-card kind-${kind}${selected ? " is-selected" : ""}${dimmed ? " is-dimmed" : ""}${entity?.status === "working" || collection?.status === "working" ? " is-working" : ""}`}
      style={{
        width: p.w,
        height: p.h,
        transform: `translate(${p.x}px,${p.y}px)`,
      }}
      role="group"
      inert={dimmed}
      aria-hidden={dimmed || undefined}
      tabIndex={dimmed ? -1 : 0}
      aria-label={`${title}${collection ? `，${count} 项` : ""}`}
      aria-roledescription={collection ? "集合" : "卡片"}
      onFocus={(e) => {
        if (e.target === e.currentTarget) onFocus(p.id);
      }}
      onDoubleClick={(e) => {
        if ((e.target as HTMLElement).closest("button,input,textarea")) return;
        e.stopPropagation();
        onOpen(p.id);
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter" && e.target === e.currentTarget) {
          e.preventDefault();
          onOpen(p.id, true);
        }
      }}
    >
      <div className={`sp-card-material color-${collection?.color ?? "white"}`}>
        {collection?.kind === "folder" ? (
          <div className="sp-folder">
            <div className="sp-folder-back" />
            <div className="sp-folder-papers">
              {members.slice(0, 3).map((child, i) => (
                <div
                  key={child.placement.id}
                  className={`sp-folder-paper paper-${i}`}
                  data-motion-id={child.placement.id}
                >
                  {child.entity ? (
                    <EntityFace entity={child.entity} preview />
                  ) : (
                    <div className="sp-mini-folder">
                      <FolderSimpleIcon />
                      <span>{child.collection?.title}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
            <div className="sp-folder-front">
              <span className="sp-folder-count">{count} 项内容</span>
              <button
                className="sp-folder-open"
                aria-label={`打开${title}`}
                onClick={(event) => onOpen(p.id, event.detail === 0)}
              >
                <ArrowRightIcon />
              </button>
              <div className="sp-folder-label">
                <h2>{title}</h2>
                <p>{collection.subtitle || "项目资料集合"}</p>
              </div>
              <FolderSimpleIcon className="sp-folder-symbol" />
            </div>
          </div>
        ) : collection?.kind === "stack" ? (
          <div className="sp-stack">
            {members
              .slice(0, 3)
              .reverse()
              .map((child, i, all) => (
                <div
                  key={child.placement.id}
                  className="sp-stack-sheet"
                  data-motion-id={child.placement.id}
                  style={
                    { "--sheet-index": all.length - 1 - i } as CSSProperties
                  }
                >
                  {child.entity ? (
                    <EntityFace entity={child.entity} preview />
                  ) : (
                    <div className="sp-mini-folder">
                      <LayersIcon />
                      <span>{child.collection?.title}</span>
                    </div>
                  )}
                </div>
              ))}
            {!members.length && (
              <div className="sp-stack-sheet sp-stack-empty">
                <LayersIcon />
                <h2>{title}</h2>
                <p>{collection.statusText || "拖入内容，开始整理"}</p>
              </div>
            )}
            <div className="sp-stack-label">
              <div>
                <h2>{title}</h2>
                <span>
                  {collection.statusText ||
                    collection.subtitle ||
                    `${count} 项内容`}
                </span>
              </div>
              <b>{collection.metric || `${count} 项`}</b>
            </div>
            <button
              className="sp-stack-open"
              aria-label={`展开${title}`}
              onClick={(event) => onOpen(p.id, event.detail === 0)}
            >
              <ArrowRightIcon />
            </button>
          </div>
        ) : entity ? (
          editing ? (
            <NoteEditor
              entity={entity}
              save={(title, body) => onSaveNote(p.entityId, title, body)}
              cancel={onCancelEdit}
            />
          ) : (
            <EntityFace entity={entity} onMediaSize={mediaSizeChanged} />
          )
        ) : null}
      </div>
      {!collection && selected && !editing && (
        <>
          <button
            className="sp-card-open"
            aria-label={`打开${title}`}
            onClick={(event) => onOpen(p.id, event.detail === 0)}
          >
            <ArrowRightIcon />
          </button>
          {["nw", "ne", "sw", "se"].map((corner) => (
            <span
              role="presentation"
              key={corner}
              data-corner={corner}
              className={`sp-resize corner-${corner}`}
            />
          ))}
        </>
      )}
    </div>
  );
});
