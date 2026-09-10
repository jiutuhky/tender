import { HAGENT_BASE, authHeaders } from "@/lib/server/upstream";

export async function POST(_req: Request, ctx: { params: Promise<{ sid: string; runId: string }> }) {
  const { sid, runId } = await ctx.params;
  try {
    const response = await fetch(`${HAGENT_BASE}/sessions/${encodeURIComponent(sid)}/runs/${encodeURIComponent(runId)}/cancel`, { method: "POST", headers: authHeaders() });
    return new Response(response.body, { status: response.status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
  } catch {
    return Response.json({ detail: { message: "停止请求未送达，请检查执行服务连接。" } }, { status: 502 });
  }
}
