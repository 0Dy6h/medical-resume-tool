# traework 提示词（2026-08-22）

两份：P1 必改（push 前）+ 下一切片建议（4.3 模式选择）。直接复制给 traework。

---

## 提示词 1 — P1 必改：恢复 `_is_experience` 互斥保护（push 前）

任务：修复导入路由中 `_is_experience` 被误删的互斥保护。

文件：`backend/app/services/profile_import/extractors.py`

当前 `_is_experience`（约 218 行）被改成了：

```python
def _is_experience(text: str, block: DocumentBlock) -> bool:
    if block.section_hint == "experiences":
        return True
    return _has_any(text, _ORG_SUFFIXES) and _has_any(text, _ROLE_SUFFIXES)
```

请恢复被删掉的互斥保护，改回：

```python
def _is_experience(text: str, block: DocumentBlock) -> bool:
    if block.section_hint == "experiences":
        return True
    if _is_education(text, block) or _is_project(text, block):
        return False
    return _has_any(text, _ORG_SUFFIXES) and _has_any(text, _ROLE_SUFFIXES)
```

原因：现在 `strong_match` 会拉高 experience 的置信度，而 `PRIMARY_PRIORITY` 里 `experiences(0)` 优先于 `projects(2)`。去掉保护后，"北京某三甲医院 科研项目 负责人"这类同时命中 project（`项目` 命中 `_PROJECT_HINT`）和 experience（`医院`+`负责人` 命中 org+role，见 legacy.py `_ROLE_SUFFIXES` 含"负责人"）的行，会在置信度并列时被误路由到 `experiences`。恢复保护后仍是每 block 至多 1 个 primary，不破坏单路由。

回归用例（加进 `backend/tests/test_extractors.py`）：

```python
def test_project_block_not_misrouted_to_experience():
    lines = ["2021.01-2023.12 北京某三甲医院 科研项目 负责人"]
    contract = build_profile_contract(lines, [])
    assert len(contract.projects) == 1
    assert contract.experiences == []
```

该用例在当前（保护被删）代码下应失败、修复后应通过。

门禁：

```
cd backend && uv run --project backend pytest -q
```

重点：`test_matching_eval.py` 14/14 不动；现有 fixture 行为不变；本提交领先 origin/main，改完 git commit（不 push）。

---

## 提示词 2 — 下一切片建议：4.3 模式选择（应届生/职场人）

任务：实现档案「应届生/职场人」模式选择与展示优先级（PRD 4.3，`medical-job-prd.html:818-952`）。

背景：导入侧路由（basics 提取 + 单最佳路由）刚完成并通过审核（仅余 P1 待修）。下一步做 4.3 里尚未实现的「模式选择」：首次进入档案页提示选 `fresh_grad` / `experienced`；不同模式调整各区块展示顺序与折叠态（应届生：教育/科研/实习优先，工作折叠；职场人：工作/成果优先，教育退居次要）；切换模式只重排展示，不删任何数据。

交付：

- 后端 `backend/app/schemas.py` 的 `Profile` 增加 `mode: str = "experienced"`（若已有则复用），取值约束 `fresh_grad | experienced`；如需要，新增 `GET/PUT /api/profile/mode` 或并入现有 profile 端点保存 mode。
- 前端 `frontend/src/pages/ProfilePage.tsx`：模式选择栏（当前模式标签 + 切换按钮）；按 mode 计算区块顺序与默认折叠态（用常量 `MODE_LAYOUT = { fresh_grad: [...], experienced: [...] }`）；切换仅改展示，不动数据。
- 后端加单测：默认 `experienced`；set mode 后 get 返回一致；切换不改变任何档案条目数量。
- 前端在 `importMerge.test.ts` 或新建测试覆盖「切换模式重排展示顺序、数据条目数不变」。

硬性约束：

- 零 DB schema 变更（仅代码/枚举/默认值）。
- 不碰 `matching/`、`adapters/`、`crawler.py`、`exporter.py`、`jd_structurer.py`。
- 不编造；模式仅影响展示，绝不因切换删除/隐藏真实数据。
- 保持 `test_matching_eval` 14/14 红线。

门禁：

```
cd backend && uv run --project backend pytest -q
cd ../frontend && pnpm test && pnpm typecheck && pnpm build
```

完成后 git commit（不 push），交总监审核。

> 注：模块 2（4.1 职位情报中心）、4.2 详情匹配、4.4 简历草稿、4.5 导出、4.6 质量监控 亦可作后续切片。若你想先做别的模块，替换提示词 2 即可。
