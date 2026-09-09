import { HAGENT_BASE, authHeaders } from "@/lib/server/upstream";

export const dynamic = "force-dynamic";

type Context = { params: Promise<{ pid: string; docId: string; kind: string }> };

/** 原件、预览与映射均走同源；保留分段读取语义，不在代理中缓冲整个 PDF。 */
async function proxy(req: Request, ctx: Context) {
  const { pid, docId, kind } = await ctx.params;
  if (!["preview", "original", "sidecar"].includes(kind)) return new Response(null, { status: 404 });
  const headers = new Headers(authHeaders());
  for (const key of ["Range", "If-Range"]) {
    const value = req.headers.get(key);
    if (value) headers.set(key, value);
  }
  const upstream = await fetch(
    `${HAGENT_BASE}/projects/${encodeURIComponent(pid)}/documents/${encodeURIComponent(docId)}/${kind}`,
    { method: req.method, headers, cache: "no-store", signal: req.signal },
  );
  const output = new Headers();
  for (const key of ["Content-Type", "Content-Length", "Content-Range", "Accept-Ranges", "ETag", "Last-Modified", "Content-Disposition", "Cache-Control"]) {
    const value = upstream.headers.get(key);
    if (value) output.set(key, value);
  }
  return new Response(req.method === "HEAD" ? null : upstream.body, { status: upstream.status, headers: output });
}

export const GET = proxy;
export const HEAD = proxy;
