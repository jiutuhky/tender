# 原文阅读字体

Newsreader 与 Noto Serif SC，字重 400–600，来自本项目原有 Google Fonts / next/font 生成的 WOFF2 文件。保留 Unicode 分片，仅在原文阅读实际使用相应字符时加载。

为消除生产构建对 Google Fonts 网络访问的依赖，将相同字体转为项目内自托管；没有修改字体内容。样式入口为 `app/workspace/_components/canvas/trace-fonts.css`。

上游及授权：

- [Newsreader](https://github.com/google/fonts/tree/main/ofl/newsreader)，授权见 `Newsreader-OFL.txt`。
- [Noto Serif SC](https://github.com/google/fonts/tree/main/ofl/notoserifsc)，授权见 `NotoSerifSC-OFL.txt`。

两套字体共约 6.1 MB，浏览器按 Unicode 范围按需请求，非首页预加载资源。
