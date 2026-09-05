# 交接：2026-09-05 — 第四批三轮「试用体验→问题清单→整改→验证」循环

在第三批（e6233d3，今晨文档收口 56e0487）基础上跑完整三轮。**改动已分轮提交**：
第 1 轮 `39e0725`（fix）；第 2 轮 `cfd2876`（fix）；第 3 轮 `feef915`（fix frontend）；
另含当晨 /init 的 `a568226`（docs agents）。
基线后端 450 → 最终 **458 passed**（+8 回归）；前端 **200 passed + typecheck + build 三绿**。

## 第 1 轮：API 层全流程试用（新账号 trial_b4_r1，主链路复验 + 新路径深探）

覆盖：注册/鉴权 → 机构 30 → 岗位库信任切片（real 264 条纯净）→ 履历保存往返 →
**部分提交语义**（PUT basics-only 清空 collections，确认全量替换语义，前端始终发全量，行为记录）→
**check-overlap 正例**（>50% 重叠告警 ✓、恰 50% 边界告警 ✓、跨集合不配对 ✓）→ 草稿生成 →
**同岗位重复生成**（201 可重复，残留 #2 行为确认）→ 审阅生命周期（全 adopt→reviewed→导出 200、
手动条目混入→application 409 未关联/diagnostic 200/override 放行、全 remove→reviewed→导出 422）→
导出 mode 白名单 422 → 报告 filters → crawl-runs 读端点 → institutions/health（需登录态）→ 跨账号隔离。

**裁决：第三批「新草稿未审阅导出四变体全 200」记录不成立。** 实测新草稿（条目无 decision）
导出 409「还有 14 项待确认」——审阅守卫工作正常，当时应是探针已带 decision 或记录笔误。
三处探针自身乌龙记录在案：Experience 无 title 字段、collect_unlinked_items 跳过 target/identity/gaps 节
（手动条目放进求职目标节不触发 409 是正确行为）、profile 页数据在 input value 里 innerText 断言会误报。

**整改 2 项（`39e0725`，`ReportCreate.filters` 白名单校验，+2 测试）**：

1. **[P2] 报告端点 filters 自由 dict 直通 SQL 构造**：`fresh_days:"abc"` → `int()` ValueError →
   **500**（实测确认）。修复：键白名单 + trust 枚举 + fresh_days/institution_id 整数校验，统一 422。
2. **[P3] 未知 trust 静默全量**：`trust:"bogus"` → 201 且样本 348 条全量计数，违背诚实口径
   （summary 端点同参数是 pattern 校验 422，口径不一）。修复后 422。

## 第 2 轮：边界与异常路径（避开前三批覆盖面）

**[P2] fresh_days 溢出 500（第 1 轮修复的漏网之鱼，`cfd2876`）**：jobs 端点只有 `ge=1` 无上限，
`fresh_days=9999999999` → `timedelta(days=...)` OverflowError → **500**（jobs 与报告两处实测确认）。
修复：jobs `Query(ge=1, le=3650)` + 报告 validator 同上限（10 年），+1 测试（含 3650 边界 200）。

**[P2] 导入教育/经历行标签词冒充值（+5 测试）**：带节标题的合法 docx 导入，行
「学校 武汉大学 专业 临床医学 学历 本科」解析出 **school=「学校」**（标签本身在
`_SCHOOL_SUFFIXES` 里被后缀启发式选中）、**major=「武汉大学」**；经历行「单位…岗位…」
纯因标签不在后缀表而侥幸正确。修复（legacy.py）：标签-值配对优先（空白或冒号分隔，
「学校：北京大学」先拆对再取值），后缀启发式兜底时过滤标签词；教育 6 标签 + 经历 6 标签。
端到端复验两变体（空白/冒号）school/major/organization/role 全部正确。

其他边界全绿：合法 docx 导入（第三批只测过损坏 docx，本批补正面用例，姓名/电话/邮箱提取正确）、
note 1000/1001 边界、username 空/200 字 422（带空格/中文 201 放行，行为记录）、
draft job_id=-1/0 → 404、profile 10 万字 summary 不 500、订阅同关键词重复 201、
他人订阅 mark-read/删除 404、summary 300 字 region、**零命中报告诚实输出「岗位样本：0 条」**。

**[观察项，非缺陷] PNG OCR 识别质量**：tesseract chi_sim 把 72px 印刷体「姓名 楚天阔」读成
「姓名 BAA」，提取管线诚实落入 unassigned（「未命中可导入事实」）——链路行为正确（非纯汉字
拒绝进姓名，正是第三批修复的设计行为），是 OCR 能力边界。图片履历导入后用户需手动认领。

## 第 3 轮：浏览器视觉复核 + 端到端重抓验证

- Playwright 走查（登录→总览→岗位库→详情抽屉→我的履历→简历生成→抓取任务→分析→登出），
  **0 console error**；岗位库列对齐保持、抽屉溯源字段完整（解析器/置信度/抓取时间）、
  履历页职场人模式渲染正常、简历生成页草稿在列、分析页信任切片口径标注诚实
  （真实 264/禁用 45/占位 29/演示 10）。
- **[P3 存量缺陷] 分析页工具栏按钮逐字竖排**（`feef915`）：全局 `select{width:100%}` 规则命中
  工具栏裸 select，flex 行内兄弟按钮（市场洞察/数据质量/刷新/报告）被挤到 min-content 逐字
  换行。**第三批截图同症状**（走查未扫到，非本批回归）。修复：`.button-row select` 恢复内容
  宽度 + `.mode-tab` nowrap，复拍验证横排单行。
- **端到端**：手动重抓哈尔滨医科大学（区别于第三批的 njmu，run 25/26 completed，8 页成功）→
  12 条岗位溯源字段完整（parser: hrbmu-notice-v1/hrbmu-table-v1/generic-list-v1）、raw_snapshot
  完整 → 爬后订阅自动扫描推送通知（1 条含 2 匹配岗位带摘要）。
- **纠正第三批 handoff 表述**：爬后自动扫描推进的是 `last_pushed_at` + 通知；
  `last_checked_at` 是已读检查点概念，`scan_subscriptions` 明确不推进它（docstring 载明）。
  第三批「last_checked_at 推进」的说法是探针测错了字段。

## 验证记录（最终态）

- 后端：`uv run --project backend pytest -q` → **458 passed**（cfd2876 时点，其后仅前端 CSS 改动）
- 前端：`pnpm test`（**200**）/ `pnpm typecheck` / `pnpm build` 三绿
- 8000/5173 在跑（start-local -NoBrowser；本批两次重启使后端修复生效，当前运行码 = 全部修复后）
- 本批未触碰 09:00 scheduler 配置（红线只读）

## 已知残留 / 下批候选（承接第三批 + 本批新增）

1. z2 图片条件表 OCR——新增能力，需切片含 fixtures+测试；
2. 同岗位可重复生成草稿——需产品决策（本批第 1 轮已确认行为：201 无守卫）；
3. 测试账号累积在 8000 库（本批新增 trial_b4_r1/r2b 及草稿/报告/订阅若干）——需清理工具；
4. #346 思政+待遇混合条款 1 条噪声——保守方向正确，观察项；
5. profile_import 文档级管线与 legacy 行式管线并存——接线统一属大重构（本批导入修复仍在 legacy）；
6. **[新] PNG OCR 中文识别质量**（tesseract chi_sim 印刷体小字弱）——能力边界观察项，链路已诚实降级；
7. **[新] register 用户名含空格/中文放行**——如需规范化（trim/白名单）属产品决策，暂记录。

## 给下批的探针提示

- 复用 `logs/trial_b4_round1.py`（全流程+审阅生命周期）/ `round1b.py`（目标岗迭代+报告 filters）/
  `round2.py`（边界+导入）/ `round3_ui.py`（UI 走查）/ `round3_e2e.py`（重抓）骨架；
- **侧边栏导航标签实际是**：情报总览/岗位库/分析/我的（我的履历/简历生成/抓取任务），
  按「履历/简历/订阅」找会 nav not found；
- profile 页数据在 `<input value>` 里，`document.body.innerText` 断言会误报缺失；
- fresh_days 校验上限 3650，别再拿超大值试 500；报告 filters 现有白名单，非法键 422；
- collect_unlinked_items 跳过 identity/target/gaps/appendix 节——手动条目要放进内容节才触发 409；
- 导入 multipart 分隔符 `--` + boundary；URL 中文务必 quote；多行 heredoc 落盘再跑（沿袭前批）。
