# 2026-09-11 夜班首班交接(2026-09-10 夜,第十一批)

首班 23:30-00:0x:/init → /loop 三轮 → /end → /commit。本轮 1 处真实缺陷修复
(空白订阅名空串入库),新基线**后端 476 / 前端 205** + typecheck + build。

## 当晚终态

- 服务:机器 **21:19:58 当晚重启(第八连)**,23:30 开工时四端点全 000;
  23:32 `pwsh scripts/start-local.ps1 -NoBrowser` 拉起。**5173 出现新形态**:
  Vite 日志 ready 但 HTTP 无响应约 2 分钟(期间 TCP 可连),当时后台恰有
  Tcm_tech 项目 next build 抢 CPU,之后自愈 50ms 内 200——判定为环境噪声非项目
  缺陷;整改后 00:0x 服务重启,四端点全 200。
- git:开工时干净 @ `6b2b099` 与 origin/main 同步,无日间遗留;运行代码 = 工作区。
- 库只读抽查:jobs=349 只增未删;今晨 09:00 auto 爬取 crawl_runs **id=34**
  completed(本地 09:00,T01:00Z 时区形态保持;今日 0 新增岗位,success 267
  failure 0);recrawl 探针(run=35,机构 1 fixture)后机构 1 岗位数 3→3 不减。
- 红线确认:09:00 scheduler 配置只读未动;岗位数据只增未删(349 条,探针
  DELETE status 仅删用户跟踪标记,岗位本体 200 仍在);脱敏规则无改动。

## /loop 三轮(23:38-23:52,全部探针 logs/trial_b11_round{1,2}.py)

- 第 1 轮(新账号 trial_b11_r1/r1b):岗位状态 PUT/DELETE 生命周期(非法 status
  422/note 超长 422/404/删后岗位仍在)、订阅创建边界(**空白名称被接受入库
  name=''=缺陷①**;空白 keyword 已有校验器正确 422;机构不存在 400;空列表 422)、
  跨用户删订阅/mark-read 404、手动 scan 幂等、通知四件套形状、auth 边界。
  乌龙自纠:重复注册探针用了 1 位密码,先撞 schema 422 非产品缺陷。
- 第 2 轮:导出 override 全链(application+未链接条目 409 → override 200 docx →
  diagnostic 200 → pdf override 200 → 非法 format 422)、decision=maybe 422、
  全 remove 422 空内容、跨用户草稿 GET/PUT/导出 404、**fixture recrawl 驱动
  通知正向路径**(recrawl 刷新 fetched_at → finally 全用户扫描 → 订阅「检验」
  收到通知,单条已读 unread 算术正确)、重复注册 400、reports 未知过滤键诚实
  422。乌龙自纠×2:手动条目误加 identity 节(该节按设计豁免证据检查)→ 移到
  内容节后 409 正确触发;again 踩「%PDF 撞 %-format」坑。
- 整改①:`SubscriptionCreate` 补 `_check_name_not_blank` 校验器(镜像既有
  keyword 校验:纯空白名长度达标但 strip 后空串,曾直接入库)+ 空白名 422
  回归测试。前端表单必填故 UI 无感。
- 第 3 轮:后端 **476 passed**(475+1)/ 前端 205+typecheck+build 全绿;服务
  重启后运行时实证:空白名 422(「订阅名称不能为空」)、正常订阅 201。

## 遗留(承接第十批,无新增缺陷)

1. profile_import 双管线统一——大重构,不宜夜班;
2. profile_field_id 位置锚定——需先做条目稳定 id(数据迁移);
3. 测试账号清理(现含 trial_b11_r1/r1b,白天
   `cd backend && uv run --project . python -m scripts.cleanup_test_accounts --apply`);
4. 观察项:PNG OCR 中文质量 / #346 混合条款噪声 / **教育时间倒置 PUT 接受**
   (本轮记录:API 不校验 end<start,check-overlap 对倒置区间不告警;前端
   日期控件可防,如需收紧属 schema 增强,非缺陷);增强候选:岗位下拉搜索框。

## 给用户/白班

- 机器重启**第八连**(9-10 21:19:58,距上次重启 9-10 06:18 不足 15 小时,频率
  仍在升高),重启即挂全套服务;临时自救双击 `start.bat` 或全局 `tcmjob`。
  建议白天排查 Windows 计划任务/更新(七连时刻已全天随机,本次 21:19 晚间形态)。
- 本晚 1 处小缺陷已修复推送:订阅名纯空白曾入库为空串(现 422 拒绝)。
- 探针复用:`logs/trial_b11_round1.py`、`logs/trial_b11_round2.py`(已 gitignore)。
