# 总监验收 — traework 2026-08-24 两切片（导出排版重做 + 前端视觉动效）

被审提交：`cc993e9 feat(export)`、`e18a162 style(frontend)`（main 领先 origin/main 9 个 commit，未 push）

结论：**两项均通过（有条件通过）**。导出从"不可用"变成"可投递"，前端视觉与动效达标；但导出侧有 1 个必修的生产风险与 1 个静默丢内容问题，须再开一个小切片修掉。

---

## 1. 门禁复核（总监独立复跑，非采信报告）

| 门禁 | traework 报告 | 总监复跑 | 结论 |
|---|---|---|---|
| `uv run --project backend pytest -q` | 339 passed | **339 passed / 53.75s** | 一致 |
| `pnpm test` | 168 passed | **168 passed / 16 files** | 一致 |
| `pnpm typecheck` | clean | clean | 一致 |
| `pnpm build` | 1604 modules | 1604 modules，CSS 35.00 kB / JS 302.14 kB | 一致 |
| 提交范围 | 前端提交零 backend | `git show --stat` 确认 e18a162 仅 `frontend/`；cc993e9 含 backend + 前端下载文件名 | 一致 |
| 依赖 | 零新增 | `package.json` 未出现在任何一次提交的文件清单中 | 一致 |

报告与事实一致，没有虚报。

## 2. 导出侧实测（渲染 + 几何 + 敌意输入）

### 2.1 已修复（实证）

- **D1 内容丢失已修**：PDF 第 1 页抽取文本含 `13800000000` / `zhangsan@example.com` / 个人简介片段（改造前只有姓名）。
- **D2/D3/D4 已修**：block 最右 `x1=530.1`，右边界上限 `532.9` → 无溢出；左边界集合 `[65.2, 87.9, 262.8, 277.6]`，`87.9` 即详情悬挂缩进（大于主行 `65.2`）；换行行不再两端拉伸。
- **D7/D9 已修**：DOCX `sectPr` = `w:pgSz w:w="11906" w:h="16838"`（A4）+ `pgMar top/bottom 1134`（20mm）/ `left/right 1247`（22mm）；`footer1.xml` 内含 `PAGE` 与 `NUMPAGES` 域；PDF 多页实测第 1/2 页均有「第 X 页 / 共 2 页」。
- **D10/D11 已修**：`pStyle` 从 `Heading1|ListBullet` 变为 `Heading1|ResumeEntry|ResumeDetail`，`keepNext` 出现 5 次。
- **D12 已修**：`build_export_filename` 产出 `张三-内科医师-简历-20260824.docx`、诊断版 `…-20260824-诊断版.pdf`。
- 附录固定文案未被破坏：`匹配分析附录` / `已满足` / `未满足` 在诊断版 PDF 中均可抽取。

### 2.2 P1 必修 — `assert_lossless` 硬失败会让整份简历导出 500

`_build_resume_doc()`（exporter.py:240）对每个条目调用 `assert_lossless()`，不一致就 `raise AssertionError`，端点 `except Exception` 兜成 **HTTP 500「文件生成失败，请稍后重试」**。

根因：`_parse_entry` 对每段做 `.strip()`（会去掉 Unicode 空白，含全角空格 U+3000、不换行空格 U+00A0），而 `_strip_all()` 只去掉半角空格与分隔符 → 空白差异被当成"丢字"。

13 条敌意输入压测，2 条触发失败并端到端确认 docx/pdf 双双抛错：

| 输入 | 来源场景 | 结果 |
|---|---|---|
| `南方医院 / 住院医师\u3000 / 2022-07-2025-06：负责病房管理` | 用户中文输入法全角状态打空格 | AssertionError → 500 |
| `南方医院 / 住院医师\u00a0：负责病房管理` | 从 Word/PDF 粘贴履历（NBSP 极常见） | AssertionError → 500 |

规格违背：提示词第 2 节明确要求「任何解析不确定的条目**一律回退为整行渲染**，禁止丢字」，实现改成了硬失败。

修复要求（两层都要）：

1. `_strip_all()` 改为先做 Unicode 空白归一（`re.sub(r"\s+", "", s)`）再去分隔符，让空白差异不再构成 violation。
2. `_build_resume_doc` 改为：解析后校验失败 → `logger.warning` + 回退 `Entry(head=None, role=None, period=None, details=[原始整行], raw=原始整行)`，**永不抛错**。`assert_lossless` 保留为纯函数供测试断言。
3. 补测试：上述两条含 U+3000 / U+00A0 的文本必须导出成功且原文完整出现在 DOCX/PDF 抽取文本中。

### 2.3 P2 应修 — 个人信息段多段自述静默丢内容

`_build_header()`（exporter.py:207-211）用 `summary = text` 循环赋值，identity 段出现两段非联系方式文字时**只保留最后一段**。实测：

```
items = [姓名, 联系方式, "第一段自我介绍：内科住院医师三年。", "第二段自我介绍：擅长糖尿病管理。"]
→ summary = "第二段自我介绍：擅长糖尿病管理。"   # 第一段消失
```

审阅页允许用户在段落内增改条目，identity 段又不走 `assert_lossless`，属于无人守护的丢内容路径。修复：`Header.summary` 改 `summary_lines: list[str]`，全部渲染；补测试断言两段都在导出文件里。

### 2.4 P3 观感（可延后）

1. 无详情的条目整行加粗：`求职目标`「应聘 南方医院 - 内科医师…」整句、`论文成果` 标题行、`技能能力`「SPSS · 熟练」都以 10.5pt 粗体渲染，视觉权重压过段落标题。建议：`details` 为空且主行字数超过阈值（或 `section_id in {"target"}`）时用常规字重。
2. 同一行混用两种分隔符：`南方医科大学 · 硕士 / 内科学`（head 与 role 用 `·`，role 内部保留 `/`）。建议统一。
3. 个人简介行紧贴联系方式行，缺 2–3mm 间距；简介左对齐与联系方式居中并置，边界略参差。

## 3. 前端侧实测

静态审计（全部通过）：

- 旧 CSS 类名 **零删除**（旧 221 个类名全部保留，新增至 243 个；差异项 `.15s/.18s/.2s/.3s` 是正则把时长当类名的误报）。
- `prefers-reduced-motion` 存在（全局降级块）；`:focus-visible` 2 处（含侧栏浅色环）；`transition: all` **0 处**；对 `width/height/top/left/margin/padding` 做 transition **0 处**。
- `AnimatedNumber` 实现正确：`matchMedia("(prefers-reduced-motion: reduce)")` 命中时直接 `setDisplayValue(value)`，rAF 在 cleanup 里 `cancelAnimationFrame`，无泄漏。

运行时实测（Playwright + 本地 chromium 1228，1440×960，注册→登录→逐页）：

- 7 个界面全部渲染成功，**console error 0 条**。
- Tab 焦点实测：`BUTTON.nav-item logout` 的 `outline = 2px solid rgb(216, 240, 230)`，深色侧栏内浅色焦点环生效。
- 登录页：网格底纹 + 卡片层次 + 左侧品牌区，明显高于改造前的裸表单。
- 总览页：指标卡（岗位 88 / 机构 24 / 地区 12）、下一步引导卡、01-02-03 工作流卡、近期岗位列表，层级清晰。
- 侧栏：新增「情报 / 我的」分组标题、active 左侧指示条、底部用户区，符合 C5。

界面级发现：

1. **P3（本次引入）Toast 压住顶栏 badge**：右上角 `.toast-container` 与 `.topbar-badge` 重叠，「注册成功」把「公开官网样本 · 真实履历重组」遮掉一半。建议 toast 下移到顶栏之下或右下角。
2. **P3（既存）顶栏与正文标题重复**：顶栏「本地 MVP / 总览」+ 正文「总览 / 公开官网岗位样本与本地履历状态」，同屏两个同名标题。
3. **P3（Task C3 未落实）简历生成页空状态缺失**：未生成草稿时整页只有一个「目标岗位」选择器 + 大片空白，没有「一句话说明 + 下一步按钮」的空状态。
4. **P2（既存，非本次引入）岗位库三栏在 1440px 挤爆**：岗位标题竖排成一列、右侧详情面板被切出屏幕。已比对旧版 CSS：`.jobs-layout {280px 1fr}` 与 `.split-page {minmax(620px,1fr) 420px}` 两版**逐字相同**，确认为既存结构问题（248 侧栏 + 280 订阅 + 620 表格 + 420 详情 ≈ 1600px > 1440px）。本次视觉升级没有引入它、也没有解决它，建议作为下一轮独立切片（表格列宽收敛 / 详情面板改抽屉 / 订阅面板可折叠）。

## 4. 运维事实（顺手记录，AGENTS.md 需更正）

- AGENTS.md 里的 `uv run --project backend uvicorn app.main:app` 从仓库根目录执行会 `ModuleNotFoundError: No module named 'app'`，必须在 `backend/` 目录下执行（`cd backend; uv run --project . uvicorn app.main:app ...`）。
- SQLite 路径是相对当前工作目录的：根目录启动用 `data/app.db`（2 个用户），`backend/` 目录启动用 `backend/data/app.db`（6 个用户，含历史 `verify` / `123` 测试账号）。本次验收的 `qa_ui_check_0824` 已从 `backend/data/app.db` 清理。

## 5. 交给 traework 的修复单（下一切片）

必修：

1. 按 2.2 修 `assert_lossless` 硬失败（空白归一 + 解析失败回退整行 + 两条空白用例测试）。
2. 按 2.3 修 identity 多段自述丢内容（`summary_lines` + 测试）。

建议同批：

3. 无详情条目不整行加粗；head/role 分隔符统一；简介与联系方式间距（2.4）。
4. Toast 容器避开顶栏 badge；简历生成页补空状态。

红线不变：`test_matching_eval.py` 8 passed；后端 339 passed 不回退；前端 168 passed / typecheck / build 全绿；零新增依赖；零 DB schema 变更；导出内容一字不增不减。

---

# 第二轮（修复轮）验收 — commit 8c76a97

结论：**通过**。上轮两个必修项已按规格修好，实测无残留；建议批次 5 项全部落地。仅剩 3 条纯观感建议，可随后续切片带走，不阻塞使用。

## R2.1 门禁复核（总监独立复跑）

| 门禁 | 报告 | 复跑 | 结论 |
|---|---|---|---|
| 后端 `pytest -q` | 344 passed | **344 passed / 51.42s** | 一致（339 → 344，新增 5 条） |
| 前端 `pnpm test` | 168 passed | **168 passed / 16 files** | 一致 |
| `pnpm typecheck` / `pnpm build` | clean / 1604 modules | clean / 1604 modules，JS 302.49 kB | 一致 |
| 改动范围 | 4 files, +177/-22 | `git show --stat` 一致（exporter.py / test_export_layout.py / ResumePage.tsx / styles.css） | 一致 |

代码差异抽查与规格逐条吻合：`_strip_all` 前置 `re.sub(r"\s+", "", s)`；`assert_lossless` 调用被 `try/except AssertionError` 包住并回退 `Entry(details=[原始整行])` + `logger.warning`；`Header.summary` → `summary_lines: list[str]`；`role` 连接符 `" / "` → `" · "`；`head_run.bold = bool(entry.details)` / PDF `main_style`；`.toast-container top: 20px → 80px`。

## R2.2 必修 1 复测 — 空白字符不再打挂导出

敌意输入从 13 条扩到 **19 条**（新增零宽空格 U+200B、BOM U+FEFF、连续三个 NBSP、全角+制表符混合、emoji、超长单行、纯空白条目）：

- 解析层 `assert_lossless`：**19/19 通过，0 失败**（上轮 2 条失败）。
- 端到端真渲染（每条都跑 DOCX + PDF，共 38 次导出）：**0 失败**。
- 上轮两条致命输入的内容完整性（把日期美化 `2022-07-2025-06` → `2022.07 – 2025.06` 一并归一后比对）：DOCX / PDF 均**完整保留**原文；逐要素核对「南方医院 / 住院医师 / 2022 / 2025 / 负责病房管理」全部命中。

## R2.3 必修 2 复测 — 多段自述不再丢内容

`_build_header` 返回 `summary_lines = ['第一段自我介绍：…', '第二段自我介绍：…']`；PDF 与 DOCX 抽取文本均同时含第一段与第二段。渲染样张确认两行依次排布、与联系方式之间有间距。

## R2.4 前端两项复测（真实浏览器）

- Toast 位置：`.toast-container` 实测 `y=80`，顶栏角标 `.topbar-badge` 占 `y=17.5~53.5`，**纵向零重叠**（上轮是压住角标）。
- 简历生成页空状态：`.empty-state` 存在，文案「选择目标岗位后点击「生成」，系统将基于您的履历和岗位要求生成定制简历草稿 / 生成的草稿可编辑、审阅、导出 DOCX/PDF」。
- console error **0 条**。

## R2.5 剩余观感建议（不阻塞）

1. **同段落内粗细混杂**（本轮引入）：`head_run.bold = bool(entry.details)` 是"有要点才加粗"，于是教育背景第一条「南方医科大学 · 硕士 · 内科学」粗体、第二条「中山大学 · 学士 · 临床医学」细体；论文成果与技能能力整行细体，条目主行看起来像正文。建议改为：**主行一律加粗以保持层级**，只对"整句话型"条目（`section_id == "target"`，或无日期且字数超过阈值）用常规字重。
2. **空状态文案在窄容器里断词换行**：「…您的履历和岗 / 位要求生成定制简历草稿」断在词中。建议给 `.empty-state p` 设 `max-width: 34em` + `text-wrap: pretty`。
3. **PDF 会静默丢弃字体缺失的字形**：实测 fpdf2 对 U+200B、U+FEFF、`\t`、emoji（🏥）输出 "missing glyphs" 警告并丢弃。前三个不可见无影响，emoji 会在 PDF 里消失（DOCX 正常）。建议导出前把这类字符规范化（零宽/BOM 直接删、`\t` 转空格），emoji 保留原样但在日志里记一条。

## R2.6 仍待处理（与本轮无关）

- 岗位库三栏在 1440px 挤爆（既存结构问题，见上一轮 3.4）。
- `AGENTS.md` 的 uvicorn 启动命令需改为在 `backend/` 目录执行。
