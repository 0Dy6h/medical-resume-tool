# 评审记录：导入侧路由重构（commit b170e5f）

审核人：项目总监（MvpDevExpertTeam）｜审核日期：2026-08-22
对照 Spec：`docs/plans/2026-08-22-import-routing-spec.md`（第 6 节 7 点清单）

## 结论：有条件通过（Approve with 1 项必改 + 1 项建议）

核心交付 A（消除扇出）与 B（basics 提取）均按 Spec 正确落地，门禁全绿。
但发现一处**超出 Spec 的改动**引入潜在误路由，需在 push/merge 前修复。

---

## 七点清单逐项核对

| # | 审核点 | 结果 | 证据 |
|---|--------|------|------|
| 1 | 扇出回归用例通过（单一多实体 block 只产 1 条 primary） | PASS | `test_multi_entity_block_routes_to_single_primary`：experiences==1, projects==[], publications==[] |
| 2 | `ProfileImportOut` 真能返回 basics | PASS | `schemas.py` + `facts.py` + `to_dict()` 均加 `basics` |
| 3 | 缺姓名信号时 `basics.name` 为空、不臆造 | PASS | `test_basics_extraction_leaves_name_empty_without_signal`：`"name" not in contract.basics` |
| 4 | 后端 pytest 绿 / 前端 test·typecheck·build 绿 | 条件通过 | 见下「门禁实跑」 |
| 5 | 改动只在 `profile_import/`+schemas+前端3触点，无越界 | PASS | 11 文件全在范围内；未碰 matching/adapters/crawler/exporter/jd_structurer；零 DB 变更 |
| 6 | 既有 fixture 行为保持 / 失效断言已同步更新（非静默删除） | PASS | `plain_unsectioned_resume.txt` 拆分证书/语言合并行并同步断言 |
| 7 | `test_matching_eval` 14/14 红线未动 | PASS | 后端 43 项 spec 关键测试全过，含该红线 |

## 门禁实跑

- 后端 `pytest -q`：**186 passed / 1 failed**。
  - 失败项 `test_jd_structurer.py::TestStructureJd::test_with_mocked_llm_response` ——
    **不在本次改动内**，且为 Windows 环境变量超 32767 字符的环境报错
    （`mock.patch.dict(os.environ)` 撞上环境内已有的超大 `ACC_PRODUCT_CONFIG_V3`）。
    属预存 flake，非 traework 责任。spec 关键测试（含 `test_matching_eval`）全绿。
  - 提示：traework 报告"全绿"不严谨，应改为"spec 关键测试全绿，1 项无关环境失败"。
- 前端 `pnpm test` 22/22、`pnpm typecheck` 干净、`pnpm build` 成功。

## 必改项（P1，merge/push 前修复）

**恢复 `_is_experience` 的互斥保护。**

当前 diff 删除了：
```python
if _is_education(text, block) or _is_project(text, block):
    return False
```

风险：现在 `strong_match` 会经 `scoring.py:22` 拉高 experience 置信度，而
`PRIMARY_PRIORITY` 中 `experiences(0)` 优先于 `projects(2)`。于是形如
"XX医院 科研项目 负责人" 这种同时命中 project+experience 的行，去掉保护后会
**误路由到 experiences**（置信平局时按优先级取 experiences）。
当前 fixture 无此类行，故测试仍绿，但是真实简历中的潜在误分类。

修复：恢复上述两行即可。单最佳路由不受影响（仍每 block 至多 1 条 fact），且
education/project 块不会再被错误并入 experiences。建议同时补一条回归用例：
`'XX医院 科研项目 负责人'` 应落入 `projects` 而非 `experiences`。

## 建议项（P2）

- `strong_match` 字段已正确接入 `scoring.py` 置信度计算，路由逻辑有效，无需改动。
- 本次 Spec 文档 `docs/plans/2026-08-22-import-routing-spec.md` 仍为 untracked，
  建议随下次提交一并纳入版本库（属交付物之一）。

## 提交状态

- commit `b170e5f`，领先 `origin/main` 1 个 commit，未 push。
- 未纳入提交的工作区项（正确）：`.workbuddy/`、`.trae-html-share-packages/`、
  `medical-job-prd/`、`docs/plans/...spec.md`。
- `frontend/package.json` 的 `packageManager` 字段已还原，未纳入提交（正确）。
