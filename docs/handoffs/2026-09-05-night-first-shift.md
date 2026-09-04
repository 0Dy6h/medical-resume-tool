# 交接:2026-09-05 夜班首班(01:30 班次升级,23:30 首班未运行)

夜班自动班次产物。预算 90 分钟(01:31–03:01),执行 /init → /loop → /end → /commit。
基线:后端 443 passed、前端 200 passed + typecheck + build 三绿(与上一批终态一致)。

## /loop 第 1 轮:API 全流程试用(新账号 trial_n1_r1c,30 项探针,0 缺陷)

覆盖:注册/登录/me、机构 30 种子与禁用原因结构、real/fixture 切片、岗位溯源字段
(source_url/fetched_at/parser_name)、强类型 ProfilePayload 往返、check-overlap 干净路径、
field-references、学历门 422(硕士档案碰博士岗)、草稿生命周期(未审阅导出 409 →
override=true 放行 → adopt/edit/remove 决策 → reviewed → docx/pdf/diagnostic 四导出魔数)、
订阅→扫描→通知→已读→unread 归零→删除、报告与分析页。

勘察确认两个非缺陷:API `/api/jobs` 默认 `trust=all` 是有意设计(前端 JobsPage 默认发
`trust=real`,CONTEXT.md 的「默认视图」由前端保证);列表条目信任字段叫 `data_trust`。

## /loop 第 2 轮:边界与异常路径(29 项探针,1 个真缺陷,已修)

覆盖并全部通过:跨用户草稿隔离(A 的草稿 B 读/改/导出均 404)、SQL 通配符关键词
(%/_'/\\) 不 500、limit>500 与 bad trust/fresh_days=0 的 422、offset 超界空页、错误密码
/重复注册/假 token、订阅空词与空白词拒绝、缺失通知 404、禁用机构 recrawl 拒绝、
crawl-runs 带 trigger、md「# 姓名」导入回归(上批修复仍有效)、不支持扩展名拒绝。

**[P2] 重叠检测对无 id 条目漏报(flagged items)**:`check_profile_overlaps` 用
`str(item.get("id",""))` 做去重键,API 载荷经 `to_profile().model_dump()` 后 id 为
`None`,`str(None)="None"` 恒真值——同一重叠对里只有第一条进 `items`,其余被去重键
吞掉(`overlap` 布尔仍正确)。修复:去重键有 id 用 id,无 id 回退对象身份
(`("obj", id(item))`);补 2 个回归测试(单对 2/2、双对 4/4 全上报)。单文件 51 passed,
重启服务后线上复测 2/2、2/2 上报正确。

两个 FAIL 归因为试探用例自身,非缺陷:50% 边界案例按日历天算恰为 49.9%(阈值为
`ratio >= 0.5`,≥50% 会告警);md 导入首次 400 是手搓 multipart 分隔符少两横。

## /loop 第 3 轮:验证轮

- 全量后端 pytest(含 2 新测试);前端无改动,沿用本晚 typecheck/build 三绿基线。
- 修复经服务重启后 API 级复测确认。
- 浏览器 UI 视觉走查本轮未做(预算约束;上一批第 3 轮已全量走查且 0 缺陷,今晚
  API 两轮 62 探针覆盖为主)。

## 设计观察(不改,记录备查)

- `check_profile_overlaps` 只做同集合内配对(edu×edu、exp×exp),不做跨类
  (edu×exp)——`test_cross_category_not_checked` 固化。领域上合理:专硕并规培、
  在职读研是医疗行业常态,跨类告警会误伤最典型的合规简历。
- 重叠告警口径是 `ratio >= 0.5`(含等于);AGENTS.md 写「>50%」,实际实现含等于,
  边界语义以代码与测试为准。

## 遗留(承接上一批,无新增大项)

上一批「已知残留/下批候选」5 项全部原样承接(图片条件表 OCR、草稿重复语义、
测试账号清理工具、#346 单条噪声、profile_import 双管线接线)。新增:无。

## 验证记录

- 修复后全量:后端 pytest(结果见提交信息/夜班记录);前端未动,基线三绿。
- 服务状态收班时:8000(带修复重启)/5173 均在跑。
- 夜班记录:`螃蟹的公众号写作流水线/夜班/简历工具/2026-09-04.md`。
