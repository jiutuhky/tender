import { HAGENT_BASE, authHeaders } from "@/lib/server/upstream";
import { byteRange } from "@/lib/canvas/range";

export const dynamic = "force-dynamic";

// project workspace 文件内容读（溯源预览取招标文件 Markdown 原文用）：
// 透传 GET /projects/{pid}/workspace/files/{path}，状态码与 Content-Type 均随上游。
export async function GET(
  req: Request,
  ctx: { params: Promise<{ pid: string; path: string[] }> },
) {
  const { pid, path } = await ctx.params;
  const filePath = path.map(encodeURIComponent).join("/");
  const headers = new Headers(authHeaders());
  for (const key of ["range", "if-range"]) {
    const value = req.headers.get(key);
    if (value) headers.set(key, value);
  }
  const upstream = await fetch(
    `${HAGENT_BASE}/projects/${encodeURIComponent(pid)}/workspace/files/${filePath}`,
    { headers, cache: "no-store" },
  );
  const responseHeaders = new Headers();
  for (const key of [
    "Content-Type",
    "Content-Length",
    "Content-Range",
    "Accept-Ranges",
    "Content-Disposition",
    "ETag",
    "Last-Modified",
  ]) {
    const value = upstream.headers.get(key);
    if (value) responseHeaders.set(key, value);
  }
  if (!responseHeaders.has("Content-Type"))
    responseHeaders.set("Content-Type", "application/octet-stream");
  const requested = req.headers.get("range");
  if (upstream.status === 200 && requested && !req.headers.has("if-range")) {
    const content = await upstream.arrayBuffer(),
      range = byteRange(requested, content.byteLength);
    responseHeaders.set("Accept-Ranges", "bytes");
    if (!range) {
      responseHeaders.delete("Content-Length");
      responseHeaders.set("Content-Range", `bytes */${content.byteLength}`);
      return new Response(null, { status: 416, headers: responseHeaders });
    }
    responseHeaders.set("Content-Length", String(range.end - range.start + 1));
    responseHeaders.set(
      "Content-Range",
      `bytes ${range.start}-${range.end}/${content.byteLength}`,
    );
    return new Response(content.slice(range.start, range.end + 1), {
      status: 206,
      headers: responseHeaders,
    });
  }
  return new Response(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}
