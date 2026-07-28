import { HAGENT_BASE, authHeaders } from "@/lib/server/upstream";

export const dynamic = "force-dynamic";

// 文档注册表分页读（document_id → workspace 路径映射，溯源预览解析来源签用）：
// 透传 GET /projects/{pid}/documents，query string 原样转发。
export async function GET(
  req: Request,
  ctx: { params: Promise<{ pid: string }> },
) {
  const { pid } = await ctx.params;
  const search = new URL(req.url).search;
  const upstream = await fetch(
    `${HAGENT_BASE}/projects/${encodeURIComponent(pid)}/documents${search}`,
    { headers: authHeaders(), cache: "no-store" },
  );
  const text = await upstream.text();
  return new Response(text, {
    status: upstream.status,
    headers: {
      "Content-Type": upstream.headers.get("Content-Type") ?? "application/json; charset=utf-8",
    },
  });
}
