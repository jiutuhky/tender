import { HAGENT_BASE, authHeaders } from "@/lib/server/upstream";

export const dynamic = "force-dynamic";

// project workspace 文件内容读（溯源预览取招标文件 Markdown 原文用）：
// 透传 GET /projects/{pid}/workspace/files/{path}，状态码与 Content-Type 均随上游。
export async function GET(
  _req: Request,
  ctx: { params: Promise<{ pid: string; path: string[] }> },
) {
  const { pid, path } = await ctx.params;
  const filePath = path.map(encodeURIComponent).join("/");
  const upstream = await fetch(
    `${HAGENT_BASE}/projects/${encodeURIComponent(pid)}/workspace/files/${filePath}`,
    { headers: authHeaders(), cache: "no-store" },
  );
  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "Content-Type": upstream.headers.get("Content-Type") ?? "application/octet-stream",
    },
  });
}
