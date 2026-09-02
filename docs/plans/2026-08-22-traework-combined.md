# traework 合并提示词（2026-08-22）

一次执行两项互相关工作，均在 `D:\螃蟹's Projects\螃蟹的简历撰写工具` 本地 FastAPI+React 项目内。先读 `docs/plans/2026-08-22-import-routing-spec.md`（已落地方案的背景）与 `docs/reviews/2026-08-22-traework-import-routing-review.md`（上轮审核结论），再动手。

---

## 任务 A — P1 必改：恢复 `_is_experience` 互斥保护（push 阻塞项，先做）

文件：`backend/app/services/profile_import/extractors.py`

当前 `_is_experience`（约 218 行）被误删了互斥保护，改成：

```python
def _is_experience(text: str, block: DocumentBlock) -> bool:
    if block.section_hint == "experiences":
        return True
    return _has_any(text, _ORG_SUFFIXES) and _has_any(text, _ROLE_SUFFIXES)
```

恢复为：

```python
def _is_experience(text: str, block: DocumentBlock) -> bool:
    if block.section_hint == "experiences":
        return True
    if _is_education(text, block) or _is_project(text, block):
        return False
    return _has_any(text, _ORG_SUFFIXES) and _has_any(text, _ROLE_SUFFIXES)
```

原因：现在 `strong_match` 会拉高 experience 置信度，而 `PRIMARY_PRIORITY` 里 `experiences(0)` 优先于 `projects(2)`。去掉保护后，"北京某三甲医院 科研项目 负责人"同时命中 project（`项目` 命中 `_PROJECT_HINT`）和 experience（`医院`+`负责人` 命中 org+role，见 legacy.py `_ROLE_SUFFIXES` 含"负责人"），会在置信度并列时被误路由到 experiences。恢复后仍是每 block 至多 1 个 primary，不破坏单路由。

回归用例（加进 `backend/tests/test_extractors.py`）：

```python
def test_project_block_not_misrouted_to_experience():
    lines = ["2021.01-2023.12 北京某三甲医院 科研项目 负责人"]
    contract = build_profile_contract(lines, [])
    assert len(contract.projects) == 1
    assert contract.experiences == []
```

该用例在当前（保护被删）代码下应失败、修复后应通过。

---

## 任务 B — 4.3 模式选择：应届生/职场人（任务 A 修复后紧接着做）

实现档案「应届生/职场人」模式选择与展示优先级。PRD 见 `medical-job-prd/medical-job-prd.html` 模块 4.3（约 818–952 行）。

背景：导入侧路由（basics 提取 + 单最佳路由）已落地并通过上轮审核，仅余任务 A 待修。本任务做 4.3 里尚未实现的「模式选择」：首次进入档案页提示选 `fresh_grad` / `experienced`；不同模式调整各区块展示顺序与默认折叠态（应届生：教育/科研/实习优先，工作折叠；职场人：工作/成果优先，教育退居次要）；切换模式只重排展示，不删任何数据。

交付：

1. 后端 `backend/app/schemas.py`：在 `Profile` 增加 `mode: str = "experienced"`（若已有则复用），取值约束 `fresh_grad | experienced`。
2. 持久化：如档案已有灵活字段/JSON(meta)列，把 mode 存进它，**不要** ALTER TABLE 新增列、不要做 DB migration（零 schema 变更红线）。如需端点，新增 `GET/PUT /api/profile/mode` 或并入现有 profile 端点。
3. 前端 `frontend/src/pages/ProfilePage.tsx`：模式选择栏（当前模式标签 + 切换按钮）；用常量 `MODE_LAYOUT = { fresh_grad: [...sectionKeys], experienced: [...sectionKeys] }` 控制区块顺序与默认折叠态；切换仅改展示顺序/折叠，绝不动数据。
4. 后端单测：默认 `experienced`；set 后 get 返回一致；切换不改变任何档案条目数量。
5. 前端测试（`importMerge.test.ts` 或新建）：覆盖「切换模式重排展示顺序、数据条目数不变」。

---

## 共用硬性约束（违反即退回）

- 零 DB schema 变更（仅代码/枚举/默认值/灵活字段内存储）。
- 不得碰 `matching/`、`adapters/`、`crawler.py`、`exporter.py`、LLM `jd_structurer.py`（无 key 且离线不可验）。
- 不得编造任何事实；模式仅影响展示，绝不因切换删除/隐藏真实数据。
- 改动范围：任务 A 仅 `extractors.py` + 一个测试；任务 B 仅 `schemas.py` + profile 端点（如加）+ `ProfilePage.tsx` + 测试。不得越界。
- 现有 fixture `backend/tests/fixtures/profile_import/plain_unsectioned_resume.txt` 行为必须保持（education/experiences/projects/certificates/languages/skills 各 1 条、unassigned 为空）。

## 交付前门禁（必须全绿）

```
cd backend && uv run --project backend pytest -q
cd ../frontend && pnpm test && pnpm typecheck && pnpm build
```

重点守护：`test_matching_eval.py` 必须 14/14 top-1、0 错源、0 误报——这条红线不可动。另：`test_jd_structurer.py` 在 Windows 上有个超长环境变量（>32767 字符）导致的环境报错，与本任务无关，无需修复。

## 完成后

- 用 `cd backend && uv run --project backend uvicorn app.main:app --host 127.0.0.1 --port 8000` 起服务，注册取 token，验证：(a) 上传"北京某三甲医院 科研项目 负责人"单行 → `projects` 为 1、`experiences` 为空（任务 A）；(b) 切换 fresh_grad/experienced → 区块顺序变化、条目数不变（任务 B）。
- 把改动 git commit（**不要 push**）。当前已领先 origin/main 1 个 commit，本次提交接在其后。

项目总监会按 Spec/审核结论复审，重点看：P1 回归用例通过、误路由消除、mode 仅改展示不删数据、`test_matching_eval` 红线、改动是否越界。
