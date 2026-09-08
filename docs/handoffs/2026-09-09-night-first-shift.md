# 2026-09-09 夜班首班交接(2026-09-08 夜,第九批)

首班 23:31 起跑(预算内 01:01 前完成)。/init → /loop 三轮 → /end → /commit 全链执行。

## 终态速览

- **零代码改动、零新缺陷**(连续第三晚)。本批唯一产物:探针脚本(logs/,已 gitignore)
  + 本交接文档 + 夜班记录。
- 服务:23:31 四端点全 000(机器重启四连背景,上次 07:19 重启即挂),23:33
  `scripts/start-local.ps1 -NoBrowser` 拉起,四端点全 200,之后全程稳定。
- 测试:零代码改动,按既定口径免重跑全量(上一绿态:后端 473 passed / 前端
  204 passed + typecheck + build,第八批末 @ 8cdece0)。
- git:基线 e276e16,工作区原有 AGENTS.md 一行 File Map 补挂(前次 /init 产物,
  良性),随本班 /commit 一并入库。

## 三轮循环明细

### 第 1 轮:experienced 视角 API 全流程(trial_b9_r1,logs/trial_b9_round1.py)

新账号注册→experienced 建档(在职跳槽画像,区别于 b8 的 fresh_grad)→auth/me→
带登录态 analytics→自适应挑真实岗位(342 南京医科大学专职辅导员,硕士/不限)生成
草稿#37→17 条目引用全真实(红线 ok)→审阅全 adopt→docx+pdf 导出文件头正确→
岗位状态 saved→archived→DELETE 生命周期(b8 未探)→check-overlap 形状→通知全链路
(列表/未读数/单条已读/read-all 归零,b8 未探)→草稿列表。**0 issue。**

### 第 2 轮:边界与异常路径(logs/trial_b9_round2.py)

- 全部按预期返回 4xx:重复用户名 400 / 空用户名 422 / 无 token 401 / 错密码 401 /
  jobs limit=0,501、offset=-1、fresh_days=5000 均 422 / limit=500 边界内 348 条 /
  不存在岗位生成草稿 404 / 非法岗位状态 422 / 删不存在订阅与读不存在通知 404 /
  空关键词订阅 422 拒绝 / 伪 field_id 引用查询 200 空引用。
- **409 审阅守卫复测保持**(未审阅导出→409,第八批结论三度实证)。
- 唯一疑点「人造重叠未检出」经复核为**探针乌龙**:`POST /api/profile/check-overlap`
  的入参是**请求体里的 ProfilePayload**(前端保存前预检语义),不是查已存档案;
  发 `{}` 等于查空档案。改传入重叠档案后 overlap=true + 条目对正确返回。产品无缺陷。
  **0 新缺陷。**

### 第 3 轮:浏览器视觉复核(IAB)

- trial_b9_r1 登录走通(登录表单按钮点击可提交;密码框内 Enter 不触发表单提交——
  IAB 合成键未触发 React onSubmit,未能判定为产品问题,列观察项)。
- 五页面 DOM 级全部健康:总览(岗位 348/机构 24/地区 12)、简历生成(岗位下拉+选项)、
  我的履历(33 个输入框有值,experienced 档案完整回显,「职场人」模式保持)、
  岗位库(信任分级默认视图 264 条+筛选器+订阅区)、分析(348 样本/解析器 13/信任切换)。
- **环境坑:IAB 截图管线不稳**——两次 `capture failed for guest`、一次整页拼贴伪影
  (侧栏×2、内容纵向重复)。已用 DOM 计数证伪(品牌文本×1、h1×1,单树无重复),
  拼贴是截图伪影非渲染缺陷。总览页获一张干净截图。页面像素复核能力今夜受限,
  以 DOM 结构 + 正文 + input value 三层复核替代。

## 探针坑(新增沉淀)

1. `check-overlap` 入参是 body payload 非已存档案(见上)。
2. profile 页数据在 input value,`innerText` 断言必误报(旧坑再证,第 3 轮实测)。
3. IAB 里 locator.click 对本应用按钮频繁超时(退出登录/导航按钮均复现),
   `evaluate` 内 `btn.click()` 稳定可用——夜间 UI 走查直接走 evaluate 派发。
4. 探针幂等:注册失败自动转登录;订阅建了即删;报告创建不重复做(b8 已建过,
   且 POST /api/reports 无 GET 列表端点,避免垃圾报告回库清理)。

## 遗留(承接第八批,本班无新增)

1. profile_import 双管线统一——大重构,不宜夜班;
2. profile_field_id 位置锚定——需条目稳定 id(数据迁移);
3. 测试账号 trial_b7_r1/r2+trial_b8_r1+trial_b9_r1 清理——白天
   `cd backend && uv run --project . python -m scripts.cleanup_test_accounts --apply`
   (自动先备份;夜班不动库);
4. 观察项:PNG OCR 中文质量 / #346 混合条款噪声 / 登录表单 Enter 不提交(见第 3 轮);
   增强候选:岗位下拉搜索框。

## 给巡逻班/末班

- 服务已拉起且稳定,四端点 200;巡逻探活即可,勿重启。
- 零代码改动夜:按口径免重跑全量测试;若你班次改了代码再跑。
- 本班提交:AGENTS.md File Map 补行 + 本文档;工作区应收口干净。
