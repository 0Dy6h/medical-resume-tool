# 评审记录：traework 合并交付（6edbfe2）

评审人：项目总监（MvpDevExpertTeam）  日期：2026-08-22
对应规格：`docs/plans/2026-08-22-import-routing-spec.md`、上轮 `2026-08-22-traework-import-routing-review.md`
提交：6edbfe2（接在 b170e5f 之后，领先 origin/main 2 个 commit，未 push）

## 交付概览
- 任务 A：恢复 `_is_experience` 互斥保护（P1 必改）
- 任务 B：4.3 模式选择（fresh_grad / experienced）

## 实测门禁
| 门禁 | 结果 |
|---|---|
| 后端 spec 关键测试（eval+extractors+import+contract） | 48/48 通过 |
| `test_matching_eval` 红线 | 14/14 top-1 / 0 错源 / 0 误报（未动） |
| 前端 `pnpm test` | 29/29 通过 |
| 前端 `pnpm typecheck` | 通过 |
| 前端 `pnpm build` | 通过 |
| `test_jd_structurer` | 仍 1 失败（Windows 环境变量 >32767 字符预存 flake，**不在本次改动、非 traework 责任**） |

## 任务 A 审核（通过）
- `_is_experience` 确已恢复：`if _is_education or _is_project: return False`（extractors.py:220-221）。
- 回归用例 `test_project_block_not_misrouted_to_experience` 真实：单行「北京某三甲医院 科研项目 负责人」→ `projects=1, experiences=0`。
- 原 `test_multi_entity_block_routes_to_single_primary` 改为断言 `publications=1, experiences=0`（single-primary invariant）。
  - **核查结论：未掩盖 regression**。实测两行「2020.09-2023.06 北京某三甲医院 主治医师 / 负责国家自然科学基金...发表SCI论文3篇」在 `build_blocks` 阶段即为 1 个合并 block（traework 未改 blocks.py，旧行为）。恢复保护后该 block 因命中 `_is_project` 排除 experience，单最佳路由选 publication 胜出——属正确行为。
- 改动范围仅 `extractors.py` + `test_extractors.py`，未越界。

## 任务 B 审核（通过）
- `Profile.mode: Literal["fresh_grad","experienced"] = "experienced"`（schemas.py:209）；`ProfilePayload` 同步加（schemas.py:396）。
- 持久化：实测 `Profile(mode='fresh_grad').model_dump()` 含 mode、`from_legacy_dict` 可还原、`ProfilePayload.to_profile()` 含 mode。**零 schema 变更**——整 Profile 经 `save_profile` 的 `to_json(profile.model_dump())` 序列化进 `profiles.data` JSON 列（注：traework 总结称「meta JSON 列」为口误，实际是 data 列；技术结论正确）。
- `from_legacy_dict` 改为遍历 `PROFILE_COLLECTION_NAMES`（含 skills，无遗漏）+ 显式 pass-through mode，数据无丢失。
- 前端：`switchMode` 仅 `setProfile(c => ({...c, mode}))` + 重置折叠态，**纯展示切换，不删任何数据**；`orderedConfigs` 按 `MODE_LAYOUT` 排序渲染；折叠态仅 UI 表现。
- 测试：`profileMode.test.ts` 覆盖两模式全部 9 section、顺序差异、默认折叠、以及「切换不改变任意 collection 条目数」；后端 `test_profile_contract.py` 覆盖默认/set-get/切换不改条目。
- 改动范围：schemas.py + ProfilePage.tsx + types.ts + defaultProfile.ts + 2 测试文件，未越界（未碰 matching/adapters/crawler/exporter/jd_structurer）。

## 结论
**Approve（通过）**——无 P0/P1 阻塞项。

## 非阻塞建议（minor）
1. `profileMode.test.ts` 的 `FRESH_GRAD_ORDER/EXPERIENCED_ORDER` 为 MODE_LAYOUT 的**内联拷贝**（注释已声明），未来改 `ProfilePage.tsx` 布局时测试不会自动同步，需手动维护。建议改为从实现导入真实常量或加联动注释。
2. 交付总结中「存入 meta JSON 列」措辞不准，应为 `profiles.data` JSON 列；零 schema 变更结论正确。

## 后续
可 push（当前领先 origin/main 2 commit）。下一切片建议从 PRD 4.1 情报中心 / 4.4 草稿 / 4.5 导出中择一。
