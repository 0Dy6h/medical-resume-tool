# 给 traework 的执行提示词 — 岗位库自适应布局 + 三条观感收尾（2026-08-24 第四轮）

> 你是 traework。上一轮（8c76a97）已验收通过并 push。本轮处理**唯一的阻断级可用性问题**：岗位库在常见笔记本屏幕上把内容裁掉看不见；顺带收掉三条上轮遗留的观感项与一条文档错误。
> 所有数字都是我用真实浏览器（chromium 1228，Playwright）在本地实测的，不要重新调研，直接照修。

---

## 0. 现状实测数据（岗位库 `/` 岗位库页，登录后测量）

嵌套的两层网格：`.jobs-layout { grid-template-columns: 280px 1fr }` 里面又套 `.split-page { grid-template-columns: minmax(620px, 1fr) 420px }`（`frontend/src/styles.css:2378` 与 `.split-page` 规则；`frontend/src/pages/JobsPage.tsx:223-226`、详情面板 `JobsPage.tsx:364`）。

| 视口宽 | 侧栏 | 订阅面板 | 表格区 | 详情面板宽 | 详情右边界 | 详情被切出屏幕 | 每列宽 | 首行岗位单元格高 |
|---|---|---|---|---|---|---|---|---|
| 1280 | 248 | 280 | 620 | 420 | **1628** | **是（切掉 348px）** | 73 | **301px** |
| 1440 | 248 | 280 | 620 | 420 | **1628** | **是（切掉 188px）** | 73 | **301px** |
| 1680 | 248 | 280 | 644 | 420 | 1652 | 否 | 76 | 301px |
| 1920 | 248 | 280 | 884 | 420 | 1892 | 否 | 106 | 201px |

单行表头高度参考：**37px**。

三条关键事实：

1. **内容是被裁掉、不是可以滚动看到**：`document.scrollWidth == clientWidth`（四档都是 0 横向溢出），因为 `.table-panel { overflow: hidden }`（styles.css:764）把溢出裁了。用户**没有任何办法**看到详情面板右侧那 188–348px（截止日期、状态操作区都在里面）。
2. **7 列平分宽度**：`table { table-layout: fixed }` 且**没有 `<colgroup>`**，7 列（岗位/机构/类别/学历/匹配度/状态/标签，`JobsPage.tsx:271-280`）各 73px ≈ 4 个汉字，于是岗位标题逐字竖排，一个单元格撑到 **301px 高**（正常 37px，等于 8 行）。
3. **可用门槛约 1660px**：只有 ≥1680 才放得下三区。1366 / 1440 / 1536 这些主流笔记本分辨率全部踩坑。

现有断点只有 `@media (max-width: 900px)` ×2、`@media (max-width: 1024px)` ×1，且 `body { min-width: 1120px }`（styles.css:78）。`.detail-panel` 也被 `ResumePage.tsx:469/649` 复用，改它的样式要顺带确认简历页不被搞坏。

## 1. 目标

岗位库在 **1280 / 1366 / 1440 / 1536 / 1680 / 1920** 六档宽度下都完整可用：任何内容都不被裁掉、岗位标题正常横排、详情可读、键盘可操作。

## 2. 任务 A — 岗位库自适应布局（本轮核心）

### A1 断点策略（写死，不要自创方案）

- **≥1600px**：保持三区并排 `订阅 260px | 表格 1fr | 详情 420px`（订阅从 280 收到 260），详情仍是右侧常驻列。
- **1200–1599px**：详情面板改为**右侧覆盖式抽屉**（不再占据网格列），表格独占主区；订阅保持左列 260px。
- **<1200px**：单列堆叠；订阅面板折叠成一行「我的订阅（N）」可展开块；详情仍是抽屉。
- 三档都必须满足 `document.scrollWidth == document.clientWidth`（零横向溢出）。

### A2 详情抽屉（新组件 `frontend/src/components/DetailDrawer.tsx`）

- 宽度 `min(480px, 92vw)`，右侧滑入：`transform: translateX(100%) → translateX(0)`，时长 `var(--dur-slow)`、缓动 `var(--ease-out)`；遮罩 `opacity 0 → 1`。
- `role="dialog"` + `aria-modal="true"` + `aria-labelledby` 指向抽屉标题；打开时锁 `body` 滚动，关闭后解锁。
- **Esc 关闭**；打开时焦点移入抽屉首个可聚焦元素；关闭后焦点**返还触发行**（复用 `CreateSubscriptionDialog.tsx` 上一轮已实现的 `triggerRef` 模式，不要另起一套）。
- `@media (prefers-reduced-motion: reduce)` 下取消滑入与遮罩渐变。
- 抽屉与常驻列**共用同一份详情 JSX**（抽出 `JobDetail` 子组件或渲染函数），禁止把详情内容复制成两份。

### A3 表格列宽（治本）

在 `JobsPage.tsx` 的 `<table>` 里加 `<colgroup>`，按下列比例分配（合计 100%）：

| 岗位 | 机构 | 类别 | 学历 | 匹配度 | 状态 | 标签 |
|---|---|---|---|---|---|---|
| 32% | 18% | 9% | 9% | 12% | 10% | 10% |

- 岗位标题：`word-break: normal`（禁止逐字断行）+ 两行截断（`display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden`），并给单元格加 `title={job.title}` 以便悬浮看全文。
- 机构列：单行截断 + `title`。
- 标签列：只渲染前 2 个标签，其余折叠成 `+N`（`+N` 的 `title` 列出剩余标签名）。这个「取前 2 个 + 计数」的逻辑写成纯函数并单测。
- 硬指标：**1440 视口下岗位列 ≥ 220px，首行岗位单元格高度 ≤ 111px（3 行）**。

### A4 订阅面板

- 宽度 280 → 260。
- `<1200px` 时折叠为「我的订阅（N）」标题行 + 展开区，展开用上一轮 B10 的 `grid-template-rows: 0fr → 1fr` 方案，不要用 `max-height` 估高。

## 3. 任务 B — 上轮遗留的三条观感项

| 编号 | 位置 | 修法 |
|---|---|---|
| B1 | `backend/app/services/exporter.py`（DOCX `head_run.bold` / PDF `main_style`） | 现在是"有要点才加粗"，导致同一段落内粗细混杂（教育背景第一条粗、第二条「中山大学 · 学士 · 临床医学」细；论文、技能整行细体）。改为：**条目主行一律加粗**，仅当 `section_id == "target"`、或（无 `period` 且主行字数 > 24）时用常规字重 |
| B2 | `frontend/src/styles.css` 的 `.empty-state p` | 加 `max-width: 34em; margin-inline: auto;`（可加 `text-wrap: pretty`），修掉「…您的履历和岗 / 位要求…」的断词换行 |
| B3 | `exporter.py` 新增文本规范化 | PDF 渲染前对文本做**不可见字符清理**：删除 `U+200B`（零宽空格）、`U+FEFF`（BOM）、`U+00AD`（软连字符）；`\t` 转单个空格；`U+00A0`/`U+3000` 转普通空格。emoji **保留原样**，但当 fpdf2 缺字形时 `logger.warning` 记一条（实测 🏥 会被静默丢弃）。规范化只处理这些字符，**禁止**顺手改写标点、全角半角或任何可见文字 |

B3 必须补测试：含 `U+200B` / `U+FEFF` / `\t` / emoji 的条目导出成功，且可见文字（去掉空白与分隔符后）完整出现在 DOCX 与 PDF 抽取文本中。

## 4. 任务 C — 文档修正

`AGENTS.md` 的 Commands 段：

- `uv run --project backend uvicorn app.main:app --host 127.0.0.1 --port 8000` 从仓库根目录执行会 `ModuleNotFoundError: No module named 'app'`（已实测）。改为在 `backend/` 目录执行：`cd backend; uv run --project . uvicorn app.main:app --host 127.0.0.1 --port 8000`。
- 补一句 SQLite 路径提示：数据库路径相对当前工作目录 —— 根目录启动用 `data/app.db`，`backend/` 目录启动用 `backend/data/app.db`，两者数据不通。

## 5. 可复跑的布局验收脚本（本轮必须交付）

新增 `scripts/measure_jobs_layout.py`（用 backend 已有的 playwright dev 依赖运行）：

- 本机 chromium 版本与 playwright 期望版本不一致，**必须显式指定**：`p.chromium.launch(executable_path=r"C:\Users\12035\AppData\Local\ms-playwright\chromium-1228\chrome-win64\chrome.exe")`（不指定会报 "Executable doesn't exist at …chromium_headless_shell-1223…"）。
- 脚本自己注册临时账号（如 `qa_layout_probe`）→ 进岗位库 → 逐档量测 → **结束时把该账号从 `backend/data/app.db` 删掉**（`users` 表 + 所有含 `user_id` 列的表），不要在库里留测试账号。
- 逐档断言并打印，任一不满足就 `exit 1`：

| 断言 | 阈值 |
|---|---|
| 零横向溢出 | `documentElement.scrollWidth == clientWidth`（1280/1366/1440/1536/1680/1920 六档） |
| 详情不被裁 | 常驻详情列或抽屉的 `getBoundingClientRect().right <= window.innerWidth` |
| 岗位列够宽 | 1440 档 `岗位` 列宽 ≥ 220px |
| 标题不竖排 | 1440 档首行岗位单元格高度 ≤ 111px |
| 抽屉可关 | 1440 档点开详情后按 Esc 抽屉消失，且焦点回到触发行 |

报告里贴出六档的实测数字表（与本文件第 0 节同格式），便于对比改造前后。

## 6. 硬性约束（违反即打回）

- **零新增依赖**：`frontend/package.json` 不许动（抽屉、动效、截断全用 CSS + React 实现，不许引入 UI/动画库）；后端不许加 Python 依赖（playwright 已在 dev 组）。
- **类名只增不删**：现有类名必须继续可用（`.detail-panel` 被 `ResumePage.tsx:469/649` 复用，改样式后必须回归确认简历页正常）。
- 沿用上一轮的设计 token（`--space-*`、`--radius-*`、`--dur-*`、`--ease-*`、`--shadow-*`），**不许再写魔法数字**；不许出现 `transition: all`；不许对 `width/height/top/left/margin/padding` 做过渡动画。
- `prefers-reduced-motion: reduce` 必须覆盖新增动效。
- 导出改动仅限 `exporter.py`；**禁止**触碰 `resume.py` 的生成逻辑与措辞、`matching/`、`adapters/`、`crawler.py`、`classifier.py`、`jd_structurer.py`、`analytics.py`、`scheduler.py`；零 DB schema 变更；导出内容一字不增不减（不可见字符清理不算内容改动，但要有测试证明可见文字无损）。
- 红线：`backend/tests/test_matching_eval.py` = **8 passed**；后端总数不得低于 **344 passed**；前端不得低于 **168 passed**。
- `test_jd_structurer.py` 在 Windows 有预存 flake，与本轮无关，不修也不计入结论。

## 7. 验收标准（EARS）

- WHEN 视口宽度为 1280 / 1366 / 1440 / 1536 THEN 岗位详情以抽屉呈现且完整可见，页面无横向溢出，无任何内容被 `overflow: hidden` 裁掉。
- WHEN 视口宽度 ≥1600 THEN 三区并排，详情右边界不超出视口。
- WHEN 岗位标题很长 THEN 标题横排、最多两行、超出以省略号收尾，悬浮可见全文；单元格高度不超过 3 行。
- WHEN 标签超过 2 个 THEN 只显示前 2 个并以 `+N` 折叠，`+N` 悬浮列出其余标签。
- WHEN 抽屉打开 THEN Esc 可关闭、焦点进入抽屉、关闭后焦点返还触发行；`prefers-reduced-motion` 下无滑入动画。
- WHEN 导出简历 THEN 同一段落内条目主行字重一致（仅求职目标类整句条目为常规字重）。
- WHEN 简历条目含零宽空格 / BOM / 制表符 / emoji THEN 导出成功且可见文字完整。
- WHEN 运行 `scripts/measure_jobs_layout.py` THEN 六档全部通过并打印数字表；脚本退出时数据库无残留测试账号。

## 8. 门禁（提交前必须全绿）

```powershell
uv run --project backend pytest -q
cd frontend; pnpm test; pnpm typecheck; pnpm build
# 布局验收（需先起两个服务）
cd backend; uv run --project . uvicorn app.main:app --host 127.0.0.1 --port 8000
cd frontend; pnpm dev
uv run --project backend python scripts/measure_jobs_layout.py
```

## 9. 交付要求

- 拆成两个提交：
  1. `fix(jobs): 岗位库自适应布局（列宽分配 + 详情抽屉 + 订阅折叠）`
  2. `polish(export): 条目主行字重统一 + 不可见字符规范化 + 空状态排版 + AGENTS.md 命令修正`
- 提交后**不要 push**，报告等我审。
- 报告需含：六档实测数字表（改造前 vs 改造后）、改动文件清单、新增纯函数与单测清单、门禁结果（区分真实通过与预存 flake）、是否零新增依赖 / 零 schema 变更、简历页 `.detail-panel` 复用处的回归确认、以及测试账号已清理的确认。
