import { HAGENT_BASE, authHeaders } from "@/lib/server/upstream";

export const dynamic = "force-dynamic";

// 创建会话：透传到上游 POST /sessions。
export async function POST(req: Request) {
  const body = await req.text();
  const upstream = await fetch(`${HAGENT_BASE}/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: body || "{}",
  });
  const text = await upstream.text();
  return new Response(text, {
    status: upstream.status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}
