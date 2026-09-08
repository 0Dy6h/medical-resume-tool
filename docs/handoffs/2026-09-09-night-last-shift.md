# 2026-09-09 夜班末班收尾(2026-09-08 夜,第九批)

末班(07:30)巡逻无事可修,本文档为当晚整体交接。首班详版见
`2026-09-09-night-first-shift.md`(三轮循环 0 新缺陷、409 守卫三度实证、
check-overlap 入参乌龙澄清、五页面 DOM 视觉复核、IAB 截图伪影坑)。

## 当晚终态

- 测试基线:首班零代码改动(唯一提交为 AGENTS.md scripts/ 补行 + 首班 handoff 文档),
  01:30/03:30/05:30 三巡逻与本班均零漂移,按既定口径末班免重跑全量测试
  (上一绿态:后端 473 passed / 前端 204 passed + typecheck + build @ `b28c8f5`)。
- git:main 与 origin/main 同步 @ `b28c8f5`(本收尾文档提交前),工作区干净零未跟踪。
- 服务:**今晨 07:03:57 机器重启(第五连:9-5 00:38 / 9-6 22:23 / 9-7 21:36 /
  9-8 07:19 / 9-9 07:03),重启即挂开发服务;末班 07:32 拉起,07:34 四端点
  (/health、/api/jobs、/api/analytics/summary、5173)全 200**,backend.log 0 错误、
  backend.err.log 仅启动 INFO。首班 23:33 拉起的上一套服务存活约 7 小时 31 分,
  死因即本次重启。运行代码 = 干净的 `b28c8f5` 工作区。
  - 坑:拉起必须用 `pwsh -File scripts/start-local.ps1`;Windows PowerShell 5.1
    (`powershell`)对 UTF-8 无 BOM 中文 ps1 报「字符串缺少终止符」ParserError。
    AGENTS.md 所写命令本来就是 `pwsh`,执行时误用 `powershell` 才踩坑。
- 库只读抽查:jobs 348 持平; crawl_runs 末条 id=32 trigger=auto
  `2026-09-08T01:00Z` = 本地 09:00 completed(时区修复形态保持);今晨 09:00 auto
  将正常触发——末班收工在 08:50 前,启动 catch-up 不抢跑(上次 auto 距今不足 24h)。
- 红线确认:09:00 抓取 scheduler 配置只读未动;已抓取岗位数据只增未删(库内 348 条);
  简历个人真实信息脱敏规则无改动。
- 运行形态:五班全部按时触发——首班 23:31、巡逻 01:30/03:30/05:30、末班 07:30,
  连续第三晚无失联、无重复空转。

## 当晚改动(1 个既有提交 + 本收尾文档,零代码改动)

| 提交 | 班次 | 内容 | 文件 |
| --- | --- | --- | --- |
| `b28c8f5` | 23:30 首班 | docs(handoff): 首班三轮循环交接 + AGENTS.md scripts/ 补行(零代码零新缺陷、连续第三晚) | AGENTS.md、2026-09-09-night-first-shift.md |
| 本班提交 | 07:30 末班 | docs(handoff): 本收尾文档 | 本文 |

巡逻三班与本班独立复核均**无事可修**:遗留剩余项均属大重构/数据迁移/观察项/
留白天事项,无 P0/P1 快修,不为凑量改代码。继第七、八、九批,连续第三晚全程零代码改动。

## 遗留(承接首班 handoff,当晚无新增)

1. profile_import 双管线统一——大重构,不宜夜班;
2. profile_field_id 位置锚定——需先做条目稳定 id(数据迁移);
3. 测试账号 trial_b7_r1/r2 + trial_b8_r1 + trial_b9_r1 在册——白天
   `cd backend && uv run --project . python -m scripts.cleanup_test_accounts --apply`
   (自动先备份库文件;夜班不动库);
4. 观察项:PNG OCR 中文识别质量 / #346 混合条款噪声;增强候选:岗位下拉搜索框。

## 给用户/白班

- **机器重启已成五连**,最近三次分别落在 21:36 / 07:19 / 07:03——无自启,重启即挂
  全套服务。建议白天查 Windows 计划任务/更新设置(07:00-07:30 窗口连续两天有命中);
  临时自救:双击 `start.bat` 或全局 `tcmjob`(任意目录)。
- 测试账号清理见遗留第 3 条,一条命令带自动备份(本轮新增 trial_b9_r1)。
- 探针复用:`logs/trial_b9_round1.py`、`logs/trial_b9_round2.py`(首班三轮产物,
  已 gitignore 保留)。
