// Node 24 原生剥离 TypeScript；仅为测试补齐工程内的扩展名和路径别名。
import { registerHooks } from "node:module";
import { existsSync } from "node:fs";

registerHooks({
  resolve(specifier,context,next) {
    const url=specifier.startsWith("@/")
      ? new URL(`../${specifier.slice(2)}`,import.meta.url)
      : specifier.startsWith(".") && context.parentURL ? new URL(specifier,context.parentURL) : null;
    if(url && !/\.[a-z]+$/i.test(url.pathname)) {
      const source=new URL(`${url.href}.ts`);
      if(existsSync(source))return next(source.href,context);
    }
    return next(specifier,context);
  },
});
