import { promises as fs } from "node:fs";
import path from "node:path";
import { dataDir } from "@/lib/server/upstream";

export const dynamic = "force-dynamic";

// 列出 data/ 下的招标 Markdown 样本（仅文件名 + 大小）。
export async function GET() {
  const dir = dataDir();
  let entries: string[];
  try {
    entries = await fs.readdir(dir);
  } catch {
    return Response.json([], { status: 200 });
  }
  const samples = [];
  for (const name of entries.filter((n) => n.toLowerCase().endsWith(".md"))) {
    const stat = await fs.stat(path.join(dir, name));
    samples.push({ filename: name, size: stat.size });
  }
  return Response.json(samples);
}
