# 评审报告 — PRD 4.5 导出增强（traework 交付，工作区未提交）

评审日期：2026-08-22
评审人：项目总监（AI）
交付状态：变更未提交、未 push（6 文件，+319/-38），交我审核

## 一、核查方式
- 读取 `git diff` 核心代码（exporter.py / main.py / api.ts / ResumePage.tsx）
- 核对 `resume.py` 生成的 `evidence`/`gaps` 数据结构，确认附录字段读取逐一对应
- 阅读 4 个新增后端测试 + 3 个前端 `exportBlock` 测试源码
- 运行门禁：后端 `test_core_flow.py` + `test_matching_eval.py` = 35 passed；后端全量 = 196 passed + 1 预存 flake

## 二、结论：✅ Approve（功能正确、约束遵守、红线未动）

### 任务 A — exporter.py（诊断版附录）
- `export_docx`/`export_pdf` 加 `include_appendix: bool = False`，签名向后兼容（默认 False，旧调用零影响）
- `_build_appendix_sections()` 从 `draft["evidence"]` 生成「已满足」、从 `draft["gaps"]` 生成「未满足」
- 字段映射逐一核对（见下），标题用纯 CJK（"已满足"/"未满足"），确保 PDF 字体兼容
- 附录字段与 `resume.py` 实际结构一致：
  - evidence 项含 `requirement` / `source_label` / `source_text` / `evidence_strength` ✓ 全部被读取
  - gaps 项含 `requirement` / `message` / `blocking`（`blocking` 仅 `not_met` 时置 true，其余缺失为 falsy）✓ 逻辑自洽

### 任务 B — main.py（导出端点 + 护栏）
- 新增 `override: bool = False` 查询参数
- 409 门禁：`_compute_draft_status(draft) != "reviewed" and not override` → 409，detail 含 pending 项数
- 422 门禁：`_draft_for_export` 过滤后无 item → 422（不受 override 影响，先经 409 后仍触发）
- `_draft_for_export` 简化为始终剥离 gaps 段落；`include_appendix = mode == "diagnostic"` 仅诊断版传 True 追加附录
- 行为正确性：application 模式本就不含 gaps 段落（与旧保持一致）；diagnostic 模式改为「去 gaps 段落 + 追加附录」，正是 PRD 4.5 意图

### 任务 C — 前端（override 转发 + 导出护栏）
- `api.ts`：`exportResume` 加 `override=false`，经 `URLSearchParams` 转发；409/422 detail 由既有 `errorMessage()` 上抛
- `ResumePage.tsx`：抽出纯函数 `exportBlock(sections)` → `{kind:"proceed"} | {kind:"confirm", pending:N}`，可测
- `exportDraft` 先走 `exportBlock`，confirm 时弹确认层（返回审阅 / 继续导出=override=true）；proceed 时直接 `doExport(..., false)`
- 确认层双按钮逻辑与后端 409/override 语义一致

## 三、红线与约束
- `test_matching_eval` = **8 passed**（top-1 准确率 / 零错源 / 零误报等全覆盖，未动）✅
- 零数据库 schema 变更：`status` 仅响应字段，`decision` 存 sections JSON 内部，`override` 仅查询参数 ✅
- 未碰 `matching/`、`adapters/`、`crawler.py`、`profile_import/`、`jd_structurer.py` ✅
- 改动仅 6 文件：main.py + exporter.py + test_core_flow.py + api.ts + ResumePage.tsx + resumeReview.test.ts ✅

## 四、测试结果独立核验
- 后端 `test_core_flow.py` + `test_matching_eval.py`：**35 passed**
- 4 个新增后端测试全部覆盖边界：
  1. 未审阅 → 409（detail 含"尚未审阅"/"项待确认"）
  2. override=true → 200
  3. 全 remove（已 reviewed 但空内容）→ 422（不受 override 影响）
  4. diagnostic 含「匹配分析附录」、application 不含；「已满足/未满足」按 evidence/gaps 实际存在性断言
- 前端 `exportBlock` 3 测试（全审阅→proceed / 无决策→confirm N / 部分决策→confirm N）与实现等价
- 前端：本沙箱 esbuild 构建脚本被禁，vitest/typecheck/build 无法复跑；已源码评审替代（traework 报 44 passed / tsc 无错 / build 成功）

## 五、非阻塞提示
1. **门禁口径修正**：traework 报"197 passed ✅"实为 **196 passed + 1 预存 flake**（`test_jd_structurer` Windows env >32767 字符，与 4.5 无关，勿判为回归）。
2. 前端 3 项工具链（vitest/tsc/vite）建议合并前在 traework 环境再跑一次确认（其报全绿）。
3. **当前 4.5 仍是工作区未提交改动**，领先 origin/main 仍为 4.4 的 3 个 commit（42f57c6 等）。建议 traework 将 4.5 提交为一个新 commit 后交我，维持未 push 状态待你定合并节奏。

## 六、下一步
PRD 主线 4.1 情报中心 / 4.6 分析 择一切片即可；亦可评估 4.6 分析的差距可视化是否复用本附录数据。
