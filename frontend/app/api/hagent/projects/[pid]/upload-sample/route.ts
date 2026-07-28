import { promises as fs } from "node:fs";
import path from "node:path";
import { HAGENT_BASE, authHeaders, dataDir } from "@/lib/server/upstream";

export const dynamic = "force-dynamic";

// 把 data/ 下的样本（服务端读盘）以 multipart 上传到项目 workspace 的 sources/。
// 统一改名为 "招标文件.md"，便于解析触发词引用。
export async function POST(req: Request, ctx: { params: Promise<{ pid: string }> }) {
  const { pid } = await ctx.params;
  const { filename } = (await req.json()) as { filename?: string };

  if (!filename) {
    return Response.json({ error: "filename required" }, { status: 400 });
  }
  // 白名单校验：必须是 data/ 下真实存在的 .md，且不含路径分隔。
  const dir = dataDir();
  const allowed = (await fs.readdir(dir)).filter((n) => n.toLowerCase().endsWith(".md"));
  if (filename.includes("/") || filename.includes("..") || !allowed.includes(filename)) {
    return Response.json({ error: "invalid filename" }, { status: 400 });
  }

  const buf = await fs.readFile(path.join(dir, filename));
  const fd = new FormData();
  fd.append("file", new File([new Uint8Array(buf)], "招标文件.md", { type: "text/markdown" }));
  fd.append("path", "sources/招标文件.md");

  const upstream = await fetch(`${HAGENT_BASE}/projects/${pid}/files`, {
    method: "POST",
    headers: authHeaders(),
    body: fd,
  });
  const text = await upstream.text();
  return new Response(text, {
    status: upstream.status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}
