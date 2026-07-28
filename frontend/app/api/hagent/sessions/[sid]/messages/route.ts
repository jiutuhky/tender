import { HAGENT_BASE, authHeaders } from "@/lib/server/upstream";

export const dynamic = "force-dynamic";

// 发送消息：把上游的 SSE 流原样透传给浏览器。
// 直接转 upstream.body（ReadableStream），不 text()/不重新分帧，避免破坏 SSE 帧。
export async function POST(req: Request, ctx: { params: Promise<{ sid: string }> }) {
  const { sid } = await ctx.params;
  const body = await req.text();
  const upstream = await fetch(`${HAGENT_BASE}/sessions/${sid}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body,
  });
  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      "Connection": "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
