"use client";

import { create } from "zustand";
import {
  createProject,
  createSession,
  getProject,
  patchProject,
  uploadProjectSample,
  uploadProjectFile,
  streamMessage,
  getMatrixStatus,
  getMatrixOverview,
  fetchAllMatrixItems,
  confirmMatrixItem,
  setMatrixItemResponseStatus,
  MatrixWriteConflictError,
  type SSEEvent,
} from "@/lib/hagent/api";
import { reduceChatEvent, type ChatMsg } from "@/lib/hagent/timeline";
import {
  MATRIX_TYPES,
  assembleMatrixDocument,
  isPublishedState,
  type BasicInfoMatrix,
  type BusinessMatrix,
  type MatrixItemRow,
  type MatrixType,
  type ResponseStatus,
  type ScoringMatrix,
  type TechnicalMatrix,
} from "@/lib/hagent/matrix";
import { prettyLabel } from "@/lib/hagent/naming";

export type RunPhase = "idle" | "creating" | "uploading" | "running" | "loading_results" | "done" | "error";

/* ---------- 矩阵结果槽位 ---------- */

export type MatrixSlotStatus = "empty" | "loading" | "ready" | "error";

export interface MatrixSlot<T> {
  status: MatrixSlotStatus;
  data: T | null;
  /** items 区段的对象库行级状态(确认/应答状态/乐观锁版本),抽屉人工动作用 */
  itemRows?: MatrixItemRow[];
  error?: string;
}

export interface MatrixSlots {
  basic_info: MatrixSlot<BasicInfoMatrix>;
  business: MatrixSlot<BusinessMatrix>;
  technical: MatrixSlot<TechnicalMatrix>;
  scoring: MatrixSlot<ScoringMatrix>;
}

const emptySlot = <T,>(): MatrixSlot<T> => ({ status: "empty", data: null });

const emptyMatrices = (): MatrixSlots => ({
  basic_info: emptySlot<BasicInfoMatrix>(),
  business: emptySlot<BusinessMatrix>(),
  technical: emptySlot<TechnicalMatrix>(),
  scoring: emptySlot<ScoringMatrix>(),
});

/** 拼装结果对四槽位类型皆可赋值(全字段可缺失 + index signature),集中一处断言 */
type AnyMatrix = BasicInfoMatrix & BusinessMatrix & TechnicalMatrix & ScoringMatrix;

/** 画布左上角消息浮窗的尺寸档。 */
export type StreamSize = "capsule" | "normal" | "expanded";

interface WorkspaceState {
  // —— UI 状态 ——
  composerDraft: string;
  /** 消息浮窗的尺寸档。放 store 而非组件本地:浮窗自身、底部坞的活动条、以及
   *  「出错自动展开」分处三棵互不相邻的子树;提到共同父级就是 CanvasPane,
   *  那会让每次改档都重渲整套卡片编排机器。与 SSE 批处理完全正交——
   *  flush 只写 timeline/todos/matrices,新增切片对热路径零成本。
   *  纪律:消费方一律用字段选择器订阅,且**不要**在 AgentStream 内读它
   *  (它在流式期每帧重渲)。 */
  streamSize: StreamSize;
  /** 胶囊态展开时回到的档位(记住用户上次留下的窗形)。 */
  lastOpenSize: Exclude<StreamSize, "capsule">;

  // —— 解析运行状态 ——
  sessionId: string | null;
  projectId: string | null;
  projectName: string | null;
  phase: RunPhase;
  errorMsg: string | null;
  currentDocName: string | null; // 当前解析文件的展示名
  timeline: ChatMsg[];
  todos: unknown[];
  /** 四张应答矩阵结果槽位(数据源:hagent 对象库 REST 读端点) */
  matrices: MatrixSlots;
  /** 本浏览器会话是否亲历解析(startParse 路径)。仅存内存、不持久化:
   *  恢复/刷新路径为 false,画布编排据此决定播放停靠飞行还是直接落停靠位。 */
  witnessedParse: boolean;

  // —— actions ——
  setComposerDraft: (text: string) => void;
  setStreamSize: (next: StreamSize) => void;
  pushEvent: (ev: SSEEvent) => void;
  flushEvents: () => void;
  /** 全量对账装载;settle=false(流中断路径)时不把未发布槽位落终态,留给「解析中断」定格。 */
  loadResults: (opts?: { settle?: boolean }) => Promise<void>;
  startParse: (opts: {
    sampleName?: string;
    sampleLabel?: string;
    file?: File;
    projectName?: string;
    instruction?: string;
  }) => Promise<void>;
  /** 项目内自由对话:续写/修改工作区产物;会话缺失时按当前项目惰性新建。 */
  sendMessage: (content: string) => Promise<void>;
  /** 项目内新建会话:新会话共享同一项目 workspace,可续写此前会话的产物。 */
  newSession: () => Promise<void>;
  /** 从 projects 页恢复:查四矩阵状态端点装载已发布矩阵,不回放 timeline(本迭代范围)。 */
  resumeProject: (pid: string, name?: string) => Promise<void>;
  /** 抽屉人工动作:确认条目(审计 actor=user);乐观锁冲突时重载该矩阵后抛出。 */
  confirmItem: (type: MatrixType, itemId: string) => Promise<void>;
  /** 抽屉人工动作:标注应答状态(合规/正偏离/负偏离);并发守卫同 confirmItem。 */
  setItemResponseStatus: (type: MatrixType, itemId: string, status: ResponseStatus) => Promise<void>;
  reset: () => void;
}

const BUSY: RunPhase[] = ["creating", "uploading", "running", "loading_results"];

// —— SSE prose 工具事件 → 槽位推导 ——
// 解析期间槽位状态由对象库工具事件驱动(spec §8):worker 用 prose_submit_matrix_records
// 提交条目时该矩阵翻「解析中」,prose_publish_matrix 完成即从 REST 装载点亮(逐张)。
const PROSE_SUBMIT_TOOL = "prose_submit_matrix_records";
const PROSE_PUBLISH_TOOL = "prose_publish_matrix";
// 工具入参里的矩阵名:args 是流式分片,对累积串做正则提取,不等 JSON 闭合
const MATRIX_ARG_RE = /"matrix"\s*:\s*"(basic_info|business|technical|scoring)"/;

export const useWorkspaceStore = create<WorkspaceState>((set, get) => {
  // —— SSE 按帧批处理 ——
  // 后端 message.delta 是逐 token 帧，一次解析可上千帧。若每帧一次 set，React 在
  // for-await 的每个 await 边界都会 flush 渲染，渲染次数随时间线增长叠加成 O(N²)，
  // 越跑越卡。这里把事件缓冲，用 rAF 合并到「每帧一次 set」，并在每帧内串联 reduce。
  let pending: SSEEvent[] = [];
  let raf = 0;

  // prose 工具调用累积(按 call_id 拼 args 分片,SSE 契约 §4.2);流开始前清空
  const proseCalls = new Map<string, { tool: string; args: string; matrix: MatrixType | null }>();

  const clearPending = () => {
    pending = [];
    proseCalls.clear();
    if (raf) {
      if (typeof cancelAnimationFrame !== "undefined") cancelAnimationFrame(raf);
      raf = 0;
    }
  };

  /** 消化一条 prose 工具事件:submit 进度 → toLoading;publish 完成 → toLoad(触发装载)。
   *  worker 在子代理里调工具,事件带 parent_tool_use_id——归属与推导无关,一律按 call_id 看。 */
  const trackProseEvent = (ev: SSEEvent, toLoading: Set<MatrixType>, toLoad: Set<MatrixType>) => {
    if (ev.event === "tool_call.started") {
      const d = ev.data as { call_id?: string | null; tool_name?: string; args_chunk?: string };
      if (!d.call_id) return;
      // 已跟踪的调用按 call_id 续接分片,不再校验 tool_name(极早期分片可能为空,契约 §4.2)
      let entry = proseCalls.get(d.call_id);
      if (!entry) {
        const name = d.tool_name || "";
        if (name !== PROSE_SUBMIT_TOOL && name !== PROSE_PUBLISH_TOOL) return;
        entry = { tool: name, args: "", matrix: null };
        proseCalls.set(d.call_id, entry);
      }
      entry.args += d.args_chunk || "";
      if (!entry.matrix) {
        const m = MATRIX_ARG_RE.exec(entry.args);
        if (m) entry.matrix = m[1] as MatrixType;
      }
      if (entry.tool === PROSE_SUBMIT_TOOL && entry.matrix) toLoading.add(entry.matrix);
      return;
    }
    if (ev.event === "tool_call.completed") {
      const d = ev.data as { call_id?: string | null };
      if (!d.call_id) return;
      const entry = proseCalls.get(d.call_id);
      if (!entry) return;
      proseCalls.delete(d.call_id);
      // publish 失败(门禁拒绝)时装载会发现矩阵未发布而不落数据,槽位维持解析中
      if (entry.tool === PROSE_PUBLISH_TOOL && entry.matrix) toLoad.add(entry.matrix);
    }
  };

  const flush = () => {
    raf = 0;
    if (pending.length === 0) return;
    const batch = pending;
    pending = [];
    const toLoading = new Set<MatrixType>();
    const toLoad = new Set<MatrixType>();
    for (const ev of batch) trackProseEvent(ev, toLoading, toLoad);
    set((s) => {
      let timeline = s.timeline;
      let todos = s.todos;
      for (const ev of batch) {
        if (ev.event === "todo.updated") {
          const d = ev.data as { todos?: unknown[] };
          if (Array.isArray(d?.todos)) todos = d.todos;
        }
        // reduceChatEvent 处理 message.delta / tool_call.* / error，忽略其余事件。
        timeline = reduceChatEvent(timeline, { event: ev.event, data: ev.data });
      }
      let matrices = s.matrices;
      if (toLoading.size) {
        matrices = { ...matrices };
        for (const t of toLoading) {
          // 只把待命/失败槽翻「解析中」;已就绪槽(逃生门重抽)保留旧数据直到重新发布
          if (matrices[t].status === "empty" || matrices[t].status === "error") {
            matrices[t] = { status: "loading", data: null };
          }
        }
      }
      return { timeline, todos, matrices };
    });
    // publish 完成 → 装载该矩阵点亮;失败留待流末 loadResults 收口,不打断对话流。
    if (toLoad.size) {
      const pid = get().projectId;
      if (pid) for (const t of toLoad) void ensureMatrixLoad(pid, t).catch(() => {});
    }
  };

  /** 装载单张矩阵:overview(envelope+state)+ 条目全量分页 → 拼回旧 final JSON 形状。
   *  返回矩阵是否已发布;projectId 已切换时放弃写入(防串台)。 */
  const loadMatrix = async (pid: string, t: MatrixType): Promise<boolean> => {
    const alive = () => get().projectId === pid;
    // 已就绪的槽位保留旧数据直到新数据到达(stale-while-revalidate),避免刷新闪空。
    set((s) => {
      if (s.matrices[t].status === "ready") return {};
      return { matrices: { ...s.matrices, [t]: { status: "loading", data: null } } };
    });
    try {
      const overview = await getMatrixOverview(pid, t);
      // 未发布(empty/drafting):不是错误,槽位维持现状等待 publish 事件
      if (!isPublishedState(overview.state)) return false;
      const rows = await fetchAllMatrixItems(pid, t);
      if (!alive()) return true;
      const data = assembleMatrixDocument(overview.meta, rows) as AnyMatrix;
      const itemRows = rows.filter((r) => r.section === "items");
      set((s) => ({
        matrices: { ...s.matrices, [t]: { status: "ready", data, itemRows } },
      }));
      return true;
    } catch (e) {
      if (!alive()) return false;
      set((s) => ({
        matrices: {
          ...s.matrices,
          [t]: { status: "error", data: null, error: e instanceof Error ? e.message : String(e) },
        },
      }));
      return false;
    }
  };

  // —— 矩阵装载去重 ——
  // publish 事件触发的逐张装载与流末/恢复路径的全量装载可能并发;同 (pid, type) 共用
  // 一个 in-flight promise,切换项目则各自独立(旧装载靠 alive() 放弃写入)。
  const matrixLoads = new Map<string, Promise<boolean>>();
  const ensureMatrixLoad = (pid: string, t: MatrixType): Promise<boolean> => {
    const key = `${pid}:${t}`;
    let p = matrixLoads.get(key);
    if (!p) {
      p = loadMatrix(pid, t).finally(() => {
        if (matrixLoads.get(key) === p) matrixLoads.delete(key);
      });
      matrixLoads.set(key, p);
    }
    return p;
  };

  /** 全量装载:查四矩阵状态端点,已发布的并行装载。返回是否存在已发布矩阵。
   *  settle(流正常收尾/恢复路径)时未发布槽位落 error 终态——停靠以「四槽位全部终态」
   *  为闸(choreography),部分发布失败不能让编排卡在中心舞台;流中断路径不 settle,
   *  未终态槽位留给「解析中断」如实定格。全部未发布时统一回落等待态(调用方随即报错)。 */
  const loadMatrices = async (pid: string, settle: boolean): Promise<boolean> => {
    const alive = () => get().projectId === pid;
    const status = await getMatrixStatus(pid);
    const published = new Set(
      status.matrices.filter((m) => isPublishedState(m.state)).map((m) => m.matrix_type),
    );
    if (!alive()) return published.size > 0;
    // 不动已就绪槽,防状态端点与装载间隙的偶发倒退
    set((s) => {
      const matrices = { ...s.matrices };
      for (const t of MATRIX_TYPES) {
        if (published.has(t) || matrices[t].status === "ready") continue;
        if (published.size === 0) {
          matrices[t] = { status: "empty", data: null };
        } else if (settle) {
          matrices[t] = { status: "error", data: null, error: "解析结束但该矩阵未发布" };
        }
      }
      return { matrices };
    });
    await Promise.all(
      MATRIX_TYPES.filter((t) => published.has(t)).map((t) => ensureMatrixLoad(pid, t)),
    );
    return published.size > 0;
  };

  // 发起解析/对话时保证回复面在场:胶囊态抬回上次的窗形,其余不动。
  // 用户刚对智能体说了话,回复必须有落点——这是状态指示,不是抢焦点。
  const revealStream = (s: WorkspaceState): Partial<WorkspaceState> =>
    s.streamSize === "capsule" ? { streamSize: s.lastOpenSize } : {};

  return {
  composerDraft: "",
  streamSize: "normal",
  lastOpenSize: "normal",

  sessionId: null,
  projectId: null,
  projectName: null,
  phase: "idle",
  errorMsg: null,
  currentDocName: null,
  timeline: [],
  todos: [],
  matrices: emptyMatrices(),
  witnessedParse: false,

  setComposerDraft: (text) => set({ composerDraft: text }),
  // 展开档同时记进 lastOpenSize:胶囊再打开时回到用户上次留下的窗形,而非固定 normal。
  setStreamSize: (next) =>
    set(next === "capsule" ? { streamSize: next } : { streamSize: next, lastOpenSize: next }),

  pushEvent: (ev) => {
    pending.push(ev);
    if (!raf) {
      raf =
        typeof requestAnimationFrame !== "undefined"
          ? requestAnimationFrame(flush)
          : (setTimeout(flush, 16) as unknown as number);
    }
  },
  // 流结束/阶段切换前同步落地缓冲，确保末帧事件不被丢在 buffer 里。
  flushEvents: () => {
    if (raf && typeof cancelAnimationFrame !== "undefined") cancelAnimationFrame(raf);
    raf = 0;
    flush();
  },

  loadResults: async (opts) => {
    const pid = get().projectId;
    if (!pid) return;
    const found = await loadMatrices(pid, opts?.settle ?? true);
    if (!found) throw new Error("项目中未找到已发布的应答矩阵");
  },

  startParse: async ({ sampleName, sampleLabel, file, projectName, instruction }) => {
    if (BUSY.includes(get().phase)) return;
    clearPending();
    set((s) => ({
      ...revealStream(s),
      phase: "creating",
      errorMsg: null,
      timeline: [],
      todos: [],
      matrices: emptyMatrices(),
      witnessedParse: true,
      sessionId: null,
      projectId: null,
      projectName: null,
      currentDocName: sampleLabel || file?.name || sampleName || "招标文件",
    }));
    try {
      // 1) 创建项目(会话必须归属项目,创建失败即终止)
      const projName =
        projectName || sampleLabel || (file ? prettyLabel(file.name) : "") || "未命名项目";
      const proj = await createProject(projName, {
        doc_name: file?.name || sampleName || "招标文件.md",
      });
      set({ projectId: proj.id, projectName: proj.name });

      // 2) 会话 + 上传到项目 workspace(落 sources/ 并形成提交)
      const { session_id } = await createSession({ projectId: proj.id });
      set({ sessionId: session_id });

      set({ phase: "uploading" });
      let docName: string;
      if (file) {
        await uploadProjectFile(proj.id, file);
        docName = file.name;
      } else if (sampleName) {
        await uploadProjectSample(proj.id, sampleName);
        docName = "招标文件.md"; // upload-sample 统一改名
      } else {
        throw new Error("缺少待解析文件");
      }

      // 3) 显式触发 bid-response-matrix skill(/skill: 语法糖由服务端展开为 Skill 工具调用)
      const defaultInstruction = `解析当前工作区 sources/ 目录下的招标文件《${docName}》，生成 basic_info、business、technical、scoring 四张应答矩阵`;
      const extraInstruction = instruction?.trim();
      const content = `/skill:bid-response-matrix ${defaultInstruction}${extraInstruction ? `。补充要求：${extraInstruction}` : ""}`;
      set((s) => ({
        timeline: [...s.timeline, { id: `u-${Date.now()}`, role: "user", content }],
        phase: "running",
      }));

      // error 帧后流即终止不再有 done(SSE 契约 §4.9),需据此分流相位。
      let streamError: string | null = null;
      for await (const ev of streamMessage(session_id, content)) {
        if (ev.event === "error") {
          streamError = (ev.data as { message?: string })?.message ?? "智能体执行异常";
        }
        get().pushEvent(ev);
      }
      get().flushEvents();

      if (streamError) {
        // error 前可能已 publish 出部分矩阵,best-effort 装载后仍落错误态;
        // 不 settle:未发布槽位保持非终态,卡面如实定格「解析中断」。
        set({ phase: "loading_results" });
        await get().loadResults({ settle: false }).catch(() => {});
        set({ phase: "error", errorMsg: streamError });
        return;
      }

      // 流末收口:publish 事件已逐张点亮,这里全量对账(防事件缺漏),一张未发布即报错。
      set({ phase: "loading_results" });
      await get().loadResults();
      set({ phase: "done" });

      // 4) 至少一张矩阵就绪才标记项目已解析(fire-and-forget,失败静默)
      const anyReady = MATRIX_TYPES.some((t) => get().matrices[t].status === "ready");
      if (anyReady) void patchProject(proj.id, { status: "parsed" }).catch(() => {});
    } catch (e) {
      set({ phase: "error", errorMsg: e instanceof Error ? e.message : String(e) });
    }
  },

  sendMessage: async (content) => {
    const text = content.trim();
    const pid = get().projectId;
    if (!text || !pid || BUSY.includes(get().phase)) return;
    clearPending();
    set((s) => ({
      ...revealStream(s),
      phase: "running",
      errorMsg: null,
      timeline: [...s.timeline, { id: `u-${Date.now()}`, role: "user", content: text }],
    }));
    try {
      let sid = get().sessionId;
      if (!sid) {
        const { session_id } = await createSession({ projectId: pid });
        sid = session_id;
        set({ sessionId: sid });
      }
      // error 帧后流即终止不再有 done(SSE 契约 §4.9),需据此分流相位。
      let streamError: string | null = null;
      for await (const ev of streamMessage(sid, text)) {
        if (ev.event === "error") {
          streamError = (ev.data as { message?: string })?.message ?? "智能体执行异常";
        }
        get().pushEvent(ev);
      }
      get().flushEvents();
      // 画布刷新由流内 prose 工具事件驱动(submit → 解析中,publish → 装载点亮);
      // 无矩阵写入的轮次无需刷新。
      set(streamError ? { phase: "error", errorMsg: streamError } : { phase: "done" });
    } catch (e) {
      set({ phase: "error", errorMsg: e instanceof Error ? e.message : String(e) });
    }
  },

  newSession: async () => {
    const pid = get().projectId;
    if (!pid || BUSY.includes(get().phase)) return;
    clearPending();
    const hasResults = MATRIX_TYPES.some((t) => get().matrices[t].status === "ready");
    set({ phase: "creating", errorMsg: null });
    try {
      const { session_id } = await createSession({ projectId: pid });
      // 新会话清空对话与任务;矩阵是项目级对象库资产,保留供续写。
      set({
        sessionId: session_id,
        timeline: [],
        todos: [],
        phase: hasResults ? "done" : "idle",
      });
    } catch (e) {
      set({ phase: "error", errorMsg: e instanceof Error ? e.message : String(e) });
    }
  },

  resumeProject: async (pid, name) => {
    if (BUSY.includes(get().phase)) return;
    // 本浏览器会话里已经在看这个项目(含解析后停留),不重复恢复
    if (get().projectId === pid && get().phase !== "idle") return;
    clearPending();
    set({
      phase: "loading_results",
      errorMsg: null,
      timeline: [],
      todos: [],
      matrices: emptyMatrices(),
      witnessedParse: false,
      sessionId: null,
      projectId: pid,
      projectName: name ?? null,
      currentDocName: name ?? "招标文件",
    });
    try {
      const proj = await getProject(pid);
      set({ projectName: proj.name });
      // 数据源是对象库 REST(矩阵状态端点 → 已发布矩阵逐张装载),不再扫 workspace 文件;
      // 会话在用户发消息或点「新建会话」时才创建。
      await get().loadResults();
      set({ phase: "done" });
    } catch (e) {
      set({ phase: "error", errorMsg: e instanceof Error ? e.message : String(e) });
    }
  },

  confirmItem: async (type, itemId) => {
    const pid = get().projectId;
    if (!pid) throw new Error("当前无项目上下文");
    const row = get().matrices[type].itemRows?.find((r) => r.item_id === itemId);
    // 无行级状态即无乐观锁基准,拒绝盲写(理论边界:动作入口只在行渲染后出现)
    if (!row) throw new Error("条目状态未装载，请刷新后重试");
    try {
      const updated = await confirmMatrixItem(pid, type, itemId, row.version);
      set((s) => replaceItemRow(s.matrices, type, updated));
    } catch (e) {
      // 乐观锁冲突:后台重载该矩阵取回当前版本,由调用方提示用户重试
      if (e instanceof MatrixWriteConflictError) void ensureMatrixLoad(pid, type).catch(() => {});
      throw e;
    }
  },

  setItemResponseStatus: async (type, itemId, status) => {
    const pid = get().projectId;
    if (!pid) throw new Error("当前无项目上下文");
    const row = get().matrices[type].itemRows?.find((r) => r.item_id === itemId);
    if (!row) throw new Error("条目状态未装载，请刷新后重试");
    try {
      const updated = await setMatrixItemResponseStatus(pid, type, itemId, {
        status,
        expectedVersion: row.version,
      });
      set((s) => replaceItemRow(s.matrices, type, updated));
    } catch (e) {
      if (e instanceof MatrixWriteConflictError) void ensureMatrixLoad(pid, type).catch(() => {});
      throw e;
    }
  },

  reset: () => {
    clearPending();
    set({
      sessionId: null,
      projectId: null,
      projectName: null,
      phase: "idle",
      errorMsg: null,
      currentDocName: null,
      timeline: [],
      todos: [],
      matrices: emptyMatrices(),
      witnessedParse: false,
      composerDraft: "",
      streamSize: "normal",
      lastOpenSize: "normal",
    });
  },
  };
});

/** 人工动作落库后原位替换行级状态(payload 不因确认/标注而变,拼装结果无需重算)。 */
function replaceItemRow(
  matrices: MatrixSlots,
  type: MatrixType,
  updated: MatrixItemRow,
): { matrices: MatrixSlots } {
  const slot = matrices[type];
  const itemRows = slot.itemRows?.map((r) => (r.item_id === updated.item_id ? updated : r));
  return { matrices: { ...matrices, [type]: { ...slot, itemRows } } };
}

// dev 调试：把 store 暴露到 window，便于在浏览器控制台驱动/检查解析状态。
if (process.env.NODE_ENV !== "production" && typeof window !== "undefined") {
  (window as unknown as { __ws?: typeof useWorkspaceStore }).__ws = useWorkspaceStore;
}
