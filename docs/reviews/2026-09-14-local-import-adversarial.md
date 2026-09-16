# 资料导入与本机 API 对抗审查

日期：2026-09-14。全部用户、档案、文件和数据库均为临时夹具；未发起实际招聘抓取或通知，未运行真实 OCR 服务。

## 已修复问题

- **P1 多页图像内容被末页替换。** `list(ImageSequence.Iterator(image))[:limit]` 收集的是 Pillow 复用的同一个对象，三页 TIFF 中前两页均被识别为末页，并且上限截断前已经遍历全部页。改为限量迭代、取一帧处理一帧。生成的三色夹具修前输出 `page 60, page 60`，修后为 `page 20, page 40`，仅访问前两帧。
- **P1 导入阻塞整个事件循环。** async 路由内直接运行同步 PDF/OCR/规则提取，使资料导入期间 `/health` 也无法及时回应。将提取和结构化构建交给线程池，实际请求并发夹具确认健康检查可以在提取完成前返回；Tesseract 每次调用增加 30 秒超时。
- **P1 上传无体积边界。** 路由原先无界 `file.read()`，multipart 解析前也无总限额。现在按实际 ASGI 字节限制请求体为 50 MB，资料文件读取最多 20 MB + 1 B，超限返回 413，并关闭上传临时文件。
- **P2 异常 token 触发 500。** 非 ASCII payload/signature 会使签名或 compare_digest 抛出 UnicodeEncodeError/TypeError。先验证 token 长度与 ASCII 结构，再严格验证 uid/exp 类型，非法凭证稳定返回 401。
- **P2 下载文件名在跨源前端不可见。** Content-Disposition 没有通过 CORS expose，界面总是落到通用文件名。现在明确暴露该响应头，保留既有 UTF-8 文件名解析。
- **测试隔离缺口。** `app.main` 在 import 时创建默认应用，原测试收集可能初始化当前目录的 DB/密钥。conftest 在 import 前强制设置临时 DATABASE_URL/DATA_DIR，并关闭后台抓取和扫描；避免验证过程改动用户库。

## 验证

新增 8 项针对性用例修前全部失败，修后全部通过。完整后端 **486 passed**，覆盖账号隔离、招聘溯源、匹配、履历导入、草稿证据门禁和 DOCX/PDF 导出。测试使用已有 Windows venv，所有 SQLite 数据库均放在 Windows 临时目录，规避 SQLite 对 WSL UNC 文件锁的限制。

本轮没有修改匹配权重、IDF 表、简历事实来源、出站抓取策略或实际用户记录。导入结果仍须用户确认后保存，识别失败继续通过既有 warnings 呈现。
