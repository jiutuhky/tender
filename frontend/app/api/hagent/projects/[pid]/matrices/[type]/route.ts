import { HAGENT_BASE, authHeaders } from "@/lib/server/upstream";

export const dynamic = "force-dynamic";

// 矩阵总览（envelope + 分组统计，不含条目）：透传 GET /projects/{pid}/matrices/{type}。
export async function GET(
  _req: Request,
  ctx: { params: Promise<{ pid: string; type: string }> },
) {
  const { pid, type } = await ctx.params;
  const upstream = await fetch(
    `${HAGENT_BASE}/projects/${pid}/matrices/${encodeURIComponent(type)}`,
    { headers: authHeaders(), cache: "no-store" },
  );
  const text = await upstream.text();
  return new Response(text, {
    status: upstream.status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}
