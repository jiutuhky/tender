import { HAGENT_BASE, authHeaders } from "@/lib/server/upstream";

export const dynamic = "force-dynamic";

// 人工确认条目（审计 actor=user）：透传 POST /projects/{pid}/matrices/{type}/items/{item_id}/confirm。
export async function POST(
  req: Request,
  ctx: { params: Promise<{ pid: string; type: string; itemId: string }> },
) {
  const { pid, type, itemId } = await ctx.params;
  const body = await req.text();
  const upstream = await fetch(
    `${HAGENT_BASE}/projects/${pid}/matrices/${encodeURIComponent(type)}/items/${encodeURIComponent(itemId)}/confirm`,
    {
      method: "POST",
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
