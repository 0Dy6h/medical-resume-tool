# 2026-09-13 夜首班交接(第十三批,2026-09-12 夜 23:30 班)

## 批次定位

- 开工 @ e56064e(= origin/main,工作区干净,无日间遗留)。
- 白天(9-12)三笔入库:73c8ad0(tcmjob 看门狗心跳文件机制)、5077f1d(AGENTS.md
  本机事实)、**e56064e(履历页一键清空,前端基线 205→217)**。
- 机器 2026-09-12 18:10:31 重启(第十一连),23:33 四端点全 000,`pwsh
  start-local.ps1 -NoBrowser` 拉起;5173 慢热自愈第 5 次复现(~2.5 分钟)。
- 今日 09:00 auto 正常跑完:crawl_runs **id=39**(本地 09:00 整 = T01:00Z)
  completed success 267 failure 0;另有白天 08:43 手动 run=38(success 10,
  白天会话测启停脚本)。jobs=349 只增未删;users=18(11 真实 + 7 探针,新增
  id=66 `123`、id=67 `trial_clearprobe_0912` 均白天测清空功能所留)。

## /loop 三轮(探针 logs/trial_b13_r1.py / trial_b13_p1.py / trial_b13_p1b.py)

- **第 1 轮(trial_b13_r1,14/14 PASS)**:一键清空(e56064e 白天新功能,
  历批未探面)API 侧端到端首次实证——建档→PUT clearedProfile 形状(九集合
  全空+basics 空+mode 保留)→GET **无复活**、**mode=fresh_grad 保留**、
  清空后重填闭环。e56064e 的「清空必须持久化」语义在后端侧成立。
- **第 2 轮(trial_b13_p1,5/7 + p1b 修正 3/3)**:非法 mode=student → 422;
  未知键静默忽略 200 no-op(契约固化);**并发 PUT 填充∥清空 ×4 轮终态无
  混合**(后端全量替换原子性——清空竞态修复所依赖的后端契约成立);空档案
  建草稿 **400 守卫**「请先填写或导入履历内容」(main.py resume_drafts 显式
  分支);field-references 带 field_id → 200 计数 0。
- **第 3 轮**:基线后端 **478 passed** / 前端 **217**(20 文件)+ typecheck +
  build 全绿;5173 降级视觉验证(HTML 挂载点+Vite 客户端直引当前工作区)。
- **零 P0/P1 缺陷,零修复,不产生代码提交**(handoff 文档提交见 /commit)。
- 探针乌龙自纠×2:①简历草稿端点是 `POST /api/resume-drafts`,误打
  `/api/reports`(市场分析报告)白建一个垃圾 report **id=35**(trial_b13_p1
  名下,随账号白天 cleanup 连带清);②field-references 漏必填参数 `field_id`
  得 422 假阳性。

## 遗留承接(给下一班/白天)

1. `profile_import` 双管线统一(禁区,待拍板)/ `profile_field_id` 迁移(禁区)。
2. 白天清理测试账号:trial_b13_r1、trial_b13_p1(含误建 report id=35)、
   白天新增 `123`、`trial_clearprobe_0912`,及历批残留(口径同历批)。
3. P2 挂账观察项:crawl-runs GET 匿名可读、institutions GET 匿名暴露
   blocked_reason(勿重复报)。
4. 基线注意:前端基线自 e56064e 起 **205→217**,后续批次以 217 为准。
