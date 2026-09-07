# 第八批首班交接(2026-09-07 夜 → 09-08 凌晨收工)

承接第七批(`6b26f3e` 末班收尾)。本班**零代码改动、零新缺陷**(继第七批末班后第二晚),
主要成果是两项挂账实证与一轮全链路成功路径验证。

## 本班完成

### #6 时区修复白天实证通过(挂账四班,结案 ✓)

`7f0a5c8` scheduler 本地时区修复后,今日 09:00(本地)auto 抓取首次以期望形态触发:
`crawl_runs` id=31 `trigger=auto` `started_at=2026-09-07T01:00:00+00:00` = **本地 09:00:00 整**。
对照旧 UTC bug 形态(id=29 `T09:00:00Z` = 本地 17:00)——修复实证通过,无需再查。
今日 09:00 抓取幂等零新增(库内 348 条与昨夜持平)。

### 三轮循环(新视角:成功路径产物验证 + UI 走查 + 溯源抽查)

1. **第 1 轮 API 成功路径**(`logs/trial_b8_round1.py`,新账号 trial_b8_r1):建档 →
   #10 生成草稿(11 条目引用全部真实,真实性红线 ✓)→ 审阅全 adopt → 导出四组合
   (docx/pdf × application/diagnostic)全 200 且二进制头正确(PK / %PDF,38-95KB)→
   field-references `{field_id,count,draft_ids}` → institutions/health → 订阅+显式 scan
   (`{scanned,pushed,notified}`,pushed=0 不回放口径 ✓)→ 报告创建。
2. **第 2 轮 UI 走查**(IAB):总览/我的履历/简历生成/岗位库+详情抽屉,布局零缺陷;
   抽屉溯源链(来源 URL/解析器/置信度/抓取时间)完整呈现。
3. **第 3 轮溯源抽查**(红线):348 条溯源四要素缺失 0;(institution_id, source_url)
   重复 0;job_snapshots 55 行在用;抽样 3 条均官网 URL+具名解析器+今日时间戳。

### 口径澄清(本轮新增 4 条,累计勿报清单见第七批首班 handoff)

1. **总览「岗位 348」vs 岗位库「264 条样本」**:348=trust=all 全量,264=real 可信默认
   视图(348 = 264 real + 29 placeholder + 55 fixture)。数据信任分级设计,非数字不一致。
2. **档案只有个人信息(basics)无履历条目时**,岗位库匹配度列显示「请完善档案以查看
   匹配度」:`is_empty` 只看集合条目(schemas.py:263 / resume.py:433 attach_job_matches),
   引导合理非缺陷。trial_b7_r1 即此形态(basics 有「陆之遥」,集合空)。
3. **导出层 profile_field_id 守卫**按「条目 id 或 位置键」回退(resume.py:89
   `item.get("id") or f"{collection}-{index+1}"`);API 建档条目 id=None 时两端都用位置键,
   守卫不会误伤(与遗留 #2 位置锚定机制同源)。
4. **草稿提及目标机构名属正常**:仅出现在「求职目标」小节的应聘意向声明
   (「应聘 XX医院 - XX岗位…」),不是把机构名捏造为履历事实。

### 机器/运行形态

- 机器 21:36:09 重启(**三连**:9-5 夜 00:38、9-6 夜 22:23、9-7 夜 21:36——建议白天
  查一次计划任务/Windows Update 定时),服务随之全挂,本班 23:33 以
  `scripts/start-local.ps1 -NoBrowser` 拉起,四端点全 200,backend.log 全程 0
  Traceback/ERROR。
- 探针账号:trial_b8_r1 新增(档案+草稿 35/36 各一份+#10 关联),连同 trial_b7_r1/r2
  留 `scripts/cleanup_test_accounts.py` 统一清理(夜班不动库,白天 `--apply`)。
- 服务持续存活至本班收尾;运行代码 = 干净的 `6b26f3e` 工作区(零漂移)。

### IAB 自动化环境坑(沉淀,勿再踩)

- **Playwright locator 注入点击在本机 IAB 系统性超时**(元素可见、无遮挡、handler 正常
  仍超时);`cua.click` 坐标间歇有效(受渲染面状态影响);dom_cua 节点点击同样会失效。
  与第七批「evaluate 点击」坑同源。UI 走查优先 domSnapshot(始终可靠),截图作辅助。
- **IAB guest 渲染面故障**:视口切换(setViewportSize)或交互后截图出现 2x2 平铺伪影、
  点击坐标错位;**重开标签页即恢复**,非产品 bug(用户真实浏览器不受影响)。
- urllib 探针取响应头须 lowercase 后取(uvicorn 发小写 `content-type`)。
- 裸 `python` 不在 Git Bash PATH,一律 `uv run --project backend python`。

## 遗留(承接第七批,无新增、无变化)

1. profile_import 双管线统一——大重构,不宜夜班;
2. profile_field_id 位置锚定——内容级锚定需先做条目稳定 id(数据迁移);
3. PNG OCR 中文识别质量 / #346 混合条款噪声——能力边界观察项(本轮抽屉「要求」段
   仍可见混合条款,如中共党员与学历并列,与既有观察一致);
4. 岗位下拉搜索框——产品增强(500 上限已够当前库 348 条);
5. 测试账号清理(trial_b7_r1/r2 + 本班 trial_b8_r1)——白天
   `cd backend && uv run --project . python -m scripts.cleanup_test_accounts --apply`。

## 红线确认

- 未投递任何岗位;scheduler 配置只读未动;岗位数据只增未删(探针仅新增 b8 档案/
  草稿/报告,订阅已删);简历个人真实信息脱敏规则无改动。
- 后端 473 / 前端 205 测试基线未受影响(本班零代码改动,未触发重跑条件)。

## 给下批(巡逻/末班)

- 探活时注意机器三连重启先例,服务不在则 `scripts/start-local.ps1 -NoBrowser` 拉起;
- 本班无代码改动,巡逻判「无事可修」的口径参照上两晚:剩余遗留均大重构/观察项/增强,
  不为凑量改代码;
- 探针复用:`logs/trial_b8_round1.py`(函数式、可幂等重跑:已存在账号走登录分支;
  注意会新增草稿)。
