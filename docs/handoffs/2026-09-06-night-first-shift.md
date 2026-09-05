# 交接：2026-09-06 夜首班（05 夜 23:30 班）— 第五批三轮「试用体验→问题清单→整改→验证」循环

承接白班第四批（fdd4c19，458+200 三绿）。首班 23:38 正常触发——**23:30 首班定时触发器
连续两晚失联后首次恢复**（09-03、09-04 夜均由 01:30 升级补位）。基线验证即发现 1 个
测试竞态假红，连同 /loop 第 1 轮 2 个产品缺陷一并修复。**改动已提交 `30dbfb8`**（5 文件，
+105/-3），后端最终 **460 passed**（458+2 回归），前端未动（200 passed 基线复核过）。

## 基线验证（/init 阶段，23:39–23:55）

- 前端 18 文件 **200 passed** ✓；后端全量 **1 failed（457 passed）**——
  `test_notifications.py::test_crawl_run_triggers_notification` 概率性失败。
- **归因**（非产品缺陷，测试竞态）：爬取钩子 `main._crawl_then_scan` 的 finally 段里
  `release_crawl_slot()` 之后才 `scan_subscriptions`；run 状态**先**写 completed、扫描在后。
  测试 `_wait_runs` 轮询到 completed 即返回并立即断言通知，落在「completed 已写、扫描
  未跑」窗口即假红。独立复现三次：`immediate check` 0/1/1 证实。白班绿/今晚红即负载
  差异放大概率。**修复**：断言前加 5s 轮询宽限；重跑三次全绿。

## 第 1 轮：API 层全流程试用（新账号 trial_b5_r1，前四批未探路径）

覆盖：重复注册/错密码、real 切片 **264 条溯源字段批量完整性**（source_url/hash/
fetched_at/parser_name 全非空 ✓）、jobs 参数边界（limit=0/offset=-5/fresh_days=0 均 422、
幽灵机构诚实空）、**岗位状态标记生命周期**（PUT/DELETE status：非法值/1001 字 note/
坏 deadline 422、缺 job 404、重复 DELETE 幂等 204、未登录 401）、订阅校验（名过短/
13 机构 422）、**订阅→扫描→通知全链**（unread-count/单条 read/read-all/幂等/跨账号隔离）、
**decision=edit 编辑文本真实性**（docx 解压实测含编辑文本、原文不残留）、导出 format 白名单、
报告幽灵机构诚实 0 样本。

**整改 2 项（`30dbfb8`）**：

1. **[P1] 伪造 profile_field_id 曾通过投递版导出**：导出守卫 `collect_unlinked_items`
   只查引用非空——把 4 个已关联条目的引用改成 `"999999"` 后 adopt，application 导出
   **200 放行**，无证据内容进入投递版，违反真实简历红线（API 直调可触发，UI 正常路径
   触发不了，但红线口径必须收紧）。修复：守卫新增 `valid_field_ids` 参数，引用须存在于
   当前档案（口径同 `flatten_profile_facts`：条目 id 或位置 id `education-1`）；export 端点
   构造合法集合并传入。实测修复后 409，diagnostic 仍放行（附录标注）。+1 回归测试。
2. **[P3] decision 任意字符串曾静默入库**：PUT 草稿 sections 为自由 dict，`decision:"maybe"`
   200 接受且 GET 原样回显。修复：`ResumeDraftUpdate.validate_decisions` 白名单
   adopt/edit/remove（None=未决策），非法 422，风格同第四批 filters 白名单。+1 回归测试。

**探针乌龙记录在案**（防下批重蹈）：目标岗选 real 护理岗对消化内科简历 422「差距较大」
是**正确阻断**（生成链路探针用 fixture 岗 #10 影像科）；`Education.id` 是 **string** 类型
（int 载荷 422 是探针错）；GET /api/profile 条目 id=None 是**设计使然**（无持久 id，
`flatten_profile_facts` fallback 位置 id），非缺陷。

## 第 2 轮：边界与异常路径（0 新缺陷，不提交）

单飞并发抓取（浙大二院真实站）201/409 互斥 ✓、recrawl 幽灵机构 400 ✓、
订阅含不存在机构 400「部分机构不存在」（创建时校验）✓、jobs keyword 切片与报告样本
计数一致（ICU：1=1）✓、field-references 合法/未知 200 诚实、缺参 422 ✓、
profile mode="alien" 422 ✓。

## 第 3 轮：交接收口（本文档）

今晚改动全在后端（exporter/main/schemas/tests），前端零改动；岗位库列对齐等 UI 面
05:30 班走查 7 页 + 白班第四批 Playwright 走查均 0 缺陷，无新风险面，UI 未重复走查。

## 验证记录（最终态）

- 后端：`uv run --project backend pytest -q` → **460 passed**（修复后全量）
- 前端：`pnpm test` 200 passed（基线复核，今晚未动前端）
- 8000/5173 在跑（**本班重启过一次**使导出守卫生效，当前运行码 = 全部修复后）
- 09:00 scheduler 配置未动（红线只读）；已抓取岗位数据只增未删；无前端/脱敏改动

## 已知残留 / 下批候选（承接第四批 handoff 7 项，原样有效）

1. z2 图片条件表 OCR——新增能力，需切片含 fixtures+测试；
2. 同岗位可重复生成草稿——需产品决策；
3. 测试账号累积（本班新增 trial_b5_r1/r1b 及草稿/订阅/岗位状态若干）——需清理工具；
4. #346 思政+待遇混合条款 1 条噪声——保守方向，观察项；
5. profile_import 双管线并存——接线统一属大重构；
6. PNG OCR 中文识别质量——能力边界观察项；
7. register 用户名含空格/中文放行——产品决策。
8. **[新·观察项] profile_field_id 位置锚定的固有边界**：条目无持久 id，位置 id 随档案
   重排漂移（"education-1" 改指向不同内容）；本次守卫只校验引用「存在于当前档案」，
   不校验指向的内容未变——内容级锚定需先做条目稳定 id（数据迁移），不宜夜班动。

## 给下批的探针提示

- 复用 `logs/trial_b5_round1.py`（溯源批量断言/岗位状态生命周期/订阅通知全链）、
  `round1b.py`（edit 真实性/伪造引用守卫/decision 白名单）、`round2.py`（单飞并发/
  幽灵机构/切片一致性）骨架；`repro_notif_fail.py` 是竞态复现样例；
- **导出守卫已收紧**：伪造 profile_field_id 会 409，别再当缺陷报；decision 非法值 422；
- 生成链路探针用 fixture 岗（#10 影像科），real 临床岗 422 多为正确阻断；
- `Education.id`/条目 id 是 string；GET profile 条目 id=None 是设计，勿报；
- 其余沿用第四批提示（侧边栏标签、input value、fresh_days≤3650、multipart 分隔符）。
