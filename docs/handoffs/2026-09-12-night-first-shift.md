# 2026-09-12 夜班首班交接(2026-09-11 夜,第十二批)

首班 23:30-00:3x:/init → /loop 三轮 → /end → /commit。**本轮零缺陷零修复**,
全部产出为未探面首次实证 + 基线守护:后端 **478** / 前端 **205** + typecheck +
build 全绿(基线与十一批末持平)。

## 当晚终态

- 服务:机器 **2026-09-11 18:20:27 重启(第九连)**,23:30 开工时四端点全 000;
  23:33 `pwsh scripts/start-local.ps1 -NoBrowser` 拉起,后端 ~1 分钟全 200,
  5173 慢热自愈复现(约 2.5 分钟,与十一批已知形态一致)。
- **今日 09:00 auto 未跑**(18:20 重启后服务挂)→ 服务拉起时 startup catch-up
  自动补跑 crawl_runs **id=37**(本地 23:32=T15:32Z)completed,12 机构
  success 267 failure 0——catch-up 属 scheduler 设计行为,调度配置只读未动。
- git:开工时干净 @ `d0bcb99` 与 origin/main 同步,无日间遗留;运行代码=工作区。
- 库只读抽查:jobs=349 只增未删;users=11;analytics totals 与 trust_breakdown
  对账一致(real 265+disabled 45+placeholder 29+fixture 10=349)。
- 红线确认:09:00 scheduler 配置只读未动;岗位数据只增未删;脱敏规则无改动。

## /loop 三轮(23:38-00:0x,探针 logs/trial_b12_round{1,1b,2,2b}.py)

- 第 1 轮(trial_b12_r1/r1b/r1c):全流程走查 + **导出文件真实性首次实证**——
  历批只验状态码,本轮验文件头魔数(docx=PK zip / pdf=%PDF)+ Content-Type +
  Content-Disposition,四组合(diagnostic/application × docx/pdf)全真。
  Content-Disposition 为 RFC 5987 双保险(`filename` ASCII 兜底 +
  `filename*=UTF-8''`),中文文件名编码正确。同岗位重复建草稿 201 第二份
  (与 reports 同性质,记观察项)。乌龙自纠×2:jobs 前 100 条默认排序不含
  fixture 岗(10 条 fixture fetched_at 老,需显式 trust=fixture 过滤);
  trust_breakdown 行键是 name/count 非 trust/count。
- 第 2 轮(trial_b12_p1):**订阅 keyword 通配符注入端到端**——keyword=%/_ 创建
  201、scan 两轮 pushed=0 无洪水(re.escape 转义 + refine_keyword_hits 词边界
  精筛,且 count_total_matching_jobs 同口径精筛故宽词 warning 不误报,行为
  一致诚实);institutions/health 登录 200 形状 {institutions, review_count,
  threshold};decision=123 → 422(schema validator 拒非字符串);
  institution_ids=[1,1] → 400(get_institutions_by_ids 去重致计数不符);
  **图片 OCR 端到端首次实证**——PIL+simhei 现场画中文 PNG 上传
  /api/profile/import,tesseract 抽出姓名「李十二」(位置启发式正常路径,
  d0bcb99 修复无回归)。OCR 自由文本的教育/经历行未被强行结构化(诚实降级,
  记观察项)。乌龙自纠:round2.py 一处 req 返回值解包元数写错(探针笔误)。
- 第 3 轮:全量后端 **478 passed** / 前端 **205** + typecheck + build 全绿;
  IAB 视觉复核——截图管道本班报「activity capture failed for guest」
  (截图功能失败,非既往平铺伪影),降级以 DOM 快照验收:标题/五导航标签/
  总览 349-24-12 齐全,近期岗位时间戳 23:33:06 = catch-up run=37 的
  fetched_at,爬取→入库→前端展示全链路活的端到端证据。

## 遗留(承接十一批,无新增缺陷)

1. profile_import 双管线统一(大重构,禁区,不宜夜班)。
2. profile_field_id 条目稳定 id 迁移(禁区)。
3. 测试账号白天清理:十二批新增 trial_b12_r1/r1b/r1c(各 1 档案;r1c 另有
   draft 46)、trial_b12_p1(档案+draft 48,订阅已全删)。十一批残留
   trial_b11_p1/p2/p3/r1 口径不变。`cleanup_test_accounts --apply`(白天跑,
   自动备份)。
4. 观察项(不动代码,勿重复报):GET /api/crawl-runs 匿名可读(P2);
   institutions GET 匿名 200 暴露 blocked_reason(同性质);同岗位重复建草稿
   201 第二份(reports 同性质,列表有 job_id 过滤,前端可自行复用);OCR
   自由文本结构化抽取覆盖率有限(无标签行不强行归类,符合诚实边界)。

## 下批候选未探面(供巡逻班参考)

- PUT /api/resume-drafts 大 payload/深嵌套边界;reports 创建后无 GET 列表的
  垃圾积累面;subscription keyword 非中文非 ASCII 混合词(如「ICU护理」)
  分类口径;auth token 并发登录互踢/共存语义;export 并发大文件。
