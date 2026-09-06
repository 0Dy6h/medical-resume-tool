# 第六批三轮「试用体验→问题清单→整改→验证」循环（2026-09-06）

承接 379fb36（遗留三项落地：z2 图片 OCR / 测试账号清理工具 / 重复生成确认），
基线：后端 467、前端 200、四端点 200、运行代码含 379fb36（服务 12:34 已重启）。
本批 3 个功能提交，最终 **后端 473 passed + 前端 204 passed + typecheck/build 绿**。

## 提交一览

| 提交 | 轮次 | 内容 | 文件 |
| --- | --- | --- | --- |
| `4a16ca3` | 开跑前 | /init 增量更新 AGENTS.md（image_table_ocr / cleanup_test_accounts / check_syntax 文件映射） | AGENTS.md |
| `03fcd21` | 第 1 轮 | fix(product): register 用户名含空白字符曾放行（遗留#7 拍板：禁任何空白、留中文）；后端 `^\S+$` + 前端 usernameValidationError | schemas.py、test_auth.py、LoginPage.tsx、loginPage.test.ts |
| `fd69650` | 第 2 轮 | fix(product): 显式空 institution_ids 曾被静默替换成全部 12 家启用机构（crawl-runs/subscriptions 双端点 422）；报告空白标题曾 201（title strip+非空）；附带修 test_subscriptions 爬后扫描竞态假红 | main.py、schemas.py、repositories.py、test_core_flow.py、test_subscriptions.py |
| `7f0a5c8` | 第 3 轮 | fix(scheduler): 每日维护循环按 UTC 算「9 点」实际本地 17:00 触发（两天 auto 运行 17:00:18/21 实证）；改按本地墙钟计算 | scheduler.py、test_subscriptions.py |
| 本班提交 | 收尾 | docs(handoff): 本文 | 本文 |

## 第 1 轮：API 全流程走查（新账号 trial_b6_r1，探前五批未探路径，0 新缺陷）

- auth/me 三态（token/垃圾 token/无 token 401）、institutions/health（需登录，threshold=2
  当前 0 家 unhealthy）、crawl-runs 列表/详情/limit 0|101→422/幽灵 404、analytics trust
  pattern 422 ✓
- **草稿版本保留**（379fb36 语义 API 侧验证）：同岗位二次生成两份并存、列表新→旧、
  旧稿 sections 逐字节不变 ✓
- **decision=remove 导出真实性**：移除条目文本实测不出现在投递版 docx ✓（edit 真实性
  是 b5 验的，remove 是本次补的）
- PDF 双模式（application/diagnostic 均 %PDF 头）、订阅 DELETE 生命周期（204→列表消失→
  再删 404→mark-read 404→scan 正常）✓
- ICU 词边界集成验证：jobs keyword=ICU 切片无 RICU-only 标题 ✓
- 观察项记录：export `override=true` 同时旁路审阅守卫与证据守卫——第 3 轮 UI 复核确认
  前端有 confirmExportOverride 显式确认弹窗，属设计内逃生门，闭环。

**整改 = 遗留 #7 拍板**：用户名禁空白（内部空格造成登录身份歧义、历史上出过垃圾账号），
中文合法保留；登录载荷保持宽松以兼容历史账号。实测重启后 space→422、中文→201、重复→400。

## 第 2 轮：边界与异常路径（2 产品缺陷 + 1 测试竞态，均已修）

- **[P2] 显式空 institution_ids 静默变全部机构**：`get_institutions_by_ids` 的 truthy
  判断把 `[]` 当成「未指定→全部启用」，POST /api/crawl-runs 与 /api/subscriptions 双端点
  中招（探针实测 201 且对 12 家真实站开跑，run #30 即探针误触产物，269 成功 0 失败）。
  UI 表单有 ≥1 校验触发不了，API 直调可触发。修复：仓库层区分 None（默认全部）与
  `[]`（空），两端点对显式空列表 422。
- **[P3] 报告空白标题 201 入库**：`title: str` 无 min_length，`"  "` 通过且 markdown
  渲染出 `#  `。修复：ReportCreate title 校验 strip 后非空，存库去首尾空白。
- **[测试竞态] test_subscriptions::test_crawl_triggers_subscription_scan**：与 30dbfb8
  在 test_notifications 修过的同款——爬取钩子先写 completed 后跑 scan，轮询到 completed
  立即断言 last_pushed_at 概率落空（5 文件并行负载下实测假红 1 次）。加 5s 轮询宽限。
- 复核既有守卫在当前运行实例全部生效：decision=maybe 422、伪造 profile_field_id 409、
  fresh_days=3651 422、报告 filters 未知键/坏 trust 422。
- 口径澄清（勿报缺陷）：`.txt` 是官方支持的导入格式（test_profile_import 有 200 用例）；
  报告负数 institution_id → 诚实 0 样本（与 jobs 幽灵机构口径一致）；岗位详情
  `user_status` 是对象（`.status` 取值）；check-overlap mode 合法值是
  fresh_grad/experienced。

## 第 3 轮：e2e + 浏览器视觉复核（1 新缺陷已修，UI 0 缺陷）

- **e2e 全旅程**（trial_b6_e2e）：注册→登录→岗位→履历→生成→审阅(edit+adopt)→投递版
  导出（编辑文本入文）→订阅→扫描→通知→报告→分析→跨会话持久，0 issues。
- **[P3·新缺陷] 调度器时区**：`_next_wait_seconds` 在 UTC 时钟上 replace(hour=9)，
  每日维护循环实际本地 17:00 触发（09-05 17:00:21、09-06 17:00:18 两天 auto 运行实证；
  此前夜班记录「09:00 自动抓取」的口径一直是错的）。修复为本地墙钟计算，回归测试
  断言触发点恰为本地 09:00。**今晚起自动抓取应在本地 09:00 出现，巡逻探活以此为准。**
- UI 走查 7 页（登录/注册、总览、岗位库、分析、我的履历、简历生成、抓取任务）0 缺陷：
  - 注册空白用户名 → toast「用户名不能包含空格」（截图实证）；
  - **重复生成确认**（379fb36）：埋点实证 window.confirm 被调用且文案正确、取消路径
    不再生成第三份草稿；此前两次「漏捕」是 IAB 对 window.confirm 自动应答所致
    （草稿 29/30 成对即自动接受的结果），非产品缺陷；
  - 匹配门 422 的 UI toast 诚实且带「去岗位库按学历筛选」引导；
  - 第四批修的分析页工具栏 select 挤压无复发；导航 active 类 DOM 核实正确。
- 观察项（新）：简历生成页岗位下拉 `api.jobs()` 无参数 = 最新 100 条，fixture 岗位
  （含 #10 演示岗）在数据量增长后从下拉不可达；属既有 discoverability 局限非本批引入，
  未动。

## 验证记录（最终态）

- 后端：`uv run --project backend pytest -q` → **473 passed**（467+6：auth 2、
  crawl/sub/report 3、scheduler 1）
- 前端：**204 passed**（200+4）+ typecheck + build 三绿
- 服务：8000/5173 在跑，运行代码 = `7f0a5c8`（含全部三个修复），四端点 200
- 09:00（本地）scheduler 配置语义已修正但触发时刻配置值未改（仍是 9）；
  已抓取岗位数据只增未删；无脱敏改动。误触的 run #30（manual）269 成功 0 失败，已核实。
- 探针与垃圾数据清理：真库删除本批探针产生的 4 条垃圾报告（空白标题/负数机构）；
  trial_b6*/中文用户* 测试账号留给 `scripts/cleanup_test_accounts.py` 统一清理。

## 已知残留 / 下批候选

1. profile_import 双管线并存——接线统一属大重构（原样承接）；
2. #346 思政+待遇混合条款 1 条噪声——保守方向观察项（原样承接）；
3. PNG OCR 中文识别质量——能力边界观察项（原样承接）；
4. profile_field_id 位置锚定固有边界——内容级锚定需条目稳定 id（数据迁移，原样承接）；
5. **[新] 简历生成页岗位下拉上限 100 条（最新），fixture 演示岗不可达**——可加搜索/
   信任切片参数或提高上限，属产品决策；
6. **[新·观察] 首班记录曾长期把自动抓取时刻记为 09:00**（实为 UTC 语义 bug，本批已修），
   下一班起请以实际本地 09:00 观察一晚验证修复效果。

## 给下批的探针提示

- 复用 `logs/trial_b6_round1.py`（auth/me/健康视图/抓取任务列表/版本保留/remove 真实性/
  PDF/订阅删除/ICU 词边界）、`round2.py`（跨用户状态隔离/空机构列表/报告边界/重叠口径/
  multipart 导入含 PNG OCR/CJK 子串）、`round3_e2e.py`（全旅程）骨架；
- **新守卫别再报缺陷**：register 用户名空白 422（中文 201 合法）、crawl-runs/subscriptions
  显式空机构 422、报告空白标题 422（创建时 strip）；
- 岗位详情 `user_status` 是对象不是字符串；check-overlap mode 只收 fresh_grad/experienced；
  `.txt` 导入 200 是设计；中文 keyword 记得 `urllib.parse.quote`；
- **IAB UI 验证**：按钮 Playwright click 会卡死，用 `locator.evaluate(el => el.click())`
  （本机已知坑）；`window.confirm` 会被 IAB 自动应答且 getJsDialog 抓不到——验证确认框
  请先 evaluate 覆写 `window.confirm` 埋点；
- 其余沿用第五批提示（生成探针用 fixture 岗但需匹配其硕士/医师门槛、 Education.id 是
  string、multipart 分隔符、fresh_days≤3650）。
