# 2026-09-10 夜班首班交接(2026-09-09 夜,第十批)

首班 23:31-00:4x。**本夜打破连续三晚零代码:两处真实缺陷修复**,来自 /loop
三轮增量探针(第十批探针 `logs/trial_b10_round1.py` / `trial_b10_round2.py`,
账号 trial_b10_r1,gitignore 保留可复用)。

## 体检与运行形态

- 23:31 首班判定:无锁、当日记录不存在 → 首班。
- **机器重启第六连:当晚 20:38:50**(此前五连:9-5 00:38 / 9-6 22:23 / 9-7 21:36 /
  9-8 07:19 / 9-9 07:03)。四端点全 000,23:32 pwsh 分离拉起,23:35 四端点全 200。
- git 干净 @ `a5063ed` 与 origin/main 同步;库只读抽查 jobs=349(348→349,
  今晨 09:00 auto 爬虫 +1,只增未删);crawl_runs #33 = 本地 09:00 auto completed
  (时区修复形态保持);日志 0 错误。

## /loop 三轮(增量设计,不重复九批用例)

- **第 1 轮** trial_b10_r1 fresh_grad 视角 + 九批未探端点:institutions 公开形状
  (30 机构,18 禁用均带 blocked_reason)、institutions/health 鉴权、岗位详情溯源
  四字段齐全、**学位门槛正向检查(fresh_grad 本科投博士岗 422 拒绝)**、9 类档案
  集合全填充并生成草稿(16 条目引用全真实、覆盖全部 9 集合)、导出文件头、
  crawl-runs 形状、fresh_days=3650 上限、trust 过滤、recrawl 越界守卫。
  → 发现 **P1:POST /api/reports 匿名可写**(全站唯一未鉴权写端点)。
- **第 2 轮** 边界与语义:导入四态(.txt 200=设计内支持,非缺陷;伪 docx 400;
  真 docx 200 契约 14 keys;1x1 png 见下)、**进程内 ICU 词边界(ICU 不中 RICU)
  通过**、check-overlap 三组(experiences 80% 检出 / 33% 不检 / 跨集合不检)、
  报告空白标题 422、mark-read 形状、档案重 PUT 幂等、同岗位再生成只增。
  → 发现 **P1:损坏图片上传 /api/profile/import 返回 500**。
- **第 3 轮** 本会话未挂载 node_repl/IAB,浏览器目视复核不可用 → 替代打法:
  前端全量组件测试(205 个 jsdom DOM 断言)+ typecheck + build + SPA 四端点冒烟。
  今晚改动纯后端,UI 风险面(reports 按钮走登录态 token)已由代码与 API 测试覆盖。

## 两处整改(均已实测验证)

1. **reports 补鉴权** `backend/app/main.py`:`POST /api/reports` 增加
   `get_current_user` 依赖,与全部其它写端点对齐。前端全站都在登录门禁后,
   `request()` 自动附 token,UI 无感。运行时实测:匿名 401、登录态 201。
   既有 5 个测试 6 处调用补 headers,新增匿名 401 回归测试
   (`test_report_creation_requires_auth`)。
2. **损坏图片诚实降级** `backend/app/services/profile_import/legacy.py`
   `_ocr_image_bytes`:截断图片流可通过 `Image.open` 但在 `exif_transpose →
   load()` 抛 `OSError: broken data stream`,原先无包裹逃逸成 500。现帧解码
   失败→警告降级(保留已解码帧文本),迭代层再兜底转 `ProfileImportError`(400)。
   运行时实测:200 +「图片帧无法解码」+「未识别到可解析文本」双警告。
   新增回归测试(`test_import_endpoint_broken_image_degrades_to_warnings`,
   fixture 为 IDAT 长度与声明不符的截断 png,已验证 open 成功/load 失败形态)。

## 验证基线

- 后端 **475 passed**(原 473 + 新增 2),3 分 42 秒。
- 前端 **205 passed + typecheck + build ✓**。澄清:前端测试自第七批 55b4aba
  后未变,205 是真实计数,第九批 handoff/记录里的「204」为误计。
- 整改后服务已重启(pwsh start-local),四端点 200,运行代码 = 工作区。

## 遗留(承接九批,无新增)

1. profile_import 双管线统一——大重构,夜班不动(注意:本次修复改的是 legacy
   管线的 `_ocr_image_bytes`,统一时需保留该降级语义);
2. profile_field_id 位置锚定——需条目稳定 id(数据迁移);
3. 测试账号 trial_b7_r1/r2 + trial_b8_r1 + trial_b9_r1 + trial_b10_r1 在册——白天
   `cd backend && uv run --project . python -m scripts.cleanup_test_accounts --apply`;
4. 观察项:PNG OCR 中文识别质量 / #346 混合条款噪声;增强候选:岗位下拉搜索框。

## 环境坑沉淀

- **本会话未挂载 node_repl/IAB 工具**:浏览器目视复核不可用时,用前端组件测试
  套件(jsdom DOM 断言)+ build + 四端点冒烟替代;后端-only 夜可放心采用。
- 匿名可写端点的排查手法:grep 路由签名里的 `Depends(get_current_user)` 缺行,
  再对照「全站登录门禁」确认非产品意图。
