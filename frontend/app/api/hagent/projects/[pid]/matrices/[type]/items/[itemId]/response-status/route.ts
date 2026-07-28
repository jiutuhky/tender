import { HAGENT_BASE, authHeaders } from "@/lib/server/upstream";

export const dynamic = "force-dynamic";

// 人工标注应答状态（合规/正偏离/负偏离，审计 actor=user）：
// 透传 PUT /projects/{pid}/matrices/{type}/items/{item_id}/response-status。
export async function PUT(
  req: Request,
  ctx: { params: Promise<{ pid: string; type: string; itemId: string }> },
) {
  const { pid, type, itemId } = await ctx.params;
  const body = await req.text();
  const upstream = await fetch(
    `${HAGENT_BASE}/projects/${pid}/matrices/${encodeURIComponent(type)}/items/${encodeURIComponent(itemId)}/response-status`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: body || "{}",
    },
  );
  const text = await upstream.text();
  return new Response(text, {
    status: upstream.status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}
