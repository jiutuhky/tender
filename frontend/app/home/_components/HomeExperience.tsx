"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";
import {
  ArrowElbowDownLeftIcon,
  ArrowUpIcon,
  FileIcon,
  LayersIcon,
  PaperclipIcon,
  PlusIcon,
  SparkIcon,
  UploadIcon,
} from "@/components/ui/icons";
import {
  DUR_FLOAT,
  DUR_PANEL,
  TRACE_EASE_ENTER,
  prefersReducedMotion,
} from "@/app/workspace/_components/canvas/traceMotion";
import {
  DEFAULT_INTENT,
  HOME_RECENT,
  HOME_SUGGESTIONS,
  KNOWLEDGE_REPLY,
} from "@/lib/mock/home";
import { useWorkspaceStore } from "@/lib/store/workspace";
import { prettyLabel } from "@/lib/hagent/naming";

/*
 * 统一 Agent 入口（登录后的首屏）：一个 composer 承担两种能力 ——
 *  1. 自由问答：直接向知识库 / 已有文件提问，对话在 composer 上方生长；
 *  2. 新建项目：把招标文件拖到窗口任何位置（或点「添加招标文件」），
 *     发送后直接进入 /workspace 开始解析（招标文件即项目）。
 * 动效走 gsap（进场 / 逐条浮现），reduced-motion 下瞬时呈现。
 */

interface Turn {
  role: "user" | "agent";
  text?: string;
  parts?: Array<{ text: string; strong?: boolean }>;
  sources?: string[];
}

/** 文件大小 → 「428 KB」/「4.2 MB」 */
function formatSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export function HomeExperience() {
  const router = useRouter();
  const rootRef = useRef<HTMLDivElement>(null);
  const threadRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const replyTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [fileErr, setFileErr] = useState<string | null>(null);
  const [received, setReceived] = useState(false); // 附件落下时 accent 描边一闪（一次性）
  const [dragging, setDragging] = useState(false);
  const startParse = useWorkspaceStore((s) => s.startParse);

  /* ---- 首屏进场：问候 + composer 依次浮现 ---- */
  useGSAP(
    () => {
      if (prefersReducedMotion()) return;
      gsap.from(".home-hero > *", {
        autoAlpha: 0,
        y: 8,
        duration: DUR_PANEL,
        stagger: 0.05,
        ease: TRACE_EASE_ENTER,
      });
    },
    { scope: rootRef },
  );

  /* ---- 新增对话回合进场（只动最后一条） ---- */
  useEffect(() => {
    const el = threadRef.current?.lastElementChild;
    if (!el || prefersReducedMotion()) return;
    gsap.from(el, { autoAlpha: 0, y: 6, duration: DUR_FLOAT, ease: TRACE_EASE_ENTER });
  }, [turns]);

  /* ---- 整窗拖放：页面任何位置都是投递区 ---- */
  useEffect(() => {
    let depth = 0;
    const enter = (e: DragEvent) => {
      e.preventDefault();
      depth += 1;
      setDragging(true);
    };
    const over = (e: DragEvent) => e.preventDefault();
    const leave = () => {
      depth = Math.max(0, depth - 1);
      if (depth === 0) setDragging(false);
    };
    const drop = (e: DragEvent) => {
      e.preventDefault();
      depth = 0;
      setDragging(false);
      const f = e.dataTransfer?.files?.[0];
      if (f) acceptFile(f);
    };
    window.addEventListener("dragenter", enter);
    window.addEventListener("dragover", over);
    window.addEventListener("dragleave", leave);
    window.addEventListener("drop", drop);
    return () => {
      window.removeEventListener("dragenter", enter);
      window.removeEventListener("dragover", over);
      window.removeEventListener("dragleave", leave);
      window.removeEventListener("drop", drop);
    };
  }, []);

  /* ---- 预取工作台，交棒时无白屏 ---- */
  useEffect(() => {
    router.prefetch("/workspace");
  }, [router]);

  useEffect(
    () => () => {
      if (replyTimer.current) clearTimeout(replyTimer.current);
    },
    [],
  );

  /** 挂载附件的统一入口(点选/拖放共用):校验 .md 后落附件行并预填意图。 */
  function acceptFile(f: File) {
    if (!/\.md$/i.test(f.name)) {
      setFileErr("目前仅支持 MinerU 导出的 .md 招标文件");
      return;
    }
    setFileErr(null);
    setFile(f);
    setReceived(true);
    setTimeout(() => setReceived(false), 900);
    const input = inputRef.current;
    if (input && !input.value.trim()) input.value = DEFAULT_INTENT;
    input?.focus();
  }

  function attachFile() {
    fileInputRef.current?.click();
  }

  function send() {
    const input = inputRef.current;
    const text = input?.value.trim() ?? "";
    if (file) {
      // 真实链路:创建项目 → 创建会话 → 上传 → /skill:bid-response-matrix 解析。
      // startParse 挂在全局 store 上,client 导航后运行态存活,工作台组件已订阅。
      void startParse({ file, projectName: prettyLabel(file.name) });
      router.push("/workspace");
      return;
    }
    if (!text) return;
    if (input) input.value = "";
    setTurns((t) => [...t, { role: "user", text }]);
    replyTimer.current = setTimeout(() => {
      setTurns((t) => [...t, { role: "agent", ...KNOWLEDGE_REPLY }]);
    }, 700);
  }

  return (
    <div className="home-entry" ref={rootRef}>
      <div className="home-entry-col">
        <div className="home-hero">
          <h1 className="home-greet">晚上好，李慧。</h1>
          <p className="home-greet-sub">向知识库提问，或把招标文件交给我。</p>
        </div>

        {/* 自由问答：对话在 composer 上方生长 */}
        <div className="home-thread" ref={threadRef}>
          {turns.map((turn, i) =>
            turn.role === "user" ? (
              <div className="home-turn-user" key={i}>
                {turn.text}
              </div>
            ) : (
              <div className="home-turn-agent" key={i}>
                {turn.parts?.map((p, j) =>
                  p.strong ? <b key={j}>{p.text}</b> : <span key={j}>{p.text}</span>,
                )}
                {turn.sources && (
                  <span className="home-turn-srcs">
                    {turn.sources.map((s) => (
                      <span className="home-src" key={s}>
                        <LayersIcon width={12} height={12} />
                        {s}
                      </span>
                    ))}
                  </span>
                )}
              </div>
            ),
          )}
        </div>

        {/* composer：平台唯一的门 */}
        <div className={`entry-composer${received ? " is-recv" : ""}`}>
          <input
            ref={fileInputRef}
            type="file"
            accept=".md,text/markdown"
            style={{ display: "none" }}
            aria-hidden="true"
            tabIndex={-1}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) acceptFile(f);
              e.target.value = "";
            }}
          />
          {file && (
            <div className="entry-att-row">
              <span className="entry-att">
                <FileIcon width={15} height={15} />
                <b>{file.name}</b>
                <span className="entry-att-size">{formatSize(file.size)}</span>
              </span>
            </div>
          )}
          <textarea
            ref={inputRef}
            name="entry-intent"
            rows={2}
            placeholder="问任何问题，或拖入一份招标文件开始新项目……"
            aria-label="向 Prose 提问或说明意图"
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
          />
          <div className="entry-composer-foot">
            <button className="entry-attach" type="button" onClick={attachFile}>
              <PaperclipIcon width={14} height={14} />
              添加招标文件
            </button>
            {fileErr ? (
              <span className="entry-note" style={{ color: "var(--red-text)" }}>
                {fileErr}
              </span>
            ) : (
              file && (
                <span className="entry-note">
                  <SparkIcon animated={false} width={13} height={13} />
                  已识别为招标文件，发送后将创建项目并开始解析
                </span>
              )
            )}
            <span className="entry-foot-spacer" />
            <span className="entry-kbd">
              <ArrowElbowDownLeftIcon width={12} height={12} />
              发送
            </span>
            <button className="entry-send" type="button" aria-label="发送" onClick={send}>
              <ArrowUpIcon width={14} height={14} />
            </button>
          </div>
        </div>

        {/* 建议 chips：问答与建项目两种能力并排示范 */}
        <div className="entry-chips">
          {HOME_SUGGESTIONS.map((s) => (
            <button
              className="entry-chip"
              type="button"
              key={s}
              onClick={() => {
                const input = inputRef.current;
                if (input) input.value = s;
                send();
              }}
            >
              {s}
            </button>
          ))}
          <button className="entry-chip is-new" type="button" onClick={attachFile}>
            <PlusIcon width={13} height={13} />
            上传招标文件，创建新项目
          </button>
        </div>

        {/* 最近项目 */}
        <div className="entry-recent">
          <h3>最近项目</h3>
          <div className="entry-recent-row">
            {HOME_RECENT.map((p) => (
              <Link className="entry-recent-card" href={p.href} key={p.name}>
                <b>{p.name}</b>
                <span className="entry-recent-meta">
                  <span className="entry-recent-status">{p.status}</span>
                  <span className="entry-recent-bar">
                    <i style={{ width: `${p.progress}%` }} />
                  </span>
                  <span className="entry-recent-ddl">{p.deadline}</span>
                </span>
              </Link>
            ))}
          </div>
        </div>
      </div>

      {/* 整窗拖放幕布：容器只动 background-color，玻璃卡自身动 opacity/transform
          （玻璃祖先禁 opacity<1，见 styles.css 注释） */}
      <div className={`entry-veil${dragging ? " is-on" : ""}`} aria-hidden="true">
        <div className="entry-veil-card frost-glass frost-glass--lens" data-thick="regular">
          <UploadIcon width={30} height={30} />
          <div className="entry-veil-title">松手，把招标文件交给 Prose</div>
          <div className="entry-veil-sub">将创建项目并立即开始解析</div>
        </div>
      </div>
    </div>
  );
}
