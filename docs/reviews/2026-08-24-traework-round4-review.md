# 第四轮验收 — traework 2026-08-24 岗位库自适应布局 + 观感收尾（298d198 + 9a8e815）

结论：**有条件通过（卡在 1 条新 P1）**。列宽分配、六档零溢出、抽屉 Esc/焦点/遮罩语义、导出字重与字符规范化全部达标；但**页面切换动画让所有 `position: fixed` 元素变成了相对长页面定位**，导致抽屉与"新建订阅"对话框在岗位库页打开时**下半部分落在屏幕外、且抽屉/遮罩内部根本滚不动**。修复后才能验收通过。

---

## 1. 门禁复核（总监独立复跑，非采信报告）

| 门禁 | traework 报告 | 总监复跑 | 结论 |
|---|---|---|---|
| 后端 `pytest -q` | 362 passed | **362 passed / 51.50s** | 一致 |
| `test_matching_eval.py` | 8 passed | 8 passed | 一致 |
| 前端 `pnpm test` | 174 passed | **174 passed** | 一致 |
| `pnpm typecheck` / `pnpm build` | clean / success | clean / 1604 modules，CSS 37.38 kB / JS 305.49 kB | 一致 |
| 改动范围 | 298d198（7 文件）+ 9a8e815（3 文件） | `git show --stat` 一致，`main...origin/main [ahead 2]` 未 push | 一致 |
| 零新增依赖 / 零 schema | 声明 | `frontend/package.json`、`database.py` 不在提交内 | 一致 |

## 2. 布局修复实测（独立脚本，非 traework 脚本）

七档视口（含 1152 边界档）独立量测：**全部零横向溢出、详情均在视口内、标签折叠生效、无 console error**。

| 视口 | 模式 | 表格区 | 岗位列 | 岗位格高 | 备注 |
|---|---|---|---|---|---|
| 1152 | 抽屉 | 848 | 260 | 103 | 订阅折叠生效 |
| 1280 | 抽屉 | 700 | 213 | 103 | 岗位列比例 32% |
| 1366 | 抽屉 | 786 | 241 | 103 | |
| 1440 | 抽屉 | 860 | **264** | **103** | 指标 ≥220 / ≤111 达标 |
| 1536 | 抽屉 | 956 | 295 | 103 | |
| 1680 | 常驻列 | 664 | 202 | 103 | 三区并排，详情右边界 1652 |
| 1920 | 常驻列 | 904 | 278 | 103 | 详情右边界 1892 |

- 列宽比例与 `<colgroup>` 吻合（1440 实测 264/149/74/74/99/83/83，即 32/18/9/9/12/10/10%）。
- 标签折叠：`+N` 生效（每行都只显示前 2 个标签）。

## 3. 抽屉行为实测

- 打开后 `role="dialog" aria-modal="true" aria-labelledby="drawer-title"`，body 锁滚动；关闭后焦点**回到所在行**（`TR.active-row`）、body 解锁；Esc 正常关闭；`prefers-reduced-motion` 分支存在于代码中。
- 这些项全部通过。

## 4. P1 回归（本轮引入，必修）— 页面动画把 fixed 元素钉在长页面上，抽屉内容无法滚动

### 4.1 现象

岗位库页（表格 50 行，页面高约 5567px）点任意一行打开抽屉：

- 抽屉 `position: fixed; top:0; right:0; bottom:0; width:min(480px,92vw)`，实测 `top=96, bottom=5531, height=5435`——**按整页高度伸展**，只有顶部 864px 可见。
- 遮罩同样 `top=96, height=5435`，只盖住页面首屏区域，页面下半部分没有遮罩。
- 抽屉内部 `overflow-y: auto` 的 `.drawer-body` 实测 `clientHeight=scrollHeight=5374`——**内容区根本不能滚**，滚轮与 `scrollTop=scrollHeight` 都无效；抽屉详情下方（职责原文等）永远看不到。

### 4.2 根因

`fixed` 元素被 `animation` 动画创建了包含块（containing block）。实测祖先链：

```
div.page-enter   → animation: page-enter var(--dur-base) var(--ease-out) both;  ← 罪魁
div.jobs-layout  → 无
div.split-page   → 无
div.detail-drawer → transform: matrix(1,0,0,1,0,0)  ← 自身的 entrance transform
```

`.page-enter` 的 `@keyframes page-enter` 带有 `transform: translateY(6px)`，`animation-fill-mode: both` 让动画结束后 **`transform: matrix(1,0,0,1,0,0)`（一个非 none 的 transform）永久留在元素上**；`transform != none` 的祖先就把所有 `position: fixed` 后代变成相对该祖先定位。抽屉、遮罩、以及同页的"新建订阅"对话框（`.dialog` / `.dialog-overlay`，都是 fixed）全部中招。

### 4.3 波及面（实测）

- 岗位库页抽屉：内容不可滚动（4.1）。
- 岗位库页"新建订阅"对话框：`dialogBottom=979 > 960`（视口），**底部 19px 被切**；页面滚到 `scrollY=2151` 时遮罩 `top=-2055, height=5435`，只在页面坐标上"盖住"文档而非视口。对话框虽用 flex 布局在视口内显示，但遮罩失效会让点不到、焦点逃逸。
- 简历生成页抽屉：同组件，同问题。
- Toast（`.toast-container` fixed）同样受该包含块影响（top:80 落在长页面坐标系里）。

### 4.4 修复方案（两处，都要做）

1. **动画结束后清掉 transform**：`@keyframes page-enter` 的 `to` 帧显式写 `transform: none;`（关键帧的 `to` 若无 transform，`animation-fill-mode: both/forwards` 会回填首个非默认值？—— 规范：fill 保留的是最后一帧的计算值，`to` 里写了 `transform: none` 才会保留 none）。改法：
   ```css
   @keyframes page-enter {
     from { opacity: 0; transform: translateY(6px); }
     to   { opacity: 1; transform: none; }
   }
   ```
2. **兜底**：给 `.detail-drawer`、`.dialog`、`.dialog-overlay`、`.drawer-overlay`、`.toast-container` 加 `transform: none !important` 无效——不能靠这个，因为自身 transform 是动画需要的。正确兜底是把 fixed 元素渲染到 body 直接子级（React portal）或给 `.page-enter` 所在容器去掉 `animation-fill-mode: both` 改用 `animation-fill-mode: backwards`（进入时无残留）。

   本项目最简单可靠的修法：**page-enter 动画只保留 opacity**（去掉 transform 或 `to { transform: none }`），并给关键帧补 `to` 帧。同时把抽屉/对话框的 `z-index` 检查一遍（101/100 已高于侧栏，够用）。

3. 新增回归测试：Playwright 打开岗位库 → 开抽屉 → 断言 `drawer.getBoundingClientRect().bottom <= window.innerHeight`（或 `>= 视口高 - 1`）且 `.drawer-body` 可滚动（`scrollHeight > clientHeight` 时设 `scrollTop` 后能变化）；打开"新建订阅"对话框断言 `dialog bottom <= innerHeight` 且遮罩覆盖整个视口。

### 4.5 为什么上一轮（e18a162）没炸

上一轮岗位库详情是常驻列（`position: sticky`），sticky 不受祖先 transform 影响；本轮新增的 fixed 抽屉/对话框把它炸出来了。这是**本轮引入**的回归，不是既存问题。

## 5. 其他检查（全部通过）

- 导出字重：`_should_bold_main_line` 规则与测试 7 例在；教育背景无要点条目现在也粗体（同段一致），求职目标整句细体。
- 不可见字符规范化：`_normalize_pdf_text` 处理 U+200B/U+FEFF/U+00AD/`\t`/U+00A0/U+3000，emoji 保留；测试 11 例。
- `AGENTS.md` 已改为 `cd backend; uv run --project . uvicorn ...` 并加 SQLite 路径说明（命令段已按新内容生效）。
- 简历页 `.detail-panel` 定义未改，两个复用页零横向溢出。
- traework 自己的 `measure_jobs_layout.py` 没有覆盖"抽屉可滚动性"与"对话框遮罩"这两个维度，所以它的 6/6 PASS 没拦住这条 P1——这是验收脚本的盲区，修 P1 时补上。

## 6. 修复单（给 traework）

1. 按 4.4 修 `.page-enter` 关键帧（`to { transform: none }` 或改为只动 opacity），并给 `measure_jobs_layout.py` 增加断言：抽屉 `bottom <= innerHeight`、`.drawer-body` 可滚动、对话框遮罩覆盖视口（岗位库页 + 简历生成页）。
2. 复跑全部门禁 + 更新脚本，报告时附抽屉/对话框的 `getBoundingClientRect` 实测数字。
3. 提交 `fix(ui): page-enter 动画不再破坏 fixed 定位（抽屉/对话框/遮罩恢复视口定位）`，不要 push。

红线不变：后端 ≥362、前端 ≥174、`test_matching_eval.py` 8 passed、零新增依赖、零 schema 变更、类名只增不删。

---

# 第五轮（P1 修复轮）验收 — commit bcefa79

结论：**通过**。第四轮 P1 已按方案修复，独立复测无残留；门禁全绿、报告数字与独立复跑一致。

## R5.1 修复内容核对（diff 抽查）

- `@keyframes page-enter` 与 `@keyframes rise-in` 的 `to` 帧：`transform: translateY(0)` → `transform: none`（两处）。
- `.page-enter` 的 `animation-fill-mode`：`both` → `backwards`（动画结束即回到基础样式，transform 归 none，fixed 元素恢复视口定位）。
- `backend/scripts/measure_jobs_layout.py` 新增 `test_fixed_positioning()`（抽屉 bottom ≤ vh、`.drawer-body` 可滚动、对话框遮罩覆盖视口 + 对话框适配视口）。

修法与评审给出的方案一致（关键帧 `to { transform: none }` + fill-mode 改 backwards），且顺带修了 `rise-in`——`rise-in` 同样带 transform，若不改，表格进场动画后也会残留同样的包含块问题。这一步比要求的多做了，是对的。

## R5.2 独立复测（Playwright，1440×960，非 traework 脚本）

| 检查项 | 实测值 | 结果 |
|---|---|---|
| 抽屉位置 | top=0, bottom=960（满视口），inViewport=True | ✅（修复前 bottom=5531） |
| 遮罩覆盖视口 | top=0, left=0, right=1440, bottom=960 | ✅（修复前 top=96, h=5435） |
| `.drawer-body` 可滚动 | scrollH=2513 > client，scrollTop 赋值后变化 | ✅（修复前 clientH==scrollH==5374） |
| Esc 关闭 + 焦点返还 | 抽屉消失，焦点回到 `TR.active-row`，body 滚动解锁 | ✅ |
| 新建订阅对话框（页面滚到中部打开） | dialog top=163 bottom=797 在视口内；遮罩 top=0 bottom=960 全覆盖 | ✅ |
| 简历生成页横向溢出 | 0 | ✅ |
| console error | 0 条 | ✅ |

说明：我方脚本中 `clientH: NaN` 是脚本笔误（对 `getBoundingClientRect()` 结果取 `.clientHeight`，该属性不存在于 DOMRect），非产品问题；可滚动性以 `scrollH=2513` 与 `scrollWorks=True` 为准。

## R5.3 门禁复核

| 门禁 | traework 报告 | 独立复跑 | 结论 |
|---|---|---|---|
| 后端 `pytest -q` | 362 passed | **362 passed / 53.12s** | 一致 |
| `test_matching_eval.py` | 8 passed | 8 passed | 一致 |
| 前端 `pnpm test` | 174 passed | **174 passed** | 一致 |
| `pnpm typecheck` / `pnpm build` | clean / 1606 modules | clean / 1606 modules，CSS 37.36 kB / JS 305.49 kB | 一致 |
| 改动范围 | 2 files, +151/-3 | `git show --stat` 一致 | 一致 |
| 未 push | main 领先 origin 3 | `main...origin/main [ahead 3]` | 一致 |

## R5.4 运维注记

- 验收中发现 8000 端口残留 uvicorn 进程（PID 23800，之前后台 job 被 kill 时子进程未随之终止），已 Stop-Process 后重启。Windows 下 kill 后台 job 不保证杀子进程，后续起服务前先查 `Get-NetTCPConnection -LocalPort 8000`。
- 第五轮验收账号 `qa_round5_probe` 已清理。

## R5.5 结论

第四轮全部问题（P1 + 建议项）至此收口。本轮两个提交（298d198 布局 / 9a8e815 观感 + bcefa79 P1 修复）验收通过，可 push。剩余已知事项：既存“岗位库数据源未登录态”之类不在本轮范围；无新增未决问题。
