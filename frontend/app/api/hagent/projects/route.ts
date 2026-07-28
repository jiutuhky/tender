import { HAGENT_BASE, authHeaders } from "@/lib/server/upstream";

export const dynamic = "force-dynamic";

// 创建项目：透传到上游 POST /projects。
export async function POST(req: Request) {
  const body = await req.text();
  const upstream = await fetch(`${HAGENT_BASE}/projects`, {
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

// 项目列表：透传到上游 GET /projects。
export async function GET() {
  const upstream = await fetch(`${HAGENT_BASE}/projects`, {
    headers: authHeaders(),
    cache: "no-store",
  });
  const text = await upstream.text();
  return new Response(text, {
    status: upstream.status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}
