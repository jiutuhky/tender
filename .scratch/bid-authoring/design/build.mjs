// 组装各画板：node build.mjs → 写出 <Name>.dc.html
import { writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const boards = {};

const mods = ["./boards/g1.mjs", "./boards/g2.mjs", "./boards/g3.mjs", "./boards/g4.mjs", "./boards/g5.mjs", "./boards/overview.mjs"];
for (const m of mods) {
  try {
    const mod = await import(m);
    for (const [name, fn] of Object.entries(mod)) if (typeof fn === "function") boards[name] = fn;
  } catch (e) {
    if (e.code === "ERR_MODULE_NOT_FOUND" && String(e.message).includes(m.replace("./", ""))) continue;
    throw e;
  }
}

for (const [name, fn] of Object.entries(boards)) {
  const html = fn();
  writeFileSync(join(here, `${name}.dc.html`), html);
  console.log(`${name}.dc.html  ${(html.length / 1024).toFixed(1)} KB`);
}
