# 简历工具整改优化方案 — 2026-06-22

> 基于代码审查、GitHub 开源项目调研、产品现状评估的综合报告

---

## 一、问题总览

### 致命（不改则产品不可用）

| # | 问题 | 位置 | 影响 |
|---|------|------|------|
| F1 | **简历匹配是纯关键词重叠计数** — `match_profile_to_job()` 用 `_tokens()` 分词后做交集，完全不理解语义。"SPSS" 配到"统计"，但"队列研究经验"配不到"临床研究设计能力" | `backend/app/services/resume.py:98-131` | 匹配准确率极低，用户看到的是随机质量的结果 |
| F2 | **简历生成是机械拼接不是"写"** — `_format_profile_item()` 用 `" / ".join()` 拼字段，没有任何自然语言改写。生成结果读起来像填表，不像是简历 | `backend/app/services/resume.py:224-240` | 核心功能名存实亡——用户来"生成简历"，得到的是一份机器拼接的字段列表 |
| F3 | **数据模型全是 `dict[str, Any]`** — `ProfilePayload` 的每个 collection 都是 `list[dict[str, Any]]`，`ResumeDraftOut.sections/evidence/gaps` 也是。前后端没有类型契约，任何字段都可能缺失或类型错误 | `backend/app/schemas.py:109-119, 181-190` | 数据一致性无保障，导入-存储-匹配-生成全链路靠祈祷 |

### 严重（显著影响用户体验）

| # | 问题 | 位置 | 影响 |
|---|------|------|------|
| S1 | **资料导入质量不可控** — `ProfileImportOut` 有 `review_items` 和 `unassigned_blocks`，说明导入结果经常有无法归类的文本块。但没有任何纠正引导 | `backend/app/schemas.py:142-155` | 用户导入一份简历 PDF，拿到一堆"未归类"的文本，不知道该怎么办 |
| S2 | **同义词组是硬编码的 8 组** — `SYNONYM_GROUPS` 覆盖不到医学领域的真正多样性。中医/西医/公卫/护理的术语差异巨大 | `backend/app/services/resume.py:71-80` | 大量真实匹配失败——用户有相关经历但措辞不同，系统判定为"未找到证据" |
| S3 | **无反馈循环** — 匹配结果错了，用户无法纠正。无法告诉系统"这个匹配是对的/错的"。下次还是同样错误 | 全链路 | 产品越用越笨 |
| S4 | **岗位要求是自由文本而非结构化** — `JobOut.requirements: str \| None`，岗位要求未拆分为结构化能力项 | `backend/app/schemas.py:74` | 匹配粒度太粗——"具有临床研究经验，熟悉 GCP 规范，能独立撰写方案"被当作一整坨文本匹配 |
| S5 | **前端字段配置与后端 schema 硬编码耦合** — `ProfilePage.tsx` 的 `CollectionConfig[]` 是前端写死的字段列表，与后端 `dict[str, Any]` 之间的契约只存在于注释里 | `frontend/src/pages/ProfilePage.tsx:22-101` | 改一个字段要同时改前后端，没有任何编译期保证 |

### 一般（影响体验但不阻断使用）

| # | 问题 | 位置 | 影响 |
|---|------|------|------|
| M1 | 缺少简历质量/ATS 可读性评分 — 用户不知道生成的简历在真实 ATS 中表现如何 | 无此功能 | 失明投递 |
| M2 | 没有"主简历"概念 — 每次匹配都从原始 profile 开始，不支持"维护一份完整主简历 + 按 JD 生成定制版" | 无此概念 | 重复劳动 |
| M3 | 导出模板单一 — 只有一个基础 layout | `backend/app/services/exporter.py` | 不同的岗位类型（临床/科研/行政）可能需要不同的简历结构 |
| M4 | 前端类型 `Profile` 与后端 `ProfilePayload` 不同步 — 前端定义在 `types.ts`，后端在 `schemas.py` | `frontend/src/types.ts` ↔ `backend/app/schemas.py` | 双源真理，容易漂移 |
| M5 | `_evidence_strength()` 用固定阈值 — 不考虑岗位类型、领域特定性 | `backend/app/services/resume.py:134-139` | 一些领域（如护理操作技能）关键词少但高度相关，被误判为 "weak" |

### 建议（长期改进方向）

- 爬虫覆盖率和数据新鲜度监控
- A/B 测试框架（对比不同匹配策略）
- 用户行为分析（从匹配到投递的转化漏斗）

---

## 二、同类项目经验总结

基于 GitHub 调研（详见 `resume-ats-research-summary.md`），5 个最值得借鉴的项目：

### 1. Resume Matcher (27K ⭐) — 匹配范式的标杆

**核心模式：「主简历 + AI 定制」**
- 用户维护一份完整的主简历
- 每次针对 JD，AI 从主简历中选取相关内容，生成定制版本
- 多 LLM 提供商抽象层（LiteLLM → OpenAI / Anthropic / Ollama）

**我们该借的：**
- 主简历概念 —— 替代当前的"原始 profile → 一次性匹配"
- 多 LLM 抽象 —— 不绑定单一提供商
- 关键词高亮 + 匹配度可视化

### 2. Reactive Resume (39K ⭐) — 数据模型与渲染分离

**核心模式：JSON Resume 标准 + 模板分离**
- 采用社区标准的 JSON Resume schema
- 数据与模板完全解耦 —— 换模板不碰数据
- 实时预览渲染

**我们该借的：**
- JSON Resume schema 作为 Profile 数据模型的基础（扩展医疗特定字段）
- 数据-模板分离架构
- 实时预览（输入即见简历效果）

### 3. OpenResume (8.7K ⭐) — 简历解析的参考实现

**核心模式：纯前端 PDF 解析 + ATS 可读性测试**
- 浏览器端 PDF.js 解析，文件不上传
- ATS 模拟检测——告知哪些内容能被机器正确读取

**我们该借的：**
- 前端 PDF 解析 —— 替换或补充当前的 Tesseract OCR 管道
- ATS 可读性检测作为独立功能

### 4. Resume AI (375 ⭐) — Markdown→DOCX 管道

**核心模式：LLM → Markdown → Pandoc → DOCX**
- LLM 生成 Markdown（最可靠）
- Pandoc 转为 ATS 友好的 DOCX
- Kanban 看板跟踪投递状态

**我们该借的：**
- Markdown 作为 LLM 与排版之间的中间格式
- 投递状态追踪（与现有 `JobStatusPayload` 互补）

### 5. ATS Screener (67 ⭐) — 多平台评分引擎

**核心模式：模拟 6 大 ATS 平台差异化评分**
- 不是单一分数，而是针对不同 ATS 的逻辑分别评分
- 五大评分维度：格式、关键词、区块完整性、经验量化、教育背景

**我们该借的：**
- 多维度的简历质量评分（不是简单的"匹配率"）
- 评分维度可独立展示，用户知道具体哪里不足

---

## 三、整改路线图

### P0 — 核心重写（2-3 周，解决 F1-F3 + S1-S5）

这是必须做的——不改则产品核心功能不可用。

#### P0-1: 强类型 Profile Schema（解决 F3, S5, M4）

**改什么：** 用 Pydantic 强类型模型替代 `dict[str, Any]`

```python
# 新 schema（参考 JSON Resume + 医疗扩展）
class Skill(BaseModel):
    name: str
    level: Literal["beginner", "intermediate", "advanced", "expert"] | None = None
    category: str | None = None  # 编程语言/实验技术/临床技能/软技能
    keywords: list[str] = []

class Experience(BaseModel):
    organization: str
    role: str
    start_date: str | None = None
    end_date: str | None = None
    highlights: list[str] = []  # 量化成果，每条一句

class Education(BaseModel):
    school: str
    degree: str
    major: str
    start: str | None = None
    end: str | None = None

class Profile(BaseModel):
    basics: BasicInfo
    skills: list[Skill] = []
    experiences: list[Experience] = []
    education: list[Education] = []
    projects: list[Project] = []
    publications: list[Publication] = []
    certificates: list[Certificate] = []
    languages: list[Language] = []
    teaching: list[Teaching] = []
    awards: list[Award] = []
```

**为什么：** 类型安全 → 前后端共享契约 → 导入/匹配/生成全链路可验证

**怎么改：**
1. 定义完整的 Pydantic v2 模型
2. 向后兼容：旧 `dict` 格式自动迁移（一次性脚本）
3. 前端 TypeScript 类型从 Python schema 生成（用 datamodel-code-generator 或手写同步）

**工作量：** 3-4 天

#### P0-2: LLM 驱动的简历匹配与改写（解决 F1, F2, S2, S3）

**改什么：** 用 LLM 替代 `match_profile_to_job()` 和 `build_resume_sections()`

**为什么：** 关键词匹配无法理解语义，简历生成是机械拼接。LLM 是唯一能理解"队列研究经验 ≈ 临床研究设计能力"的技术。

**怎么改（三阶段）：**

```python
# 阶段 A: 结构化 JD 要求
def extract_structured_requirements(jd_text: str) -> list[Requirement]:
    """LLM: 从 JD 中提取结构化能力要求"""
    # 输入: 原始 JD 文本
    # 输出: [{category: "临床技能", requirement: "独立设计临床试验方案", must_have: true}, ...]

# 阶段 B: 语义匹配
def match_profile_to_requirements(profile: Profile, requirements: list[Requirement]) -> list[Match]:
    """LLM: 判断 profile 中哪些经历匹配哪些 JD 要求，给出置信度和理由"""
    # 不再做关键词重叠，而是让 LLM 理解两边的语义

# 阶段 C: 真实改写
def rewrite_for_jd(matches: list[Match], job: Job, profile: Profile) -> ResumeDraft:
    """LLM: 基于真实经历，按 JD 要求改写成自然语言简历条目"""
    # 核心约束: 每个改写项必须锚定到 profile_field_id，不可创造新事实
    # 输出: Markdown 格式，由 exporter 渲染
```

**安全约束（防编造）：**
- 每个改写条目必须带 `source_fact_id`（锚定到 profile 字段）
- 改写后做回译验证：LLM 判断改写内容是否可由原文推断
- 用户可查看"改写前 vs 改写后"的对比
- 用户可拒绝单条改写

**工作量：** 5-7 天（含 prompt 工程、安全护栏、测试用例）

#### P0-3: 结构化 JD 要求提取（解决 S4）

**改什么：** 岗位抓取后，用 LLM 将自由文本的 requirements/responsibilities 拆成结构化能力项

**怎么改：**
1. 在爬虫/分类器之后增加一个 LLM 提取步骤
2. 输出 `StructuredRequirement[]`，支持 must-have / nice-to-have 分类
3. 前端展示不再是"一坨文本"，而是可勾选的能力清单

**工作量：** 1-2 天

#### P0-4: 引入"主简历"概念（解决 M2）

**改什么：** 用户维护一份完整的主简历，不是每次匹配都从零开始

**怎么改：**
1. 数据库新增 `profiles` 表的主版本标记
2. 前端增加"保存为主简历"按钮
3. 简历生成页增加"选择主简历版本"下拉框
4. AI 匹配时从主简历中选取相关条目

**工作量：** 2-3 天（前后端）

#### P0-5: 前端与后端类型统一（解决 S5, M4）

**改什么：** 从 Pydantic schema 生成 TypeScript 类型，或手动维护一份共享类型文件

**怎么改：**
1. 选项 A（推荐）: 用 `datamodel-code-generator` 从 `schemas.py` 生成 `frontend/src/types.generated.ts`
2. CI 中增加类型一致性检查

**工作量：** 1 天

---

### P1 — 体验增强（1-2 周，解决 M1, M3）

#### P1-1: 简历质量/ATS 可读性评分

**怎么改：**
- 参考 ATS Screener 的多维度评分模型
- 评分维度：格式兼容性、关键词覆盖、区块完整性、量化程度、ATS 解析友好度
- 前端展示雷达图，每项给出改进建议

**工作量：** 2 天

#### P1-2: 投递版 vs 诊断版内容分离

**怎么改：**
- 投递版：不展示缺口、不展示证据链、不展示内部评分
- 诊断版：展示全部匹配分析、缺口建议、ATS 评分
- 当前 `ExportMode = Literal["application", "diagnostic"]` 已有基础，增强内容过滤

**工作量：** 1 天

#### P1-3: 投递状态看板

**怎么改：**
- 扩展现有 `JobStatusPayload`（saved/evaluating/preparing/applied/archived）
- 前端增加 Kanban 视图
- 链接简历版本到投递状态

**工作量：** 2 天

---

### P2 — 生态扩展（后续迭代）

- 更多医院适配器（当前 6 家 → 目标 20+）
- JSON Resume 导入/导出
- 多模板支持
- PDF 前端解析（替换 OCR 管道）
- 用户反馈系统（匹配纠错 → 持续改进）

---

## 四、是否需要重做

### 判断：**核心部分重写，外围保留**

**保留的部分（质量可接受）：**
- ✅ 岗位爬虫 + 适配器架构（6 家真实适配器 + fixture 系统）
- ✅ FastAPI 路由和服务框架
- ✅ React/Vite 前端架构（路由、导航、组件体系）
- ✅ Auth 系统（注册/登录/token）
- ✅ DOCX/PDF 导出管道
- ✅ 部署脚本和运维体系

**必须重写的部分（当前不可用）：**
- 🔴 `backend/app/services/resume.py` — 整个文件：匹配逻辑、生成逻辑、事实展平 → 全部替换为 LLM 驱动方案
- 🔴 `backend/app/schemas.py` — Profile/ResumeDraft/Job 的 schema → 全部替换为强类型 Pydantic 模型
- 🟡 `frontend/src/pages/ProfilePage.tsx` — 字段配置 → 与后端 schema 对齐
- 🟡 `frontend/src/pages/ResumePage.tsx` — 增加改写对比、证据链可视化

### 为什么不全部重做

1. 爬虫和适配器是独立模块，质量稳定
2. 前端框架和认证系统可以复用
3. 全量重做成本过高（4-6 周），且无必要
4. 增量替换可以边改边测，降低风险

---

## 五、重做方案（核心模块）

### 新架构

```
                    ┌─────────────┐
                    │  Job Sources │  (保留 — 爬虫 + 适配器)
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │ JD Structurer│  (新增 — LLM 提取结构化要求)
                    └──────┬──────┘
                           │
    ┌──────────────────────┼──────────────────────┐
    │                      │                      │
┌───▼───┐          ┌──────▼──────┐        ┌──────▼──────┐
│Profile│          │   Matcher   │        │  Rewriter   │
│(强类型)│──────────▶  (LLM语义)  │────────▶  (LLM改写)  │
└───────┘          └─────────────┘        └──────┬──────┘
                                                 │
                                          ┌──────▼──────┐
                                          │  Markdown   │
                                          │  (中间格式)   │
                                          └──────┬──────┘
                                                 │
                                    ┌────────────┼────────────┐
                                    │            │            │
                               ┌────▼───┐  ┌────▼───┐  ┌────▼───┐
                               │  DOCX  │  │  PDF   │  │ Preview│
                               │(pandoc)│  │(fpdf2) │  │ (React)│
                               └────────┘  └────────┘  └────────┘
```

### 技术选型（新增部分）

| 层次 | 选择 | 理由 |
|------|------|------|
| Profile Schema | Pydantic v2 + JSON Resume 扩展 | 类型安全、社区标准兼容 |
| LLM 调用 | LiteLLM（多提供商抽象） | 不绑定单一 API，支持 Ollama 本地 |
| LLM 输出格式 | Markdown | LLM 最可靠的输出格式，Pandoc 可转任何格式 |
| DOCX 渲染 | Pandoc (Markdown→DOCX) | ATS 友好，排版可靠 |
| 前端类型 | 从 Pydantic 生成 TypeScript | 单源真理 |
| 结构化 JD | LLM + Pydantic 解析 | 从自由文本到结构化能力项 |

### 安全护栏（不可妥协）

1. **每个改写条目锚定 source_fact_id** — 可追溯到用户真实输入的哪个字段
2. **改写后回译验证** — LLM 自行判断改写是否可从原文推断
3. **用户审批** — 每条改写默认可被拒绝
4. **差异高亮** — 前端展示"改写前 vs 改写后"
5. **审计日志** — 每次 LLM 调用记录 prompt、response、使用的事实 ID

---

## 六、实施建议

### 开发顺序

1. **Week 1**: P0-1（强类型 Schema）+ P0-5（前后端类型统一）— 打好地基
2. **Week 2**: P0-3（结构化 JD）+ P0-2 阶段 A/B（LLM 匹配）— 先让匹配准确
3. **Week 3**: P0-2 阶段 C（LLM 改写）+ P0-4（主简历）— 核心功能就绪
4. **Week 4**: P1（ATS 评分、Kanban、模板）— 体验打磨

### 风险

- **LLM API 可达性**：中国 CVM 可能无法直连 api.anthropic.com → 用 OpenRouter 或国内代理
- **LLM 成本**：每次匹配+改写约 500-2000 tokens → 估算 ¥0.05-0.20/次，可接受
- **prompt 工程复杂度**：匹配和改写的质量高度依赖 prompt 设计 → 需建立 eval set（10-20 个真实 JD-简历对）

---

## 附录：参考文件清单

- 本方案: `docs/remediation-plan-2026-06-22.md`
- GitHub 调研（子 agent 产出）: `~/resume-ats-research-summary.md`
- 往期产品调研: `docs/product/research-synthesis-2026-06-18.md`
- 往期交接: `docs/handoffs/2026-06-19-end-of-day.md`
- 当前部署清单: `DEPLOYMENT-CHECKLIST.md`
