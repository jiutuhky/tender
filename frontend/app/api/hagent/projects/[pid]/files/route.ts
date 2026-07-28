import { HAGENT_BASE, authHeaders } from "@/lib/server/upstream";

export const dynamic = "force-dynamic";

// 上传：把浏览器的 multipart 原样转发到上游 POST /projects/{pid}/files（落 sources/ 并提交）。
export async function POST(req: Request, ctx: { params: Promise<{ pid: string }> }) {
  const { pid } = await ctx.params;
  const form = await req.formData();
  const upstream = await fetch(`${HAGENT_BASE}/projects/${pid}/files`, {
    method: "POST",
    headers: authHeaders(),
    body: form,
  });
  const text = await upstream.text();
  return new Response(text, {
    status: upstream.status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}
