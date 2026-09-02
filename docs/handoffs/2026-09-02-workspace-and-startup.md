# 交接：工作区清理与本地启动验收（2026-09-02）

> 接续 `docs/handoffs/2026-07-26-end-of-day.md`。其间完成的工作见 git log：
> U1–U7、A1–A4、B1–B3、D1–D3 各单元（提交 372e11b..048ac1f），方案与评审文档
> 已全部入库（`docs/plans/`、`docs/reviews/`）。

## 本次会话做了什么

1. **对抗性工作区审查与清理**（commit `048ac1f`）：
   - 删除垃圾：`log`（nohup 残留）、`backend/tmp/`（旧提交信息草稿）、`overview.md`（U1 摘要，内容已随 372e11b 入库）；
   - gitignore 补齐：`frontend/.pnpm-store/`（127MB pnpm 缓存）、`medical-job-prd/`（3.9MB PRD 静态单页，源头文档保留在本地不入库）、`.dsh-vision-toolkit/`、`.trae-html-share-packages/`、`.workbuddy/`；
   - 入库：`docs/plans/`（11 个方案）、`docs/reviews/`（16 个评审）、`frontend/pnpm-workspace.yaml`（pnpm esbuild 构建白名单，D5 要求）。
2. **start-local.ps1 -Stop 加固**：PID 文件失效时按端口兜底停止（仅限 python/node 进程，防误杀其他程序），此前只打印提示不强停。
3. **本地启动验收通过**：一键启动 → 后端 8000（/health、/api/jobs、/api/analytics/summary 200）→ 前端 5173 渲染正常 → Vite 代理 API 200 → PID 文件对应存活进程。
4. **/init bootstrap 补齐**：新增 `CONTEXT.md`（领域词汇与核心概念权威索引）、`docs/adr/index.md`（8 条既有核心决策登记）。

## 当前状态

- 门禁：后端 pytest **427 passed**；前端 vitest **197 passed** + typecheck + build 全绿。
- 数据（backend/data/app.db）：岗位 346 条（real 262 / fixture 10 / 其余为占位历史）；12 家启用机构最后一次全量跑批 **completed，零失败**。
- 服务：本机后端 8000 / 前端 5173 由 start-local.ps1 托管运行中。
- 文档面：AGENTS.md（红线+命令）、README.md、CONTEXT.md、docs/architecture.md、docs/runbook.md（本地开发）、docs/deploy.md（服务器部署）、docs/adr/、docs/plans/、docs/reviews/、docs/handoffs/。

## 关键事实（新会话必读）

- 适配器曾因 `guard_response` 钩子访问未读流式响应（ResponseNotRead）而 100% 全盲，已修复（42c21d9）；改 `http_client.py` 时务必跑 `test_crawl_guard.py` 全部 22 条。
- 数据库里 24 家机构的 listing_url 曾被历史会话覆写为首页；`init_db` 现有自动修复迁移 `_repair_adapter_seed_urls`，别删。
- 两个数据库路径（根目录 `data/` 与 `backend/data/`）不共享数据（见 AGENTS.md），当前生效的是 `backend/data/app.db`。
- 前端门禁需 `CI=true pnpm ...`（pnpm 11 交互确认问题），或直接用 start-local.ps1 的环境。

## 建议下一步

1. **B5 分析报告**：可筛选、保存回看、导出（M2 收尾）。
2. **E2 匹配评测扩容**：学历等结构化字段抽取率低（约 81% 未注明），影响匹配精度。
3. **C1/C4 可用性工程**：首用引导、键盘可达、小屏适配（M3）。
4. 部署链路按 `docs/deploy.md` 在真实服务器过一遍验收清单（D1 落地）。
