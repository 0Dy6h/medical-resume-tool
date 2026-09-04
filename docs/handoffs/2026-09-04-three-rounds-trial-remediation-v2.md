# 交接：2026-09-04 — 第二批三轮「试用体验→问题清单→整改→验证」循环

在上一批三轮整改（1e08b83）基础上又跑了完整三轮。**三轮改动已分轮提交**：
`9de36eb`（docs）、`fea2fcf`（第一轮）、`ee3634b`（第二轮）。基线后端 435 → 最终 443 passed；
前端 200 passed + typecheck + build 三绿。

## 第 1 轮：全流程试用（注册→岗位库→详情→履历→生成→导出→订阅→分析）

发现 4 个问题，全部整改（fea2fcf）：

1. **[P2] z2hospital 文章解析器把页面样板混入 requirements**：全部 10 条
   z2hospital-article-v1 岗位正文以「作者：审核：编辑：来源：发布时间：…阅读次数：」开头。
   根因：`extract_job_from_article` 对 `div.main` 直接 `get_text`，meta 行位于标题与正文之间。
   修复：正文收集时按 `_META_LINE` 正则剥离。重抓后实测全部干净（见第 3 轮端到端验证）。
2. **[P2] 图片表格型公告产生垃圾要求条款「岗位及条件 二」**：#95/#100 的条件表在站点上是
   PNG 图片（文本不可得），正文残留「一、岗位及条件 二、报名方式」，而「岗位及条件」不在
   `REQUIREMENT_HEADINGS`，分段器产出无意义 unmet 条款，列表显示误导性的「满足 0/1 项」。
   修复：`岗位及条件` 加入标题表；图片型公告现在诚实空态（total=0 →「以公告原文为准」）。
3. **[P2] 待遇条款被计为硬性要求**：#97 多一条「岗位待遇…待遇面议」unmet、#346 有 4+ 条
   （引进待遇/工资福利…）。根因：`_requirement_block` 截止正则要求枚举前缀，「岗位待遇」
   裸标题截不住。修复：`segment.is_benefits_clause`（待遇标记；学历标记优先留给学位门；
   含需求提示词不误杀），resume 匹配层与资格条款同位跳过。#97 列表从「满足 0/5」→「满足 0/4」。
4. **[P3] 订阅计数未做 ASCII 词边界精筛**：`count_total_matching_jobs` /
   `has_matching_jobs_last_30d` 只做 LIKE 粗筛，RICU 会计入 ICU，影响宽词告警比率与展示。
   修复：与 `find_new_jobs_for_subscription` 同样补 `refine_keyword_hits`。

新增 5 项测试；后端 440 passed；IDF 表重建后字节不变（可复现）。

## 第 2 轮：边界与异常路径（导入/草稿生命周期/订阅触达/导出变体）

覆盖：docx 导入（姓名正确进 basics）、PNG OCR 导入（本机 tesseract 正常出字）、空文件 400、
重叠检查（27% 重叠 < 50% 阈值不告警属设计）、草稿审阅完成→导出四变体（docx/pdf/诊断版，
魔数与中文文件名 RFC5987 全部正确）、岗位状态 422 白名单、订阅→重抓→扫描→通知闭环、
报告生成（分析页有消费，非死功能）。

发现 2 个问题并整改（ee3634b）：

1. **[P2] 并发订阅扫描重复通知**：手动抓取完成后后台线程自动 `scan_subscriptions`
   （`_crawl_then_scan`），用户再点「检查更新」与之并发——check-then-insert
   （读 last_pushed_at → 建通知 → 推进检查点）跨多个连接非原子，实测同秒为同一订阅
   生成两条重复通知。修复：进程级 `_SCAN_LOCK` 串行化（本地单进程部署足够）。
   新增 8 线程并发回归测试。
2. **[P3] markdown「# 姓名」被静默丢弃**：docx 标题段落（无 # 前缀）一直能映射
   basics.name，但 md 行式提取保留 `#` 前缀，纯中文姓名检测失败——basics、
   unassigned_blocks、warnings 三处都没有（上一批交接说进 unassigned_blocks，实测是彻底丢失）。
   修复：md/markdown 行式提取剥离标题标记（.txt 不受影响）。

## 第 3 轮：前端 UI 视觉复核 + 端到端验证（本轮，无新缺陷）

- 浏览器实际走查：总览/岗位库/详情抽屉/订阅面板/通知角标（4 条未读）渲染正常。
- 列表匹配度列实时反映修复：#97「满足 0/4 项」、#100/#95「以公告原文为准」。
- **端到端**：手动重抓浙大二院（run #20，10/10 成功）→ 重抓后 requirements/responsibilities
  全部无样板（#97 直接以「二、任职要求」开头）；旧正文按 A4 归档到 job_snapshots（20 条），
  详情接口 `history` 返回 1 条快照。
- 「机构 24」是分析页口径（有岗位的机构数，30 种子中 6 家无岗位），非缺陷。
- 观察项（不改）：IAB/headless 自动化里 Playwright locator 点击侧边栏按钮会超时，
  evaluate 点击正常——自动化环境 quirk，非产品缺陷证据；导出端点 format/mode 是
  Query 参数，body 传参会静默取默认值（前端用的是 query，正确）。

## 验证记录（最终态）

- 后端：`uv run --project backend pytest -q` → **443 passed**（435 基线 + 8 新测试）
- 前端：`pnpm test`（200）/ `pnpm typecheck` / `pnpm build` 三绿
- 8000/5173 在跑（start-local -NoBrowser）；z2 已重抓，库内 z2 数据为修复后正文

## 已知残留 / 下批候选

- 图片条件表（z2 部分岗位）文本不可得 → total=0 诚实空态；如需内容需 OCR 图片，
  属新增能力（对齐 PDF 附件政策：需切片含 fixtures 与测试再做）。
- 同一岗位可重复生成草稿（#9/#10 并存），按版本设计接受；如需替换语义需产品决策。
- 测试账号持续累积：trial_r1/trial_r2/fresh_user/trial_v2_r1/r1b/r2/verify_ui 留在
  8000 库（无删除端点，直接删库行有 FK 风险），需要清理工具时再做。
- `#346`「思政特岗教授 享受…工资和福利待遇…」这类职称+待遇混合条款因含需求提示词
  保守保留（保守方向正确，仅 1 条噪声）。
- profile_import 的文档级管线（extraction.py/facts.py 的 ExtractedDocument 路径）存在但
  端点仍走 legacy 行式管线；两套并存是有意过渡，接线时需统一。
