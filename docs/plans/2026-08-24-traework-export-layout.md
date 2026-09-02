# 给 traework 的执行提示词 — 简历导出（DOCX / PDF）排版重做（2026-08-24）

> 你是 traework。当前导出的简历"根本看不了"，本文件给出已实测的缺陷清单 + 目标排版规格 + 可自动断言的门禁。项目总监（AI 审核）会对照本文件逐条验收。
> 与同日的《前端视觉系统升级》提示词**文件互不重叠**，可独立提交。建议**先做本任务**（属于阻断级可用性问题）。

## 0. 现状事实与缺陷证据（已实测，不要重新调研）

复现方法（我用的就是这套，你可以照做）：直接调 `export_docx` / `export_pdf` 渲染一份含 identity + 教育 + 工作 + 论文的草稿；DOCX 解 zip 读 `word/document.xml`；PDF 用已在依赖里的 `pymupdf` 抽文本、抽 block 坐标、渲染 PNG 目检。

相关文件：`backend/app/services/exporter.py`（255 行，唯一渲染器）、导出端点 `backend/app/main.py:455-503`、草稿生成 `backend/app/services/resume.py`、前端下载 `frontend/src/pages/ResumePage.tsx` + `frontend/src/lib/api.ts`。

### PDF 侧（fpdf2）

| 编号 | 缺陷 | 证据 / 根因 |
|---|---|---|
| **D1** | **联系方式行与个人简介行整行丢失**（最严重，属数据丢失） | PyMuPDF 抽取第 1 页只有「张三」一个 block，y=52.6→102.8 之间是空白。根因：fpdf2 的 `multi_cell` 默认 `new_x=XPos.RIGHT`，姓名那次 `multi_cell` 结束后光标 x 停在右边距；紧接着的 `pdf.multi_cell(pdf.epw, 6, line, align="C")`（exporter.py:227）从右边距起、宽度又是整个 epw，整段被画到纸面之外，但仍占用垂直空间 |
| **D2** | 换行行被两端拉伸，中文条目出现巨大空隙 | fpdf2 `multi_cell` 的默认 `align` 是 **J（两端对齐）**。渲染图里「南方医科大学 / 硕士 / 内科学 / 2019-09」之间被撑成大空格 |
| **D3** | 项目符号无悬挂缩进 | 续行 block 的 `x0` 与「•」所在行相同（都是 31.2），条目在视觉上断成两段无关文字 |
| **D4** | 页边距是 fpdf2 默认 10mm | 正文 `x0≈31.2pt≈11mm`，行宽 ≈535pt ≈ 每行 40+ 汉字。中文简历应 20–25mm 边距 |
| **D5** | 没有粗体 | 只 `add_font("cjk", style="", ...)` 注册了 regular，层级全靠字号；一旦请求 `style="B"` 会直接抛异常 |
| **D6** | 段落标题溢出/落单 | 标题用 `pdf.cell(0, 8, section["title"])`（不换行、不裁剪），长标题会溢出；标题落在页尾时与条目分离，无 keep-with-next |
| **D7** | 无页码、无页脚 | 多页简历无法确认页序与总页数 |
| **D8** | 字体子集化告警 | 渲染时输出 `MERG NOT subset; don't know how to subset; dropped`（Windows 走 `msyh.ttc` 字体集合）；且 Linux 上若未装 noto-cjk 且未设 `PDF_FONT_PATH`，`export_pdf` 会 `RuntimeError` → 端点 500 |

### DOCX 侧（python-docx）

| 编号 | 缺陷 | 证据 / 根因 |
|---|---|---|
| **D9** | **纸张是 Letter 不是 A4** | `word/document.xml` 的 `<w:pgSz w:w="12240" w:h="15840"/>`（8.5×11 英寸）+ `<w:pgMar w:left="1800" w:right="1800"/>`（1.25 英寸）。国内投递/打印必须 A4（11906×16838 twips） |
| **D10** | 全文只有两种样式，层级塌平 | `document.xml` 里 `pStyle` 只出现 `Heading1` 与 `ListBullet`：教育、工作、论文、技能全部是同一层级的项目符号，没有「机构 — 角色 — 时间」三段式、没有右对齐日期。且 `Heading1` 沿用 Word 默认主题（Calibri Light + 主题蓝），中文走字体回退，与正文 `Microsoft YaHei`（exporter.py:61-71 只改了 Normal 样式）不一致 |
| **D11** | 无排版控制 | 未设行距、段前段后、标题 keep-with-next、孤行控制；未写文档属性（标题/作者）；无段落分隔线 |
| **D12** | 文件名无意义 | 后端 `resume-{draft_id}.docx`，前端另存为 `resume-3-application.docx`；HR 收到一堆同名文件。`Content-Disposition` 也没有 RFC 5987 `filename*`，中文名无法安全传递 |

## 1. 目标

**只改渲染，不改内容**：把两个导出格式重做成"可以直接投三甲医院 HR"的版式，且 DOCX 与 PDF 观感一致。

## 2. 任务 A — 抽出共享排版模型（exporter.py 内部重构）

在 `exporter.py` 内新增一层与格式无关的中间表示（不新增文件也可，但必须是独立函数/dataclass，可被单测直接调用）：

```
ResumeDoc
├── header: {name, contact_lines: list[str], summary: str | None}
└── blocks: list[SectionBlock]
    └── SectionBlock: {title: str, entries: list[Entry]}
        └── Entry: {head: str, role: str | None, period: str | None, details: list[str], raw: str}
```

**条目解析契约**（严格按 `resume.py:_format_profile_item` 的真实产出格式，不要凭想象）：

- 生成侧格式为：`head1 / head2 / ... / 日期段：详情1；详情2`
  - head 各段用 `" / "` 连接（`ITEM_HEAD_FIELDS`，如教育 = school/degree/major）；
  - 日期段是 head 的**最后一段**，由 `_date_range` 产出，形如 `2019-09-2022-06` 或单侧 `2019-09`（可能不存在）；
  - 详情在**第一个 `：` 之后**，用 `"；"` 连接（来自 `highlights` / `skills`）；
  - 有些条目没有 head，只有详情；有些是兜底的整段散文（无分隔符）。
- 解析规则：先按第一个 `：` 切 head/details（identity 段不参与此解析，因为联系方式本身含 `：`）；head 按 `" / "` 切分；若最后一段匹配日期正则（`^\d{4}([-./]\d{1,2})?(-\d{4}([-./]\d{1,2})?)?$` 之类）则视为 period，其余首段为 `head`、次段为 `role`。
- **无损红线**：解析后渲染的所有文本片段拼接（去掉分隔符与空白）必须与原 `text` 去分隔符后**完全一致**；写一个纯函数 `assert_lossless(raw, entry)` 供测试断言。任何解析不确定的条目**一律回退为整行渲染**，禁止丢字、禁止改写、禁止补词。
- 日期显示可以美化为 `2019.09 – 2022.06`（仅分隔符替换，数字一字不改）。

## 3. 任务 B — 版式规格（DOCX 与 PDF 必须一致）

| 项目 | 规格 |
|---|---|
| 纸张 | A4（DOCX：`section.page_width = Mm(210)` / `page_height = Mm(297)`；PDF：fpdf2 默认 A4，显式声明） |
| 页边距 | 上下 20mm，左右 22mm，两个格式一致 |
| 字体 | 中文：`Microsoft YaHei` → `Noto Sans SC` → `PingFang SC` 链；DOCX 必须同时设置 `ascii` / `hAnsi` / `eastAsia`（含 Heading 样式，不能只改 Normal）；PDF 必须注册 **regular + bold 两个字面**（Windows `msyh.ttc` / `msyhbd.ttc`，Linux `NotoSansCJKsc-Regular/Bold`）；找不到 bold 时降级用 regular 并 `logger.warning`，**不得抛错** |
| 姓名 | 20pt 加粗居中，段后 4pt |
| 联系方式 | 9.5pt 居中，`--muted` 灰（DOCX 用 `RGBColor(0x66,0x71,0x6D)`），多项用 ` ｜ ` 保持原样 |
| 个人简介 | 10pt，两端不拉伸（PDF 用 `align="L"`），行距 1.4 |
| 段落标题 | 12pt 加粗 + 下方 0.75pt 细线（DOCX：段落下边框；PDF：`pdf.line()`），段前 10pt / 段后 4pt，**keep-with-next** |
| 条目主行 | 10.5pt；`head` 加粗，`role` 常规，二者用 ` · ` 或 ` — ` 分隔；`period` 9.5pt **右对齐同一行**（DOCX 用右制表位 `tab_stops.add_tab_stop(Cm(17), WD_TAB_ALIGNMENT.RIGHT)`；PDF 用先量 `get_string_width` 再在右边距处绘制） |
| 条目详情 | 10pt，短横「– 」+ **悬挂缩进**（DOCX：`paragraph_format.left_indent` + `first_line_indent` 负值；PDF：手动量 bullet 宽度，续行从缩进位起绘制），行距 1.35，条目间段后 4pt |
| 分页 | PDF 渲染段落标题前预估「标题 + 首条目」高度，不足则先 `add_page()`（避免标题落单）；DOCX 用 `keep_with_next` / `keep_together` |
| 页码 | PDF：页脚居中「第 X 页 / 共 Y 页」（`footer()` + `{nb}` + `alias_nb_pages()`）。DOCX：页脚同格式（需手写 `PAGE`/`NUMPAGES` field XML；若你判断风险高可只做 PDF，但必须在报告中明确说明取舍） |
| 文档属性 | DOCX `core_properties.title = "{姓名} 简历"`、`author = 姓名`（姓名缺失则用草稿 title） |
| 诊断附录 | 结构与固定文案 **保持不变**：`匹配分析附录` / `已满足` / `未满足` / `用户手动添加，无档案证据`（现有测试断言这些字符串），仅套用新版式 |

## 4. 任务 C — 文件名（后端 + 前端）

- 后端导出端点：文件名改为 `{姓名}-{岗位}-简历-{YYYYMMDD}.{ext}`；姓名取 identity 首项、岗位从 `draft["title"]`（形如「内科医师 定制简历」）里取；任一缺失则回退现有 `resume-{draft_id}.{ext}`。诊断版追加 `-诊断版`。
- `Content-Disposition` 同时给两段：ASCII 回退名 + `filename*=UTF-8''{percent-encoded}`（用 `urllib.parse.quote`）。
- 前端 `frontend/src/lib/api.ts` 的 `exportResume` 需要把响应头文件名带出来（返回 `{blob, filename}` 或额外返回 headers），`ResumePage.tsx` 的 `downloadBlob` 优先用服务端文件名，解析失败再回退现有 `resume-${draft.id}-${mode}.${format}`。
- 前端为「文件名解析」写纯函数 + 单测（`parseContentDispositionFilename`），覆盖：只有 `filename`、只有 `filename*`、两者都有、都没有、百分号编码中文。

## 5. 任务 D — 可自动断言的排版测试（这是本任务的核心门禁）

新增 `backend/tests/test_export_layout.py`，**用已有依赖 pymupdf / python-docx 断言几何与结构**，不要写"看起来更好了"这种无法验证的测试：

PDF（`fitz.open(stream=...)`）：

1. **D1 回归锁**：第 1 页抽取文本必须包含联系方式里的电话、邮箱、以及个人简介的一段子串。
2. **无溢出**：所有 text block 的 `x0 >= 左边距 - 1pt` 且 `x1 <= 页宽 - 右边距 + 1pt`。
3. **纸张**：`page.rect.width/height` ≈ A4（595.28 × 841.89，容差 1pt）。
4. **悬挂缩进**：构造一条必然换行的长详情，断言其续行 block 的 `x0` 严格大于该条目主行的 `x0`。
5. **非两端对齐**：同一条目内换行行的字间距不被拉伸——用「最后一行之外的行，其 `x1` 不得等于右边距」或直接断言渲染调用使用了 `align="L"`（二者择一，写清理由）。
6. **页码**：多页样例（灌入足够条目）末页文本包含 `第 2 页` 与 `共 2 页`。
7. **中文**：包含中文的条目文本可被正确抽取（防字体/编码回归）。

DOCX（`Document(io.BytesIO(...))` + zip 读 XML）：

8. **A4**：`section.page_width == Mm(210)`（或 XML `w:pgSz w:w="11906"`）。
9. **eastAsia 字体**：Normal 与各 Heading 样式的 `rFonts` 均含 `w:eastAsia`。
10. **层级**：文档里出现的 `pStyle` 不再只有 `Heading1|ListBullet`；条目主行与详情行使用不同样式/缩进。
11. **keep_with_next**：段落标题段的 `w:keepNext` 存在。
12. **文档属性**：`core_properties.title` 非空。
13. **无损**：把草稿全部 item 文本去分隔符拼成一个大字符串，断言 DOCX 抽取文本（去分隔符）包含其中每一条 item 的核心内容（逐条 `assert in`）。

再新增预览脚本 `backend/scripts/export_preview.py`：构造一份覆盖全部 9 个 collection（education / experiences / projects / publications / certificates / skills / teaching / awards / languages）+ identity + gaps + evidence 的样例草稿，输出 `backend/tmp/preview-application.docx|pdf` 与 `preview-diagnostic.docx|pdf`，并用 pymupdf 把 PDF 每页渲成 PNG，便于人工目检（`backend/tmp/` 加入 `.gitignore`）。

## 6. 硬性约束（违反即打回）

- **真实性红线**：导出内容 = 草稿内容，一字不增不减；禁止任何"润色/改写/补全/精简"；禁止调用模型；禁止改动 `resume.py` 的生成逻辑与措辞。
- **零 DB schema 变更**；`include_appendix` 参数签名保持兼容（`export_docx(draft, include_appendix=False)` / `export_pdf(...)` 现有调用方式不变）。
- **零新增 Python 依赖**（python-docx / fpdf2 / pymupdf / pillow 都已在 `backend/pyproject.toml`）。
- **禁止改动**：`backend/app/services/matching/`、`adapters/`、`crawler.py`、`profile_import/`、`classifier.py`、`jd_structurer.py`、`analytics.py`、`scheduler.py`。本次只动 `exporter.py`、导出端点的文件名逻辑、前端导出/下载相关文件、新增测试与预览脚本。
- **既有导出行为不许退化**：`test_core_flow.py` 里 17 处导出相关断言必须继续通过（含 `%PDF` 前缀、未审阅 409+pending、override 绕过、空内容 422、渲染异常 500 兜底与日志、application 无附录 / diagnostic 有附录）。**不得为了让新排版通过而放宽任何既有断言**。
- **红线**：`backend/tests/test_matching_eval.py` 必须 **8 passed**（2026-08-24 实测基线）。
- `test_jd_structurer.py` 在 Windows 上有 env var 超长的**预存 flake**，与本任务无关，不要修、也不要计入门禁结论。

## 7. 验收标准（EARS，总监据此验收）

- WHEN 导出 PDF THEN 姓名、联系方式、个人简介**全部出现在纸面上**（D1 修复），无任何内容被画到页面外。
- WHEN 条目文本超过一行 THEN 续行悬挂缩进对齐正文起点，且不出现两端对齐造成的字间空隙。
- WHEN 导出任一格式 THEN 纸张为 A4、上下 20mm / 左右 22mm 边距、正文无溢出。
- WHEN 一份草稿同时导出 DOCX 与 PDF THEN 两份文件的段落顺序、条目层级、日期位置、字号层级在观感上一致。
- WHEN 段落标题出现在页面末尾 THEN 标题与其首个条目不被分页拆开。
- WHEN 简历超过一页 THEN PDF 每页有「第 X 页 / 共 Y 页」页脚。
- WHEN 用户下载文件 THEN 文件名形如 `张三-内科医师-简历-20260824.docx`（信息缺失时回退旧命名），中文不乱码。
- WHEN 以 `mode=diagnostic` 导出 THEN 附录仍含固定文案「匹配分析附录 / 已满足 / 未满足 / 用户手动添加，无档案证据」，且套用新版式。
- WHEN 运行门禁 THEN 后端全绿（除预存 flake）、`test_export_layout.py` 全部通过、前端三件套全绿。

## 8. 门禁（提交前必须全绿）

```powershell
uv run --project backend pytest -q
uv run --project backend python backend/scripts/export_preview.py
cd frontend; pnpm test; pnpm typecheck; pnpm build
```

- 后端：新增 `test_export_layout.py` 全通过；`test_matching_eval.py` 8 passed；其余用例零回归。
- 前端：基线 **14 文件 / 143 用例全绿**（2026-08-24 实测），新增文件名解析测试后用例数只增不减。
- 预览产物：报告里贴出 PDF 第 1 页渲图（若无截图能力，则贴 pymupdf 抽取的 block 坐标表，证明无溢出、悬挂缩进生效）。

## 9. 交付要求

- 提交信息：`fix(export): 简历 DOCX/PDF 排版重做（A4 + 结构化条目 + 悬挂缩进 + 页码 + 中文文件名）`。
- **保持未 push**（当前 `main` 领先 `origin/main` 7 个 commit），提交后报告，由总监审核。
- 报告需列出：D1–D12 逐条修复情况（含未修项及原因）、改动文件清单、新增测试清单与断言点、门禁结果（区分真实通过与预存 flake）、是否零 schema 变更 / 零新增依赖、无损性如何被测试保证。
