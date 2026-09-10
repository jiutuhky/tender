import { HAGENT_BASE, authHeaders } from "@/lib/server/upstream";

export const dynamic = "force-dynamic";

export async function GET(
  _request: Request,
  context: { params: Promise<{ pid: string }> },
) {
  const { pid } = await context.params;
  const response = await fetch(
    `${HAGENT_BASE}/projects/${encodeURIComponent(pid)}/workspace/files`,
    {
      headers: authHeaders(),
      cache: "no-store",
    },
  );
  return new Response(response.body, {
    status: response.status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}
