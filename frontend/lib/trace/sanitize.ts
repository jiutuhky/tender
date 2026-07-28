// 溯源预览:内联 HTML 表格的白名单净化(仅浏览器端,DOMParser)。
// 语料的 HTML 块是 MinerU 吐出的单行 <table>,但内容源自 OCR 不可尽信——
// 只放行表格结构与少量行内修饰标签,属性只留跨行跨列;其余标签剥壳保文、属性一律丢弃。

const ALLOWED_TAGS = new Set([
  "TABLE",
  "CAPTION",
  "COLGROUP",
  "COL",
  "THEAD",
  "TBODY",
  "TFOOT",
  "TR",
  "TD",
  "TH",
  "BR",
  "B",
  "STRONG",
  "I",
  "EM",
  "U",
  "SUB",
  "SUP",
  "SPAN",
  "P",
]);

const ALLOWED_ATTRS = new Set(["colspan", "rowspan"]);

/** 文本内容也不可保留的标签:剥壳会把脚本/样式源码当正文放出来,必须整体移除 */
const DROP_TAGS = new Set(["SCRIPT", "STYLE", "IFRAME", "OBJECT", "EMBED", "LINK", "META", "NOSCRIPT", "TEMPLATE"]);

function scrub(node: Element): void {
  for (const el of [...node.children]) {
    if (DROP_TAGS.has(el.tagName)) {
      el.remove();
      continue;
    }
    scrub(el);
    if (ALLOWED_TAGS.has(el.tagName)) {
      for (const attr of [...el.attributes]) {
        if (!ALLOWED_ATTRS.has(attr.name.toLowerCase())) el.removeAttribute(attr.name);
      }
    } else {
      // 剥壳保文:非白名单标签(含 script/style 等)整体降级为其文本内容
      el.replaceWith(el.ownerDocument.createTextNode(el.textContent ?? ""));
    }
  }
}

/** 净化 HTML 块;解析后无白名单内容时返回空串(调用方按纯文本兜底呈现)。 */
export function sanitizeDocHtml(html: string): string {
  const doc = new DOMParser().parseFromString(`<body>${html}</body>`, "text/html");
  scrub(doc.body);
  return doc.body.innerHTML;
}
