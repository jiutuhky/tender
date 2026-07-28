// 服务端专用：hagent 后端的 base 地址与鉴权。
// 仅被 app/api/hagent/** 的 route handler 引用（服务端），不会进客户端 bundle，
// 故可安全使用 node 内置模块；也因此不暴露给浏览器，不用 NEXT_PUBLIC_*。
import path from "node:path";

export const HAGENT_BASE = process.env.HAGENT_API_BASE || "http://localhost:8000";
const KEY = process.env.HAGENT_API_KEY || "";

export function authHeaders(): Record<string, string> {
  return KEY ? { Authorization: `Bearer ${KEY}` } : {};
}

/** data/ 语料目录（相对仓库根；frontend 的 CWD 是 tender/frontend，故 ../data）。 */
export function dataDir(): string {
  return path.resolve(process.cwd(), "..", "data");
}
