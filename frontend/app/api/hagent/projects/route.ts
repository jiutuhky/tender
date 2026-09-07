import { HAGENT_BASE, authHeaders } from "@/lib/server/upstream";

export const dynamic = "force-dynamic";

// 创建项目：透传到上游 POST /projects。
export async function POST(req: Request) {
  try {
    const body = await req.text();
    const upstream = await fetch(`${HAGENT_BASE}/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: body || "{}",
      signal: AbortSignal.timeout(15000),
    });
    const text = await upstream.text();
    return new Response(text, {
      status: upstream.status,
      headers: { "Content-Type": "application/json; charset=utf-8" },
    });
  } catch {
    return Response.json({ detail: "暂时无法创建项目，请稍后重试。" }, { status: 503 });
  }
}

// 项目列表：透传到上游 GET /projects。
export async function GET() {
  try {
    const upstream = await fetch(`${HAGENT_BASE}/projects`, {
      headers: authHeaders(),
      cache: "no-store",
      signal: AbortSignal.timeout(15000),
    });
    const text = await upstream.text();
    return new Response(text, {
      status: upstream.status,
      headers: { "Content-Type": "application/json; charset=utf-8" },
    });
  } catch {
    return Response.json({ detail: "暂时无法加载项目，请稍后重试。" }, { status: 503 });
  }
}
