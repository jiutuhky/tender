import { HAGENT_BASE, authHeaders } from "@/lib/server/upstream";

export const dynamic = "force-dynamic";

// 项目详情（含 latest_session 与嵌入的 sessions 列表）：透传 GET /projects/{pid}。
export async function GET(_req: Request, ctx: { params: Promise<{ pid: string }> }) {
  const { pid } = await ctx.params;
  const upstream = await fetch(`${HAGENT_BASE}/projects/${pid}`, {
    headers: authHeaders(),
    cache: "no-store",
  });
  const text = await upstream.text();
  return new Response(text, {
    status: upstream.status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}

// 更新项目（改名/状态/metadata 整体替换）：透传 PATCH /projects/{pid}。
export async function PATCH(req: Request, ctx: { params: Promise<{ pid: string }> }) {
  const { pid } = await ctx.params;
  const body = await req.text();
  const upstream = await fetch(`${HAGENT_BASE}/projects/${pid}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: body || "{}",
  });
  const text = await upstream.text();
  return new Response(text, {
    status: upstream.status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}

// 删除项目（软删，级联结束 active 子 session）：透传 DELETE /projects/{pid}。
export async function DELETE(_req: Request, ctx: { params: Promise<{ pid: string }> }) {
  const { pid } = await ctx.params;
  const upstream = await fetch(`${HAGENT_BASE}/projects/${pid}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  const text = await upstream.text();
  return new Response(text, {
    status: upstream.status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}
