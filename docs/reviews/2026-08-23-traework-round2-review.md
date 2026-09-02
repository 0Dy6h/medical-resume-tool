# traework 第二轮三切片评审 — 2026-08-23（f44e058 → 9eb998a → 5ace47e）

## 结论：通过（Approve，无 P0/P1 阻塞，无 minor 遗留）

PRD 4.4「用户修改措辞越界」诊断标记、PRD 4.3「导入解析失败」提示、上轮 minor 清理，三片全部按提示词落地。上一轮的 3 条 minor 已全部闭环。

## 实测门禁（本沙箱实际运行）

- 后端：`uv run --project backend pytest -q` → **295 passed**（45.4s；红线 test_matching_eval 全绿）
- 前端：`pnpm test` → **119 passed**（13 文件，新增 profileImport.test.ts 6 条 + resumeReview 增至 28 条）；`pnpm typecheck` clean；`pnpm build` 通过（289.56 kB / gzip 86.71 kB）
- 变更范围：9 文件，与声明一致，无夹带

## 切片 1 — 诊断版标记无档案证据条目（f44e058）

- `collect_unlinked_items`：跳过 7 个结构性区块 id + 标题「投递前需补充确认」，跳过 `decision == "remove"`，`str(profile_field_id or "").strip()` 为空即收集——与提示词口径逐条一致。
- **关键风险已规避**：identity/target/gaps 条目天然无 field_id，测试①用正常草稿的诊断版导出断言不含标记，证明无误报。
- 附录小节仅在 `_build_appendix_sections`（include_appendix=True 路径）追加，标题逐字「用户手动添加，无档案证据」；测试③断言应聘版导出不含该小节，投递版洁净性有守卫。
- exporter.py 纯增量：正文/身份行/字体/PDF 版式与既有附录小节零改动（对照 441e62b 的历史事故约束）。
- 前端 `isUnlinkedReviewItem` 与后端同规则；`flattenReviewItems` 已带 sectionTitle，标题排除在 UI 侧同样生效；警示标签复用 `status danger` 类。
- 测试：后端 2 个测试函数（纯函数排除矩阵 + 三场景导出集成）、前端 8 条单测。

## 切片 2 — 导入解析失败提示（9eb998a）

- `importExtractionEmpty`：集合全空 + review_items 空 + basics 无非空值 → true；unassigned_blocks 不影响判定（按 PRD「未提取到结构化信息」口径）。空白字符串 basics 也判为空，边界处理到位。
- 提示面板文案逐字「无法从该文件中提取结构化信息，请尝试手动输入或上传更清晰的文件」；面板内保留「未归类原文」折叠区（PRD 要求未分配文本不丢弃）。
- 硬失败路径：后端 detail 作为次要说明文字保留在面板内，未被吞掉；同时 `setPreview(null)` 避免残留空预览。
- 「手动录入」按钮经 `basicFormRef` 滚动到基本信息表单（ref 已确认挂在 `<section className="panel form-panel" ref={basicFormRef}>`），未新建页面/路由。
- 后端与 API 语义零改动，符合本切片「只改前端」的约定。
- 既有 toast 分支加了 `&& !importExtractionEmpty(result)` 守卫，避免面板与 toast 重复提示。

## 切片 3 — minor 清理（5ace47e）

- api.ts 缩进恢复为 2 空格风格，纯格式、零行为变更。
- `.history-item` / `-active` / `-title` / `-meta` / `-time` 与 `.warning-banner` 入 styles.css，两个页面内联 style 全部移除。
- 额外收益：原内联样式里的硬编码色值（#3b82f6 / #e5e7eb / #eff6ff / #6b7280）替换为主题变量 `--blue/--blue-soft/--line/--muted`，已核实变量均存在——比原实现更贴合主题体系。

## 未 touch（核实属实）

matching/、adapters/、crawler.py、jd_structurer.py、backend profile_import/ 零触碰；零 DB schema 变更；无新增依赖；exporter.py 仅新增附录逻辑。

## 上轮 minor 闭环情况

| 上轮 minor | 状态 |
|---|---|
| api.ts 缩进损坏 | 已修（切片 3） |
| .history-item 未定义、靠内联样式 | 已修（切片 3，含色值主题化） |
| 历史版本面板无草稿时整体隐藏 | 保留现状（提示词未要求空态，可接受） |

## 下一轮建议

PRD 4.3「未归类原文手动归类到档案字段」（业务逻辑段明确要求用户可把未分配文本归类到正确字段）——需按各 collection schema 设计预填表单，避免把原文塞进 name 字段产生低质数据。
