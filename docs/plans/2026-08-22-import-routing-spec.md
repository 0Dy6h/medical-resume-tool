# 导入侧路由重构技术方案（Spec / 执行契约）

> 生成日期：2026-08-22
> 基于：PRD v1.0（2026-07-29，模块 4.3）+ 2026-07-26 end-of-day 交接「推荐下一步：导入侧路由」
> 执行方：traework ｜ 审核方：项目总监（大湾区靓仔）
> 状态：待执行

---

## 0. 事实依据（已核实，非推断）

- 最新进度见 `docs/handoffs/2026-07-26-end-of-day.md`：main 已修红，中文匹配重建（184 后端测试通过），**明确把"导入侧路由（basics 提取 + 停止 experience→project/publication 扇出）"列为下一步推荐**，且标注"完全可离线验证"。
- PRD 模块 4.3「用户档案管理」明确要求：导入流程"展示预览界面（原始文本+提取字段并排对照）→ 用户确认或修正 → 保存"；基本信息含 `name/phone/email`（字段规则表 profile.name / profile.phone / profile.education[].school 等）；"未成功分配的文本以待审核形式保留"。
- 当前实现：`backend/app/services/profile_import/` 整包已存在（`pipeline.py` / `extractors.py` / `blocks.py` / `scoring.py` / `facts.py` / `legacy.py` / `extraction.py` / `adapter.py` / `normalization.py`）。
- 关键缺口两处，均在 `profile_import` 包内：
  1. **扇出**：`extractors._facts_for_block()` 对单个 block 独立判断所有 `_is_*` 并逐个 `facts.append()`，导致单一事实被复制进多个 collection。
  2. **basics 缺失**：`ProfileImportContract`（facts.py:39）和 `COLLECTIONS`（extractors.py:31）均无 `basics`；`schemas.Profile` 已有 `basics: BasicInfo`（schemas.py:199，含 name/phone/email），但导入从不填充它 → name/phone/email 只能落 `unassigned_blocks`。

---

## 1. 范围锁定（In / Out of Scope）

### 本次必须做（P0）
- **A. 单最佳路由**：消除扇出——每个 block 至多产出 1 个 primary fact。
- **B. basics 提取**：从导入文本识别 name/phone/email，写入 `contract.basics`，进入预览与确认流程。

### 明确不做（Out of Scope，避免范围蔓延）
- LLM `jd_structurer` / grounded rewriting（无 API key，且离线不可验证，已在 2026-07-26 标注 deferred）。
- major / certificate / age 等其他 gates（degree gate 已完成）。
- 爬虫、适配器、exporter、matching/ 目录——**一律不碰**。
- DB schema 变更——**零 schema 变更**，纯代码 + 测试。

---

## 2. 技术方案 A：单最佳路由（消除扇出）

### 2.1 设计
每个 `DocumentBlock` 产出 **至多 1 个 primary fact** = 所有候选 collection 中置信度最高者（确定性 tie-break 见 2.3）；**skills 作为加法轴共存**（一个 block 可以是 experience 且带 skills，这是合理而非扇出）。

### 2.2 改造点（仅 `extractors.py`）
- 改写 `_facts_for_block(block) -> tuple[ExtractedFact | None, list[ExtractedFact]]`：
  - 计算 primary 候选：`education / experiences / projects / publications / teaching / awards / certificates / languages`（保留现有各 `_build_*` 与 `_scored_fact` 逻辑不变）。
  - 取 `confidence` 最大者作为唯一 primary；并列时按 `PRIMARY_PRIORITY` 顺序定胜负。
  - skills 仍按现有 `extract_skills` 加法产出，不计入 primary 竞争。
- `extract_facts(blocks)` 改为：对每个 block 调 `_facts_for_block`，收集 `(primary, skills)`，primary 为 `None` 时跳过（仍可能产 skills）。
- `pipeline.build_profile_contract` 无需大改：`facts` 列表现在天然每 block ≤1 条 primary + N 条 skills；现有 `_append_fact` / review / unassigned 逻辑照常。

### 2.3 优先级常量（写在 `extractors.py` 顶部）
```python
# 单一 block 命中多 collection 时，确定性定胜负（经验优先级，非评分）
PRIMARY_PRIORITY: tuple[str, ...] = (
    "experiences",   # 含 org+role 的工作块最具体
    "education",
    "projects",
    "publications",
    "teaching",
    "awards",
    "certificates",
    "languages",
)
```

### 2.4 回归测试（新增，放 `test_extractors.py`）
构造一个**明确多实体单行** block，断言只路由到 1 个 primary：
```python
def test_multi_entity_block_routes_to_single_primary():
    lines = [
        "2020.09-2023.06 北京某三甲医院 主治医师",
        "负责国家自然科学基金面上项目，发表SCI论文3篇",
    ]
    contract = build_profile_contract(lines, [])
    # 扇出修复：整段只产生 1 条 primary（experience），不得出现 project/publication
    assert len(contract.experiences) == 1
    assert contract.projects == []
    assert contract.publications == []
```
> 该用例专门覆盖此前 CI 漏掉的扇出场景。

---

## 3. 技术方案 B：basics 提取

### 3.1 数据结构（facts.py）
`ProfileImportContract` 新增字段（单对象，非数组）：
```python
basics: dict[str, str] = field(default_factory=dict)  # {name?, phone?, email?}
```
`to_dict()` 同步加入 `basics`。

### 3.2 schemas.py
`ProfileImportOut`（schemas.py:436）新增：
```python
basics: dict[str, str] = Field(default_factory=dict)
```

### 3.3 提取逻辑（新增 `extractors.build_basics(blocks)` 或独立小函数）
扫描所有 block 文本，**保守**提取，只填高置信字段，绝不编造：
- **phone**：`re.compile(r"1[3-9]\d{9}")`
- **email**：`re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")`
- **name**：启发式二选一
  1. 显式标签：`(?:姓名|名字|称谓)[:：]\s*(\S{2,4})`
  2. 顶部独立行：位于文档前 3 个 block、纯 2–4 个汉字、非板块标题别名、不含 org/role/education 后缀、非纯数字年份。
  - 任一命中才填；都不命中则 `name` 留空（用户手动补）。

### 3.4 装配（pipeline.build_profile_contract）
- 调用 `build_basics(blocks)` 得 `basics` 与 `basics_source_texts`（被 basics 消耗的原文集合）。
- `contract.basics = basics`。
- unassigned 循环排除 `basics_source_texts`，避免 phone/email/name 行污染 `unassigned_blocks`。

### 3.5 前端（3 个触点）
- `frontend/src/types.ts`：`ProfileImportResult` 增加 `basics?: Record<string, string>`；`Profile.basics` 已是 `Record<string, unknown>`，兼容。
- `frontend/src/lib/importMerge.ts`：`mergeImportSelection` 当前按 `collections` 数组逐集合 push。**basics 是单对象不是数组**，需单独处理：确认时 `next.basics = { ...next.basics, ...selectedBasics }`（对象合并，不进数组循环）。调用方传入的 `collections` 不含 `basics`。
- 导入预览页（ProfilePage 导入区）：新增一个 basics 卡片，渲染 name/phone/email 为**预填可编辑输入框**，随其他条目一起确认。

---

## 4. 验收标准（EARS 格式，QA / 审核据此判定）

| 编号 | 功能 | EARS 验收标准 | 优先级 |
|------|------|---------------|--------|
| AC-01 | 单最佳路由 | When 一个 block 同时命中 experience 与 project 与 publication，系统**必须**只写入置信度最高的 1 个 collection | P0 |
| AC-02 | 扇出回归 | If 上述多实体 block 被导入，系统**必须**使其余两个 collection 对应该 block 为空 | P0 |
| AC-03 | basics 提取 | When 导入文本含 `1[3-9]\d{9}` 或标准邮箱，系统**必须**将其写入 `contract.basics` 且不出现在 `unassigned_blocks` | P0 |
| AC-04 | basics 不编造 | If 文本中无姓名信号，系统**必须**使 `basics.name` 为空字符串，不得臆造 | P0 |
| AC-05 | 兼容性 | While 现有 fixture（plain_unsectioned_resume.txt）导入，系统**应该**保持 education/experiences/projects/certificates/languages/skills 各自恰好 1 条且 unassigned 为空 | P1 |
| AC-06 | 前端合并 | When 用户在预览中确认 basics，系统**必须**将其合并进 `profile.basics` 而非新增数组项 | P1 |

---

## 5. 测试门禁（traework 交付前必须全绿）

后端：
```bash
cd backend
uv run --project backend pytest -q
# 硬性：全部通过；特别关注——
#   test_matching_eval.py       14/14 top-1、0 错源、0 误报（不可动）
#   test_extractors.py          既有用例 + 新增 AC-01/AC-02 回归
#   test_profile_import.py      端点用例（含 unsectioned 纯文本）
#   test_profile_contract.py    保存/加载契约
```
前端：
```bash
cd frontend
pnpm test && pnpm typecheck && pnpm build
```

---

## 6. 项目总监审核清单（RoleVerdict —— 我审 traework 产物时使用）

> 格式：`verdict: pass | fail`；fail 时列 `blocking` 证据。

1. **无扇出**：AC-01/AC-02 回归用例存在且通过；代码 review 确认 `_facts_for_block` 每 block ≤1 primary。
2. **basics 上线**：`ProfileImportOut` 与 `ProfileImportContract.to_dict()` 均含 `basics`；端点响应能返回 phone/email。
3. **不编造**：`build_basics` 对缺姓名输入返回空 name（抽查 3 个无姓名样本）。
4. **测试全绿**：后端 `pytest -q` 全过（含 test_matching_eval 14/14），前端 `pnpm test/typecheck/build` 通过。
5. **P0 合规**：前端新增 UI 无 emoji 作图标（用现有 SVG/文本标签）；无硬编码颜色；无"Lorem/Welcome"占位。
6. **范围受控**：diff 仅触及 `profile_import/`（extractors/pipeline/facts）+ schemas.py + 前端 3 触点；**未触碰** matching/、adapters/、crawler.py、exporter.py。
7. **无破坏性**：`legacy_to_contract` 与现有导入端点契约向后兼容；无 DB migration。

---

## 7. 端到端验证步骤（交付后我手动复验）

```bash
# 1. 启动后端
uv run --project backend uvicorn app.main:app --host 127.0.0.1 --port 8000 &
# 2. 注册并取 token
TOKEN=$(curl -s -X POST localhost:8000/api/auth/register -H 'Content-Type: application/json' \
  -d '{"username":"reviewer","password":"secret123"}' | python -c "import sys,json;print(json.load(sys.stdin)['token'])")
# 3. 上传含 basics + 多实体单行的简历文本
printf '张三\n电话：13800138000\n邮箱：zhangsan@example.com\n2020.09-2023.06 北京某三甲医院 主治医师 负责国家自然科学基金项目，发表SCI论文3篇\n' > /tmp/resume.txt
curl -s -X POST localhost:8000/api/profile/import \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/tmp/resume.txt;type=text/plain" | python -m json.tool
# 断言：basics 含 name/phone/email；experiences 为 1；projects/publications 为空
```

---

## 8. 风险与回滚

- **零 schema 变更**：仅代码 + 测试，git 可整段回退（`git revert` 或分支对比）。
- **既有 fixture 风险**：AC-05 约束现有 `plain_unsectioned_resume.txt` 行为不变；若某既有断言因单最佳路由而失效，traework 必须**同步更新该断言并说明原因**，不得静默删除。
- **回滚触发**：任一 P0 验收（AC-01~04）未达成 → `verdict: fail`，退回重做，最多 3 轮。
