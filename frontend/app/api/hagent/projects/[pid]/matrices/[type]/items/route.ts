import { HAGENT_BASE, authHeaders } from "@/lib/server/upstream";

export const dynamic = "force-dynamic";

// 条目分页查询（过滤参数与 MCP prose_query_matrix_items 对齐）：
// 透传 GET /projects/{pid}/matrices/{type}/items，query string 原样转发。
export async function GET(
  req: Request,
  ctx: { params: Promise<{ pid: string; type: string }> },
) {
  const { pid, type } = await ctx.params;
  const search = new URL(req.url).search;
  const upstream = await fetch(
    `${HAGENT_BASE}/projects/${pid}/matrices/${encodeURIComponent(type)}/items${search}`,
    { headers: authHeaders(), cache: "no-store" },
  );
  const text = await upstream.text();
  return new Response(text, {
    status: upstream.status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}
