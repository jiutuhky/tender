"""PDF 入库管线：上传后的确定性前置任务（OCR → 规范化 md + sidecar）。

分工：`assembler` 是唯一测试缝（纯函数，版面块 →(md, sidecar)）；`ocr_client`
负责分批与页级断点续跑；`pdf` 负责页数、逐页尺寸与预览版重压缩；`blobs` 按
sha256 把二进制存到 project workspace 之外；`tasks` 登记在跑的解析；`pipeline`
把它们串成一次上传的完整入库。各模块按需直接 import，本文件不做再导出。
"""
