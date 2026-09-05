# 交接：2026-09-05 — 第三批三轮「试用体验→问题清单→整改→验证」循环

在前两批（1e08b83、v2 批 fea2fcf/ee3634b）基础上跑完整三轮。**改动已分轮提交**：
第 1 轮无新缺陷不提交；第 2 轮 `e6233d3`（fix）；第 3 轮无新缺陷不提交，本批仅 1 个功能提交。
基线后端 445 → 最终 **450 passed**（+5 回归）；前端 **200 passed + typecheck + build 三绿**。

## 第 1 轮：API 层全流程试用（新账号 trial_b3_r1 走通主链路）

覆盖：注册/鉴权边界（重复注册 400、错密码 401、无 token 401）→ 机构 30 → 岗位库信任切片
（real 264 条全部含 source_url/fetched_at/parser_name，trust=real 无混入）→ 岗位详情/历史 →
岗位状态生命周期（422 白名单、204 清除）→ 履历保存往返 → check-overlap（不可解析日期不告警）→
草稿生成阻断门 → 审阅生命周期（adopt/edit → reviewed）→ 导出四变体（docx/pdf × application/
diagnostic 魔数全部正确）→ 订阅全生命周期（scan/通知/read-all 幂等/删除幂等 404）→ 分析与报告 →
跨账号隔离（他人草稿 404、新账号空白履历、无履历生成 400）。

**结论：无新缺陷。** 试探中三处「疑似问题」均为探针自身错误，记录以免重蹈：

1. `Experience` 模型字段是 `organization`/`role`（无 `title`），pydantic 对未知键静默忽略——
   探针用错字段名会导致履历条目静默变空行，进而 422「差距较大」，勿误判为匹配缺陷；
2. `match_analysis` 条目键是 `requirement/status/evidence/advice`（无 met/blocking 键）；
3. `check-overlap` 返回形状是 `{"overlap": bool, "items": [...]}`。

临床岗 422 全部为正确阻断（#324 中医专业不符、#129 博士硬门槛），fixture 岗 #10 正常出稿。

## 第 2 轮：边界与异常路径（发现 3 个问题，全部整改 e6233d3）

覆盖：岗位列表参数边界（trust/limit/offset/fresh_days 全部 422 正确、SQL 型与 300 字关键词
不 500、RICU 词边界不泄漏 ICU 专属岗位）→ 导入变体（exe 400、空文件 400、损坏 docx 400、
GBK txt 解码、PDF 文本导入）→ 订阅边界（institution_ids 空/13 个/不存在、关键词 50/51 字、
mark-read 404）→ 草稿导出边界（job_id 类型/不存在、sections 非法形状、空 sections、format 白名单）
→ 抓取守卫（禁用机构 400、不存在 400、并发 recrawl 单飞 201+409、run 404）→ 鉴权边界 → 通知 404。

整改 3 项（`e6233d3`，后端 445→450）：

1. **[P2] 文档标题行冒充姓名**：txt/pdf 导入首行「个人简历」被位置启发式当成姓名，
   「姓名 王大力」（无冒号）反被丢弃——basics.name 错、整块被 consume 不进 unassigned、
   还产出 major=「个人简历」的垃圾教育 review item，三个症状一个根因。
   修复（extractors.py）：姓名标签（姓名/名字/称谓）是强信号，先扫全部块再做位置兜底；
   标签正则放宽为冒号**或空白**分隔 + 纯汉字 2-4 位姓名本体（负向断言防「姓名与身份证
   不符」误截）；位置启发式排除简历标题行（个人简历/求职简历/履历等 8 词）。
2. **[P3] PDF 文本导入姓名为空**：同根因（`姓名 张三丰` 无冒号不识别），随 1 一并修复，
   实测 PDF 导入 name=张三丰。
3. **[P3] 空草稿导出自相矛盾 409**：`PUT sections=[]` 后导出命中审阅守卫，报
   「草稿尚未审阅完成，还有 0 项待确认」；空草稿永远到不了 reviewed。修复（main.py）：
   空内容 422 提前到审阅 409 之前，空草稿导出现在诚实报「导出内容为空」。

新增 5 个回归测试（test_extractors ×4：标签优先/标题行排除/无冒号标签/无分隔不误截；
test_core_flow ×1：空 sections 无 override 导出 422）。

## 第 3 轮：浏览器视觉复核 + 端到端重抓验证（无新缺陷）

- Playwright 走查 7 页（登录→总览→岗位库→详情抽屉→我的履历→简历生成→抓取任务→分析→登出），
  **0 console error**；岗位库列对齐（昨晚 inset box-shadow 修复保持）、详情抽屉溯源字段
  （解析器/置信度/抓取时间）完整、分析页信任切片口径标注诚实（真实 264/禁用 45/占位 29/演示 10）。
- **端到端**：手动重抓南京医科大学（run completed，12 条岗位）→ requirements 无样板（v2 修复
  保持）、source_url/parser_name 完整、raw_snapshot 完整；抓取完成后订阅自动扫描链路正常
  （last_checked_at 推进）。

## 验证记录（最终态）

- 后端：`uv run --project backend pytest -q` → **450 passed**
- 前端：`pnpm test`（200）/ `pnpm typecheck` / `pnpm build` 三绿
- 8000/5173 在跑（start-local -NoBrowser，白天使用）；本批未触碰 09:00 scheduler 配置（红线只读）

## 已知残留 / 下批候选（承接 v2 批 + 夜班末班，本批无新增）

1. z2 图片条件表 OCR——新增能力，需切片含 fixtures+测试；
2. 同岗位可重复生成草稿——需产品决策；
3. 测试账号累积在 8000 库（本批新增 trial_b3_r1/r1b 及草稿/报告若干）——需清理工具；
4. #346 思政+待遇混合条款 1 条噪声——保守方向正确，观察项；
5. profile_import 文档级管线与 legacy 行式管线并存——接线统一属大重构
   （注：本批修复仍在 legacy 管线，文档级管线 extractors 同文件但未接入端点）。

## 给下批的探针提示

- 复用 `logs/trial_b3_round1.py`（全流程）/ `round2.py`（边界）/ `round3_e2e.py`（重抓）骨架；
- 导入探针 multipart 分隔符是 `--` + boundary；URL 中文务必 quote；
- 多行 heredoc 在本机 Git Bash 偶发截断，脚本一律用文件方式落盘再跑；
- 裸 multipart/Python 调用坑见 [[night-shift-resume-tool-facts]] 与 [[this-machine-env-facts]]。
