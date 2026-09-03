# 交接：2026-09-04 — 三轮「试用体验→问题清单→整改→验证」循环

按用户要求完整跑了三轮产品试用与整改循环。**所有改动未提交**，工作区待审后 commit。
改动基于上一批（2026-09-03 P0 批次）的未提交工作区之上。

## 第 0 轮：基线

- 后端 437 passed；前端 200 passed + typecheck + build。
- **发现并修复工具链阻塞**：pnpm 的 `verify-deps-before-run` 在非交互终端误报需要清空
  重建 node_modules（`ERR_PNPM_ABORTED_REMOVE_MODULES_DIR_NO_TTY`），所有 pnpm 脚本
  无法运行。修复：`frontend/pnpm-workspace.yaml` 加 `verifyDepsBeforeRun: false`。
  此后 `pnpm test/typecheck/build` 直接可用，无需 `CI=true`（后者会杀 Vite，见 AGENTS.md）。

## 第 1 轮：全流程试用（注册→样本→岗位库→履历→生成→审阅→导出→订阅→通知→分析）

发现 4 个问题并全部整改：

1. **[P2] trust=placeholder 切片与内存分类口径不一致**：SQL 只按 parser_name 过滤，
   混入 45 条已禁用机构的占位历史（74 vs 29），用户在「占位」筛选里看到大量「已禁用」
   徽章行。修复：`repositories.py` 的 placeholder/fixture 切片补
   `institution_id IN (enabled=1)`，与 `classify_job_trust` 的 disabled 优先级对齐。
   实测 placeholder 74→29，四切片之和 = total。
2. **[P2] 列表 blocking_gap 与生成 422 判定不一致**：博士后岗（复合条款"……博士，
   具备……能力"）列表不标红、生成却被 422 拦。两层修复：
   - `matching/gates.py`：新增 `hard_degree_floor`（剥离「博士优先」「博士点」等非底线
     语境）；`evaluate_degree_gate` 对复合条款只做「低于即阻断」的算术判定（达线返回
     None，其余方面仍归模糊匹配，不抢证据）。纯学历条款行为不变。
   - `main.py` 生成端点：422 条件改为 `is_total_mismatch or any(blocking gap)`，
     对齐 CONTEXT.md「学历等硬性门槛不满足会阻断」。
   - 效果：博士后岗列表正确显示「硬性不符」红标；详情页 match_analysis 该条款
     status=blocking。`test_matching_eval`（零错源/零误报）保持全绿。
3. **[P3] 死代码**：`/api/jobs/{id}/structure` 端点前端从未调用、对真实岗位恒返回空
   （jd_structurer 是未接线的 LLM 半成品）。整体删除：端点、`jd_structurer.py`、
   `test_jd_structurer.py`、`StructuredJDOut`/`JDRequirement` schemas。
4. **[P3] 匹配度列文字截断**：「满足 X/Y 项硬性要求」在 12% 列宽（fixed table layout）
   下被硬裁。修复：列表显示「满足 X/Y 项」，完整文案放 `title` 悬停提示；
   `.match-text` 改为可换行。用户手册同步更新。

新增测试：gates 复合条款 4 项 + data_trust 切片口径 1 项 + core_flow 阻断一致性 1 项。
后端最终 435 passed（净变化：-7 structurer 测试 +6 新测试）；前端 200 passed。

## 第 2 轮：边界与异常路径扫描

覆盖：空档案 400、资格条款公告 201（0 证据 0 缺口）、导出 409/override=true/诊断版、
未审完编辑后状态回退 draft、空关键词 422、宽词告警阈值实测（招聘 44%<50% 不告警是对的）、
禁用机构 recrawl 400、并发抓取单飞 409、通知 read-all/mark-read、报告生成、
分页越界、fresh_days、坏 token 401、DOCX/PDF 导出与中文文件名。

- 守卫全部符合预期，未发现新缺陷。
- **[P3] 首启离线场景**：全新库被默认「真实数据」筛选藏住 fixture 演示数据
  （断网时岗位库看起来是空的）。修复：JobsPage 在真实视图零结果且无其他筛选时，
  探测演示数据并显示「切换到演示数据」一键入口。
  （验证方式：8001 临时实例 + 删真实岗位复现 real=0/fixture=10，API 层确认；
  临时设施已清理。）
- 观察项（不改）：宽词告警仅在创建时弹一次，列表不持久显示（对话框即产品设计）。

## 第 3 轮：剩余页面 UI 复核 + 文档一致性

- 分析页：样本构成行「真实 262 / 禁用 45 / 占位 29 / 演示 10」与修复后口径完全一致；
  市场洞察条形图比例正常；数据质量表解析器健康度全部「稳定」。
- 抓取任务页：任务 #14 auto 补跑、#17 手动 fixture 重抓状态徽章正确；禁用机构
  结构化原因（站点超时/需登录/404 等）展示完好。
- AGENTS.md：pnpm gotcha 更新为 verifyDepsBeforeRun: false 方案。
- 本交接文档。

## 验证记录（最终态）

- 后端：`uv run --project backend pytest -q` → **435 passed**
- 前端：`pnpm test`(200) / `pnpm typecheck` / `pnpm build` 三绿
- 8000（真实库）/5173 服务在跑（start-local，-NoBrowser 由本会话启动）
- 真实抓取在重启后由 maybe_catch_up 自动补跑，269 机构抓取全成功

## 已知残留 / 下批候选

- 复合条款的受众拆分（哈医大"面向不同学位受众"条款仍在逐条分析里，见 09-03 交接）。
- 订阅宽词告警只在创建时出现一次，列表不持久显示（如需持久需前端列表 UI 配合）。
- 导入 markdown 的 `# 姓名` 标题不进 basics.name（进 unassigned_blocks，审阅 UI 可手工归类）。
- 新库首启即自动补跑真实抓取（maybe_catch_up 设计如此）；离线首启依赖上面的演示数据提示。
- 测试账号 trial_r1 / trial_r2 / fresh_user(8001 临时库已删) 留在 8000 库里，可删。
