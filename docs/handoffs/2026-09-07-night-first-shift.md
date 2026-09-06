# 第七批首班三轮循环交接（2026-09-07 凌晨收工）

承接第六批（`bb27067`：后端 473 + 前端 204 三绿）。基线验证一致，本班 1 个功能提交，
最终 **后端 473 passed（基线重跑一致，后端零改动）+ 前端 205 passed + typecheck + build 绿**。

## 本班提交

| 提交 | 轮次 | 内容 |
| --- | --- | --- |
| `55b4aba` | 第 1 轮 | fix(product): 简历生成页岗位下拉对齐后端上限 500（遗留#5 拍板落地） |

- #5 现状实证：库内岗位已 **348 条**（>100），旧口径下拉只取最新 100 条，248 条岗位
  （含 #10 华西医院影像科医师 fixture 演示岗）不可达。修法：`ResumePage.tsx` 导出
  `JOB_DROPDOWN_LIMIT = 500`（对齐后端 /api/jobs 上限）并在取数时使用，测试钉住。
  关键词搜索属产品增强，另立观察项不混入本修。
- 浏览器实测验收（IAB，trial_b7_r1 登录）：下拉 348 项全量、#10 可达、选岗联动与
  草稿历史正常，348 项原生 select 无卡顿。Vite HMR 已让运行实例吃到修复（348 实证）。

## 第 1 轮 API 走查（trial_b7_r1/r2，0 新缺陷）

覆盖：auth 边界（错密码 401/空密码 422/用户名 ≤32 上限）、草稿跨用户隔离
（GET/PUT 他人草稿 404）、全 remove 后导出（双模式都 422，空守卫与模式无关系
`main.py` 注释明示设计）、岗位状态生命周期（PUT/DELETE/非法值 422/幽灵 404）、
通知 limit 0|101→422、幽灵通知 mark-read 404、check-overlap 非法 mode 422、
crawl-runs 显式空 422 复核、jobs offset 越界/幽灵机构/组合过滤。

## 第 2 轮 边界与异常路径（0 新缺陷，口径澄清 7 条）

1. **check-overlap 契约**：检查的是**请求体携带的档案**（非已存档案），响应键是
   `{overlap, items}` 而非 `warnings`。语义全验：同集合重叠 70%≥50% 告警 ✓、
   8%<50% 不告警 ✓、跨集合（教育 vs 经历）不告警 ✓、不可解析日期不告警不崩溃 ✓。
2. **禁用机构口径三分**：crawl-runs POST → 400「所选机构均尚未适配」；recrawl →
   400「不存在或尚未适配」（幽灵机构同此 400，勿报 404 缺陷）；订阅 → **201 接受**
   （设计：订阅列表显示维护中 is_maintenance，扫描跳过非 active 机构）。
3. **scan pushed=0 是设计**：订阅只推 `last_checked_at`（创建时刻）之后新抓的岗位，
   创建订阅不回放存量；首扫 pushed=0 勿报缺陷。
4. **PUT /api/profile = 全量替换**：部分载荷会清空未带字段（REST 语义，UI 恒全量
   提交，无现实触发路径，观察即可）。
5. **keyword LIKE 通配安全**：`%`/`_` 粗筛后由 `refine_keyword_hits` 的 `re.escape`
   精筛兜底，keyword=`%` 返回「文本含字面 %」的岗位（实测 total=items=348），
   total 与 items 一致，非注入缺陷。
6. **草稿 PUT 不校验伪造 profile_field_id**（200 接受），守卫在导出层：application
   409、`override=true` 逃生门 200（与第六批 UI 侧结论闭环）。
7. 通知 read-all 空列表 200、单条已读、unread-count 形状正常。

## 给下批的探针提示

- 复用 `logs/trial_b7_round1.py`（auth 边界/草稿隔离/导出边界/状态生命周期/通知
  limit/爬取校验/过滤组合）、`trial_b7_round2.py`（通知全生命周期/重叠语义/草稿
  PUT 伪造引用/override 逃生门）、`trial_b7_round2b.py`（check-overlap 正确契约/
  阈值上下界/LIKE 通配/profile PUT 语义）骨架；
- **探针账号**：trial_b7_r1（有 #10 草稿一份、档案完整）/trial_b7_r2，留
  `scripts/cleanup_test_accounts.py` 统一清理；
- **探针脚本非幂等**：trial_b7_round2.py 顶部模块级代码在 `import` 时会整体重跑
  （本班实测重复注册 400→级联 401 空跑），复用片段请抽取函数或单独脚本；
- **Python `%` 格式串坑**：标签里含 `%`（如 `70%≥50%`、`keyword='%'`）会炸
  ValueError，一律 `%%` 转义——本班两次踩中；
- 沿用第六批提示（IAB evaluate 点击、confirm 埋点、user_status 对象、Education.id
  string、fresh_days≤3650、中文 keyword 要 quote）。

## 已知残留 / 下批候选（承接第六批，更新后 5 项）

1. profile_import 双管线并存——大重构（原样承接）；
2. #346 思政+待遇混合条款噪声——观察项（原样承接）；
3. PNG OCR 中文识别质量——能力边界观察项（原样承接）；
4. profile_field_id 位置锚定固有边界——需条目稳定 id（数据迁移，原样承接）；
5. **[新] 岗位下拉无关键词搜索**——#5 上限已提至 500，数据超 500 后需搜索/切片
   （产品增强候选，非缺陷）。
（#6 09:00 本地触发实证——今晚巡逻班待办，见下。）

## 给巡逻班 / 末班

- **明早 09:00（本地）后核实 auto 抓取是否本地触发**（`7f0a5c8` 时区修复的首夜
  实证，巡逻探活时顺带查 `crawl-runs` 最新 auto run 的本地时刻）；注意机器今晚
  22:23 曾重启、服务由本班 23:33 重拉，若再重启需重新探活+拉起；
- 运行代码：前端含 `55b4aba`（HMR 已生效），后端 = `bb27067` 无变化；
- 本班服务未重启过（前端改动 HMR 生效），8000/5173 四端点 200。

## 验证记录（最终态）

- 后端：473 passed（本班 23:37 重跑 127s，后端零改动，终态一致）
- 前端：205 passed（204+1 钉住 JOB_DROPDOWN_LIMIT）+ typecheck + build 三绿
- git：main @ `55b4aba` 工作区干净（logs/ 探针 gitignore 内按可复用资产保留）
- 红线遵守：未投递任何岗位；scheduler 配置只读未动；岗位数据只增未删
  （本班仅新增 trial_b7_r1 在 #10 的 1 份草稿与 2 个测试账号，无真实岗位/报告残留，
  探针订阅已删）；脱敏规则无改动。
