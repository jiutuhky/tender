import { HAGENT_BASE, authHeaders } from "@/lib/server/upstream";

export const dynamic = "force-dynamic";

// 四矩阵状态汇总（恢复路径）：透传 GET /projects/{pid}/matrices。
export async function GET(_req: Request, ctx: { params: Promise<{ pid: string }> }) {
  const { pid } = await ctx.params;
  const upstream = await fetch(`${HAGENT_BASE}/projects/${pid}/matrices`, {
    headers: authHeaders(),
    cache: "no-store",
  });
  const text = await upstream.text();
  return new Response(text, {
    status: upstream.status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}
