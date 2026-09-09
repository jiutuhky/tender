// PDF 引擎及附属资源与依赖同版本，开发和构建时同步到同源静态目录。
import { cp, mkdir, rm } from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";
const require = createRequire(import.meta.url);
const source = path.dirname(require.resolve("pdfjs-dist/package.json"));
const { version } = require("pdfjs-dist/package.json");
const target = new URL(`../public/pdfjs/${version}/`, import.meta.url);
await mkdir(target, { recursive: true });
for (const name of ["cmaps", "standard_fonts", "wasm"]) {
  await rm(new URL(`${name}/`, target), { recursive: true, force: true });
  await cp(path.join(source, name), new URL(`${name}/`, target), { recursive: true });
}
await cp(path.join(source, "legacy/build/pdf.worker.min.mjs"), new URL("pdf.worker.min.mjs", target));
