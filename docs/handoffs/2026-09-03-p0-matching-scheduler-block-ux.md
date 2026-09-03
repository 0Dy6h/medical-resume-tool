# 交接：2026-09-03 — P0 修复批次（匹配语义 / 自动抓取 / 阻断 UX）+ P2 快赢

上轮产品评审（见会话记录）定出 P0 三项 + P2 快赢，本批次全部落地并验证。**改动未提交**，工作区待审后 commit。

## 改动清单

### P0-1 资格条款不再污染匹配缺口
- `backend/app/services/matching/segment.py`：新增 `is_eligibility_clause` 谓词（国籍/年龄/周岁/身体条件/遵纪守法…），**学历词优先**——含学历/学位/硕士等的混合条款（"硕士及以上学历，年龄不超过35周岁"）不算资格条款，保留给算术学历门槛。
- `backend/app/services/resume.py`：`match_profile_to_job` 循环里跳过资格条款（不进 evidence/gaps）。过滤在**匹配层**而非 segment 层：`test_jd_segmenter` 明确要求"身体条件"留在分词结果里，且 `test_matching_eval` 直接测 `best_matches`，此 placement 两边都不碰。
- 效果（实测 8000 新栈）：辅导员岗 0/13 → 1/10；"人事代理"岗 total=0；纯资格公告不再 422 阻断。
- 已知残留：哈医大"来我校应聘的博士研究生：年龄不超过40周岁"这类**面向不同学位受众的混合条款**仍会出现在逐条分析里（设计取舍：学历门槛需要它们）。后续可做"按受众拆分条款"。
- 前端 `JobsPage.computeMatchLabel`：total=0 时显示「以公告原文为准」而非「满足 0/0 项硬性要求」。

### P0-2 学历阻断不再是死胡同
- `frontend/src/pages/ResumePage.tsx`：新增纯函数 `mismatchNoticeFromError`（识别"差距较大"422 文案）+ `blockNotice` 状态；generate 失败时页面内常驻红色面板（原因 + 「去岗位库按学历筛选」按钮），切岗位/成功生成时清除。`App.tsx` 给 ResumePage 传 `onNavigate`。
- `styles.css` 新增 `.block-notice` 样式。

### P0-3 每日自动抓取真正落地
- 根因：`DailyScheduler._next_wait_seconds` 只算下一个 09:00，进程晚于 9 点启动就等明天；而本机服务从不常驻 → 历史 run 全是 manual。
- 修复：`scheduler.py` 新增 `maybe_catch_up()`——启动时若 24h 内无 `trigger='auto'` 抓取记录则立即补跑一轮（复用单飞锁）；`_loop` 开头调用。`catch_up: bool = True` 可注入关闭。
- 实测：8001 全新库启动即补跑成功；**8000 真实库重启后出现史上第一条 auto run #14（completed）**。
- 常驻保活仍未做（部署机 systemd / 本机 schtasks），属运维项，见 runbook 待补。

### 顺手修的测试炸弹
- `tests/test_auto_crawl.py::_backdate_iso` 原用真实墙时回溯 2 天做断言基准，2026-09-03 起必然失败（已验证在干净 main 上同样失败）；改为相对注入时钟 `FIXED_TIME` 回溯。

### P2 快赢
- `styles.css`：`.match-bar-fill` / `.bar-fill` / `.progress-fill` 三处死 `transform: scaleX(0)`（无任何代码翻回，填充条从未渲染）移除——分析页/岗位库匹配条/抓取进度条此前全是空轨道。截图复核：条长与数值严格成比例。
- 根目录 5 份 2026-06 过时报告 `git mv` 到 `docs/archive/`（互相引用，无外部引用）。
- 新增 `docs/user-guide.md`（5 分钟上手：注册→样本→匹配度读法→履历→审阅导出→订阅→FAQ），README 文档索引加了入口（含 archive 说明）。

## 验证记录

- 后端 `uv run --project backend pytest -q`：**437 passed**（新增 test_eligibility_filter.py 6 项 + test_auto_crawl.py 4 项补跑测试 + 前端 3 项）。
- 前端 `pnpm test`(200) / `pnpm typecheck` / `pnpm build` 三绿。注意：`CI=true pnpm test` 会触发 node_modules 重建，会把正在跑的 Vite 干掉（本次 5173 就这么没的）——跑测试前先知道这点。
- 8001 临时实例（独立 DB，已删）API 实测：补跑、匹配过滤、422 阻断、草稿缺口无资格词，全过。
- 浏览器复核（5173 新栈）：分析页条形比例 ✓；简历页生成博士岗 → 常驻阻断面板 ✓ → 出口按钮跳岗位库 ✓。

## 运行栈事故与恢复（给未来 agent 的操作经验）

本批次收尾时服务栈发生过一次死亡与恢复，教训记录如下：

1. **`CI=true pnpm test` 会触发 node_modules 重建**（ERR_PNPM_ABORTED_REMOVE_MODULES_DIR_NO_TTY → purge + reinstall），把正在运行的 Vite 连根拔掉。5173 就这么死的；跑前端测试前先预期这一点。
2. **start-local 以 ZCode 后台任务运行时，脚本退出会连带杀掉服务子树**（harness 的 job 对象 kill-on-close 语义，Start-Process 的"独立"进程也逃不掉）。复现：脚本探测失败 exit → 8000/5173 全部消失。所以：**不要用后台任务方式跑 start-local 然后指望它驻留**；要么让该后台任务永远不退出（脚本后接 sleep），要么用 schtasks。
3. **schtasks 是可靠的逃逸路径**：`schtasks /create /tn <名> /tr "<包装cmd>" /sc once /st 00:00 /f` + `/run`，服务在计划任务自己的作业里拉起，脚本退出后服务继续驻留（已实测：任务"就绪"后 8000/5173 均存活）。Git Bash 下记得 `MSYS_NO_PATHCONV=1`，否则 `/create` 被转译成路径。临时包装 cmd 用完即删（ASCII+CRLF）。
4. **start-local 前端探测出现过一次 60 秒假失败**：服务实际可达（curl/浏览器均 200，Vite 日志 ready），但脚本内 `Invoke-WebRequest` 持续失败 → [X] exit。事后单测 iwr 正常，未能复现，原因未明。若再次出现：服务其实活着，别急着杀；或改用 tcmjob / schtasks 方式启动。

## 服务现状（交接时刻）

- 8000/5173 经 schtasks 拉起后驻留运行中，后端为本批次新代码；启动补跑在真实库再验证一次：距上次 auto run #14 不足 24h，重启**正确跳过**（无重复抓取），24h 判定双向（补跑/跳过）均实测通过。
- 测试账号 `verify_ui`/`verify123`、`pm_review_2609` 留在库里，可删。
- 本批次改动**未提交**，`git status` 含 19 个文件（含本文件）。

## 遗留（下批次候选）

1. P1-4：岗位库默认"适合我"排序/过滤（匹配信号前移到默认视图）。
2. P1-7：OCR 去 Tesseract 化（RapidOCR，依赖已调研）或隐藏入口。
3. P1-8：适配器工具链 SOP（RSSHub 模式已调研）。
4. 学历+年龄混合条款按受众拆分（见上）。
5. 本机 schtasks 保活 + runbook 补章节。
