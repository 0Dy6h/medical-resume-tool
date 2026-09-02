# 给 traework 的执行提示词 — 前端视觉系统升级 + 动效体系（2026-08-24）

> 你是 traework。本文件是一次完整的前端视觉/交互升级规格，项目总监（AI 审核）会对照本文件逐条验收。
> 与同日的《简历导出排版重做》提示词**文件互不重叠**，可独立提交。

## 0. 现状事实（已核实，不要重新调研）

- 技术栈：React 19.0 + Vite 6 + TypeScript 5.7，包管理 pnpm。图标 `lucide-react`。**没有** UI 框架、**没有** 动画库、**没有** CSS 预处理器。
- 样式全部在单文件 `frontend/src/styles.css`（约 2000 行），类名扁平（`.panel` / `.panel-head` / `.metric` / `.table-panel` / `.primary-button` / `.secondary-button` / `.icon-text-button` / `.tag` / `.status` / `.toast` / `.dialog` / `.match-finding-card` …）。
- 结构：`frontend/src/App.tsx`（87 行，左侧栏 + 顶栏 + 内容区的 grid shell，6 个页面用 `useState` 切换，**没有路由库**）；页面在 `frontend/src/pages/`（Overview / JobsPage / AnalyticsPage / ProfilePage / ResumePage / CrawlPage / LoginPage）；组件在 `frontend/src/components/`（DataBar / StatusPill / Toast / SubscriptionsPanel / CreateSubscriptionDialog / AuthContext）。
- 动效基本为零：整份 CSS 只有 4 处 `transition`（`.chevron` transform、`.nav-item` background/color、两处进度条 `width`）与 2 个 `@keyframes`（`toast-in`、`spin`）。**没有** `prefers-reduced-motion`，**没有** `:focus-visible` 样式，**没有** 骨架屏。
- 设计变量只有颜色 + 一个阴影：`:root` 里 `--bg #eef1ef` / `--surface #fbfcfb` / `--ink #17211f` / `--muted #66716d` / `--line #d9dfdb` / `--green #16775a` / `--blue #2f5d90` / `--amber #9a6b16` / `--red #a33b35` + 各 soft 变体 + `--shadow`。**没有** 间距 / 圆角 / 字阶 / 动效时长 / 缓动 token；`color-scheme: light`，无暗色模式。
- `body { min-width: 1120px }`，全文件仅 3 个 `@media`（900px×2、1024px×1）——当前是定宽桌面应用。
- `frontend/index.html` **没有加载任何 webfont**，而 `styles.css` 首选 `"Noto Sans SC"`，实际落到系统字体（Windows 上是 Microsoft YaHei），中文字重/字距不稳定。
- 前端测试是**纯函数测试**（`src/lib/*.test.ts`、`src/pages/*.test.ts`，vitest），不做 DOM 渲染断言，所以视觉改造不会撞测试——但这也意味着**没有测试兜底，回归靠你自己的门禁与目检**。

## 1. 目标

在不改变任何功能与信息架构的前提下，把界面从"能用的内部工具"提升到"可以给医生用户看的专业产品"：

1. **建立设计系统**：颜色语义 + 间距网格 + 字阶 + 圆角 + 层级阴影 + 动效时长/缓动，全部 token 化。
2. **视觉高级感**：靠留白、对齐、层级、克制的描边与阴影、数字排版实现，而不是靠花哨特效。
3. **成体系的动效**：页面切换、导航指示、卡片交互、列表进入、数值滚动、加载骨架、Toast/对话框进出、折叠展开、按钮 loading、焦点环，全部统一时长与缓动。
4. **功能更简洁明了**：同一屏内的信息密度分级（主 → 次 → 辅），减少视觉噪音，让"下一步该点哪里"一眼可见。

## 2. 设计方向（硬性风格约束，防止跑偏）

**保留品牌基因**：主色仍是 `--green #16775a`（医疗/严肃/可信），侧栏仍是深墨绿黑 `#17211f`。不要换成 AI 模板常见的紫蓝渐变。

允许并鼓励：

- 中性色阶细化（`--ink` 之外补 2–3 级次要文字色；`--line` 补一级更浅的分隔线）。
- 分层阴影：`--shadow-1/2/3`（卡片静置 / hover / 浮层），透明度低、扩散大、无彩色。
- 1px 描边 + 极浅内渐变（`linear-gradient` 白到 `--surface`）营造质感。
- 数字统一 `font-variant-numeric: tabular-nums`，表格数字右对齐、等宽对齐。
- 标题字距收紧（`letter-spacing: -0.01em`），正文行高 1.6–1.7，中文可读性优先。
- 顶栏轻微毛玻璃（`backdrop-filter: saturate(140%) blur(8px)` + 半透明底），仅顶栏一处，不滥用。
- 可选（加分项，非必须）：`prefers-color-scheme: dark` 的暗色 token 映射；若做，必须全页面自检对比度。

明确禁止：

- 禁止引入任何新的运行时依赖（不许 framer-motion / GSAP / tailwind / antd / MUI / styled-components）。动效只用 CSS + 必要时 `requestAnimationFrame`。
- 禁止霓虹光晕、彩色阴影、全站玻璃拟态、跳动/弹跳（bounce）夸张动效、无限循环的装饰动画（除 loading spinner）。
- 禁止 `transition: all`；禁止对 `width/height/top/left/margin` 做动画（进度条除外，且优先改用 `transform: scaleX`）。
- 禁止改动任何界面文案、按钮语义、DOM 层级里承载语义的元素（可加 wrapper，不许删）。
- 禁止改动 `frontend/src/lib/**` 的业务逻辑与 `frontend/src/types.ts` 契约（纯样式/纯展示层改动除外）。
- 禁止碰 `backend/**`（提交里出现 backend 改动即打回）。

## 3. 任务 A — 设计 token 与样式组织

1. 在 `styles.css` 顶部（或拆出 `frontend/src/styles/tokens.css` 并由 `styles.css` `@import`）建立完整 token：
   - 间距：`--space-1: 4px` … `--space-8: 48px`（4/8 网格）。
   - 圆角：`--radius-sm/md/lg/pill`。
   - 字阶：`--text-xs/sm/base/lg/xl/2xl` + 对应 `line-height`。
   - 阴影：`--shadow-1/2/3`。
   - 动效：`--dur-fast: 120ms`、`--dur-base: 180ms`、`--dur-slow: 260ms`、`--ease-out: cubic-bezier(0.22, 0.61, 0.36, 1)`、`--ease-in-out: cubic-bezier(0.4, 0, 0.2, 1)`。
2. 允许把 `styles.css` 拆为 `frontend/src/styles/{tokens,base,layout,components,pages}.css` 并在 `styles.css` 中 `@import`。**约束：现有类名一个都不许重命名或删除**（只能新增），因为多个页面组件依赖这些类名字符串。
3. 现有硬编码的 px 间距/圆角/阴影，逐步替换为 token；替换不得改变现有布局的视觉结构（可微调数值以对齐 4/8 网格）。
4. 字体：在 `index.html` 里**不引入外网 CDN 字体**（本项目是本地/内网部署，外网字体会拖慢首屏且可能加载失败）。改为完善本地字体链：`"Microsoft YaHei", "PingFang SC", "Hiragino Sans GB", "Noto Sans SC", "Source Han Sans SC", system-ui, sans-serif`，并为数字/代码补一条等宽链。

## 4. 任务 B — 动效清单（逐条实现，逐条验收）

| # | 场景 | 实现要求 |
|---|---|---|
| B1 | 页面切换（`App.tsx` 内容区） | 切换 `active` 时内容区做 `opacity 0→1` + `translateY(6px)→0`，`--dur-base` + `--ease-out`。用 CSS animation + `key={active}` 触发重挂载动画，不引入路由库 |
| B2 | 侧栏导航 active 指示 | active 项左侧 3px 指示条，用 `transform: scaleY()` 或伪元素位移实现，`--dur-fast`；hover 有背景过渡（已有，统一到 token） |
| B3 | 卡片/面板 hover | `.panel`、`.metric`、`.workflow-card`、`.subscription-card`、`.match-finding-card`：hover `translateY(-2px)` + 阴影 1→2；`:active` `scale(0.995)`；`--dur-fast` |
| B4 | 列表/表格进入 | 表格行与卡片列表首次渲染时上浮淡入，**每项延迟 24ms、最多前 12 项**（用 `nth-child` 或 CSS 变量 `--i`），避免长列表整体抖动 |
| B5 | 关键数字 | Overview 的 `.metric` 数值、分析页统计值做 count-up（`requestAnimationFrame`，300–600ms，`ease-out`）。抽成 `frontend/src/components/AnimatedNumber.tsx`，并**为它的取值/插值函数写纯函数单测** |
| B6 | 加载态 | 现有"加载中…"文本骨架化：新增 `.skeleton` + shimmer（`transform: translateX` 扫光，不用 `background-position`），至少覆盖岗位列表、分析页、简历页初次加载。保留原文本于 `.sr-only` 或 `aria-busy`，不删可读文案 |
| B7 | 进度/匹配度条 | `.bar-fill`、`.match-bar-fill`、`.progress-fill` 改为 `transform: scaleX()` + `transform-origin: left`，`--dur-slow`；`.bar-track` 补内阴影 |
| B8 | Toast | 现在只有进入动画。补退出动画（`opacity` + `translateX(12px)`，120ms）与堆叠位移；`Toast.tsx` 需要支持"退出中"状态，卸载延迟到动画结束（用 state + `setTimeout`，卸载前清理定时器） |
| B9 | 对话框 | `.dialog-overlay` fade（120ms）、`.dialog` `scale(0.98)→1` + 上浮（180ms）；补 Esc 关闭、打开时焦点移入首个可聚焦元素、关闭后焦点还原（`CreateSubscriptionDialog` 与 ResumePage 的导出确认弹层都要） |
| B10 | 折叠面板 | `.collapsible-head` 的 `.chevron` 旋转已有；内容展开改为 `grid-template-rows: 0fr → 1fr`（现代浏览器可动画）或 `max-height` 方案，**在代码注释里写明你选了哪个方案与原因** |
| B11 | 按钮 loading | 所有 `disabled={loading}` 的按钮统一为"文案 + 内联 spinner"，**按钮宽度不得跳变**（预留 spinner 宽度或用 `min-width`）；复用已有 `spin` keyframes |
| B12 | 焦点可见 | 全局 `:focus-visible` 统一焦点环：`outline: 2px solid var(--green)` + `outline-offset: 2px`（深色侧栏内用浅色环）。键盘 Tab 走一遍主流程必须处处可见 |

**降级红线（必须实现）**：

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

同时 B5 的 count-up 在 `window.matchMedia("(prefers-reduced-motion: reduce)").matches` 时**直接显示终值**，不做插值。

## 5. 任务 C — 信息密度与"简洁明了"

1. 每个页面确定**唯一主行动**（Overview→开始抓取/生成简历；JobsPage→查看详情；ResumePage→进入审阅/导出），主行动用 `.primary-button` 且同屏只有一个；其余降级为 `.secondary-button` / `.text-button`。
2. 表格：表头固定语义、数字右对齐 + `tabular-nums`、行高统一、hover 行底色、`.active-row` 用左侧 2px 主色条而不是整行重底色。
3. 空状态：`.empty-state` 统一为「一句话说明 + 一个下一步按钮」，不要只显示"暂无数据"。
4. 顶栏：`.topbar` 常驻，滚动时加 `box-shadow`（用 `IntersectionObserver` 或 scroll 监听 + `requestAnimationFrame` 节流，不要每帧改布局属性）。
5. 侧栏：分组标题（如「情报」/「我的」），当前用户区与退出按钮固定底部（已有 `.sidebar-footer`，补视觉分隔）。

## 6. 硬性约束（违反即打回）

- 零新增运行时依赖；`frontend/package.json` 的 `dependencies` 不得变动（`devDependencies` 亦不需要变）。
- 不动 `backend/**`、不动 `frontend/src/lib/**` 的业务逻辑、不动 `types.ts` 契约。
- 现有类名只增不改不删；现有界面文案只增不改不删（可增补 `aria-label` / `sr-only`）。
- 所有动画只作用于 `transform` / `opacity`（进度条允许 `transform: scaleX`）；不得出现 `transition: all`。
- `prefers-reduced-motion` 降级必须存在且有效。
- 一次性交付，不留半成品：不允许"新样式与旧样式并存的两套观感"（例如只改了一半页面的卡片圆角）。

## 7. 验收标准（EARS，总监据此验收）

- WHEN 打开任意页面 THEN 卡片、按钮、表格、标签的圆角/间距/阴影/字号来自统一 token，同类元素在 6 个页面里视觉一致。
- WHEN 在侧栏切换页面 THEN 内容区有 180ms 上浮淡入，导航 active 指示条平滑移动，无闪白、无布局跳动。
- WHEN 鼠标悬停卡片/表格行 THEN 有 120ms 的抬升与阴影变化；按下有轻微回弹反馈。
- WHEN 页面首次加载数据 THEN 显示骨架屏（非纯文字"加载中"），数据到达后关键数字有 count-up。
- WHEN 打开/关闭对话框或 Toast THEN 进入与退出都有动效，Esc 可关闭对话框，焦点回到触发元素。
- WHEN 用键盘 Tab 遍历主流程 THEN 每个可聚焦元素都有清晰焦点环。
- WHEN 系统开启"减少动态效果" THEN 所有动画与 count-up 立即降级为无动效，功能完全可用。
- WHEN 运行 `pnpm test && pnpm typecheck && pnpm build` THEN 全绿，且 `git diff --stat` 中不含 `backend/`。

## 8. 门禁（提交前必须全绿）

```powershell
cd frontend
pnpm test
pnpm typecheck
pnpm build
```

- 基线（2026-08-24 实测）：`pnpm test` = **14 个测试文件 / 143 个用例全绿**。改造后必须 ≥ 143 通过、0 失败；B5 新增组件的纯函数需补测试（用例数只增不减）。
- 起 `pnpm dev` 与后端 `uv run --project backend uvicorn app.main:app --host 127.0.0.1 --port 8000`，**人工/自动走查 7 个界面**（登录 + 6 页），确认无错位、无溢出、无 hover 抖动。
- 若你具备截图能力：给出 7 张改造后截图；若不具备：在报告中给出逐页自查清单与结论。

## 9. 交付要求

- 提交信息：`style(frontend): 设计 token 化 + 动效体系 + 焦点可见性`。
- **保持未 push**（当前 `main` 领先 `origin/main` 7 个 commit），提交后报告，由总监审核。
- 报告需列出：改动文件清单、token 清单、B1–B12 逐条完成情况（含未做项及原因）、门禁结果、是否零新增依赖、是否触碰 backend。
