/** 把招标文件名美化为可读项目名:去掉 MinerU_markdown_ 前缀与尾部 _<id> / .md 后缀。 */
export function prettyLabel(filename: string): string {
  return filename
    .replace(/^MinerU_markdown_/, "")
    .replace(/_\d+\.md$/i, "")
    .replace(/\.md$/i, "");
}
