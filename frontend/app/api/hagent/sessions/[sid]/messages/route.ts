import { HAGENT_BASE, authHeaders } from "@/lib/server/upstream";

export const dynamic = "force-dynamic";

// 发送消息：把上游的 SSE 流原样透传给浏览器。
// 直接转 upstream.body（ReadableStream），不 text()/不重新分帧，避免破坏 SSE 帧。
export async function POST(req: Request, ctx: { params: Promise<{ sid: string }> }) {
  const { sid } = await ctx.params;
  const body = await req.text();
  let upstream: Response;
  try {
    upstream = await fetch(`${HAGENT_BASE}/sessions/${sid}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body,
      signal: req.signal,
    });
  } catch {
    return Response.json(
      { detail: { code: "upstream_unavailable", message: "执行服务暂时无法连接，请稍后重试。" } },
      { status: 502 },
    );
  }
  if (!upstream.ok) {
    const headers = new Headers({
      "Content-Type": upstream.headers.get("Content-Type") ?? "application/json",
      "Cache-Control": "no-store",
    });
    const retryAfter = upstream.headers.get("Retry-After");
    if (retryAfter) headers.set("Retry-After", retryAfter);
    return new Response(upstream.body, { status: upstream.status, headers });
  }
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
