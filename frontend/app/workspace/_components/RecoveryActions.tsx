"use client";

import { useWorkspaceStore } from "@/lib/store/workspace";

/** 失败恢复仅调用已有能力；恢复要求先回填，由用户判断是否再次发送。 */
export function RecoveryActions() {
  const model = useWorkspaceStore((s) => s.modelRecovery);
  const recovery = useWorkspaceStore((s) => s.recovery);
  const retry = useWorkspaceStore((s) => s.retryOperation);
  const projectId = useWorkspaceStore((s) => s.projectId);
  const label = recovery === "parse" ? "重试文件提交" : recovery === "message" ? "恢复上次要求" : recovery === "session" ? "重试新建会话" : "重新加载结果";
  return <div className="workspace-recovery">
    <p>{model.failure?.action ?? (model.cancelled ? "可恢复上次要求，确认后重新发送。" : recovery === "parse" ? "文件与补充要求已保留，可重新尝试提交。" : recovery === "message" ? "连接中断时，任务可能仍在处理。先核对已更新的结果，再决定是否重发。" : "已有结果会保留。可以重新加载，或说明需要继续处理的内容。")}</p>
    {model.checkpointSaved && <p>已有成果已保存。</p>}
    {model.failure?.checkpoint_message && <p>{model.failure.checkpoint_message}</p>}
    {model.failure?.category && <details className="model-error-details"><summary>技术详情</summary><dl>
      <dt>错误类别</dt><dd>{model.failure.category}</dd>
      {model.failure.attempts != null && <><dt>请求次数</dt><dd>{model.failure.attempts}</dd></>}
      {model.failure.status_code != null && <><dt>HTTP 状态</dt><dd>{model.failure.status_code}</dd></>}
      {model.failure.request_id && <><dt>请求标识</dt><dd>{model.failure.request_id}</dd></>}
    </dl></details>}
    <div>{(recovery || projectId) && <button type="button" className="prose-button" onClick={() => { void retry(); if (recovery === "message") requestAnimationFrame(() => document.querySelector<HTMLTextAreaElement>(".composer textarea")?.focus()); }}>{label}</button>}
      {projectId && recovery !== "parse" && <button type="button" className="prose-text-button" onClick={() => {
        const state = useWorkspaceStore.getState();
        state.setComposerDraft("请检查本项目目前已完成的解析结果，说明中断或缺失的部分，并继续完成。"); state.setStreamSize("min");
        requestAnimationFrame(() => document.querySelector<HTMLTextAreaElement>(".composer textarea")?.focus());
      }}>补充继续处理的要求</button>}
    </div>
  </div>;
}
