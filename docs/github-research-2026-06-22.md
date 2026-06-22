# GitHub 开源简历/ATS/岗位匹配项目调研报告

> 调研时间：2025年6月22日  
> 范围：GitHub 开源生态中简历构建、AI 改写、ATS 优化、岗位匹配相关项目  
> 目标：提炼可借鉴的最佳实践与设计决策

---

## 一、简历解析（Resume Parsing）

### 1. OpenResume — xitanggg/open-resume
- **GitHub**: https://github.com/xitanggg/open-resume
- **Stars**: ⭐8,698 | **语言**: TypeScript | **许可**: AGPL-3.0
- **核心思路**: 同时提供简历构建器和解析器。解析器可读取用户现有 PDF，自动提取结构化内容导入编辑器；也是 ATS 可读性测试工具。
- **可借鉴设计**:
  1. **纯前端 PDF 解析**: 使用 Mozilla 的 PDF.js 在浏览器端完成，无需上传文件到服务端——隐私优先
  2. **"ATS 可读性测试"功能**: 让用户上传简历 PDF，模拟真实 ATS 解析过程，告知哪些内容能被机器正确读取——这一功能可以独立作为免费引流工具
  3. **Redux Toolkit 管理复杂简历状态**: 集中式状态管理处理简历多区块、拖拽排序、实时预览等复杂交互

### 2. ATS Screener — sunnypatell/ats-screener
- **GitHub**: https://github.com/sunnypatell/ats-screener
- **Stars**: ⭐67 | **语言**: Svelte/TypeScript
- **核心思路**: 模拟 6 大真实企业 ATS 平台（Workday, Taleo, iCIMS, Greenhouse, Lever, SuccessFactors）的解析方式，分别给出评分
- **可借鉴设计**:
  1. **多 ATS 平台差异化评分**: 不是单一"ATS 分数"，而是针对不同平台给出不同分数和针对性建议。例如 Taleo 做严格字面匹配，iCIMS 做语义匹配，Greenhouse 不做自动评分——这一设计极具教育价值
  2. **评分维度精细化**: 每个平台从 Formatting(格式)、Keyword Match(关键词)、Sections(区块完整性)、Experience(经验量化)、Education(教育背景) 五个维度评分
  3. **纯客户端 PDF/DOCX 解析 + Web Worker**: 文件永不离开浏览器，仅提取文本发送给 LLM 分析

### 3. 技能提取类项目
- **Msq-9/Extraction-of-Skills** (⭐31): 用机器学习从简历中提取技能标签
- **MuvvaThriveni/Custom-NER-of-Resume-Parsing-using-Spacy3** (⭐5): 用 spaCy3 训练自定义 NER 模型提取姓名、技能、经历、教育
- **imgabrieldev/NLP-Resume-Extraction** (⭐3): 用 NER 自动化简历筛选，分类提取实体

**可借鉴设计**:
- 使用 **spaCy 自定义 NER 模型** 做简历实体提取是成熟方案
- 将技能提取做成独立管道，输出结构化 JSON

---

## 二、简历生成（Resume Builder）

### 1. Reactive Resume — amruthpillai/reactive-resume
- **GitHub**: https://github.com/amruthpillai/reactive-resume
- **Stars**: ⭐38,920 | **语言**: TypeScript | **许可**: MIT
- **核心思路**: 隐私优先的简历构建器，支持多模板、多格式导出、自托管。不强制注册，数据完全由用户掌控。
- **可借鉴设计**:
  1. **JSON Resume 标准格式**: 采用社区标准的 JSON Resume schema 作为内部数据结构，使简历可跨平台导入导出
  2. **所见即所得实时预览**: 输入时 PDF 实时渲染更新，React-pdf 组件渲染
  3. **模板与数据分离**: 切换模板只需换渲染层，用户数据保持不变——这一点对支持多模板至关重要
  4. **自托管 + Docker 一键部署**: 用户可完全掌控数据
  5. **技术栈选择**: TanStack Start (React 19) + PostgreSQL (Drizzle ORM) + Better Auth——全栈 TypeScript，类型安全

### 2. JadeAI — LingyiChen-AI/JadeAI
- **GitHub**: https://github.com/LingyiChen-AI/JadeAI
- **Stars**: ⭐1,785 | **语言**: TypeScript | **许可**: Apache-2.0
- **核心思路**: AI 驱动的智能简历构建器，50+ 模板，支持 PDF/图片解析、AI 优化、JD 匹配分析、多格式导出。
- **可借鉴设计**:
  1. **拖拽可视化编辑器**: 使用 @dnd-kit 实现区块拖拽排序，操作直观
  2. **Markdown 支持**: 在描述字段中支持 Markdown 语法（粗体、列表等），兼顾简洁和排版
  3. **多 AI 能力集成**: 简历生成、PDF/图片解析、语法检查、翻译、JD 匹配、模拟面试——功能矩阵完整，用户粘性强
  4. **双数据库策略**: 默认 SQLite（零配置）+ 可选 PostgreSQL（生产部署），降低入门门槛
  5. **品牌色系统**: CSS 语义变量统一管理，支持主题切换

### 3. Oh My CV! (Markdown Resume) — junian/markdown-resume
- **GitHub**: https://github.com/junian/markdown-resume
- **Stars**: ⭐610 | **语言**: TypeScript/Vue | **许可**: MIT
- **核心思路**: 用 Markdown 写简历，实时预览，导出 PDF。极简设计理念。
- **可借鉴设计**:
  1. **Markdown 作为中间表示**: Markdown 既是编辑格式也是存储格式，介于纯文本和富文本之间，非常适合 LLM 生成和解析
  2. **PWA 离线可用**: 数据存本地浏览器，无服务端依赖
  3. **KaTeX 支持**: 学术简历中可嵌入数学公式

### 4. OpResume — oopooa/opresume
- **GitHub**: https://github.com/oopooa/opresume
- **Stars**: ⭐207 | **语言**: TypeScript
- **核心思路**: 国产开源简历制作工具，纯本地运行，保护隐私。遵循 JSON Resume 标准。
- **可借鉴设计**:
  1. **local-first 架构**: 所有数据存在本地 IndexedDB，不上传任何服务器
  2. **shadcn/ui 组件库**: 统一 UI 风格，快速开发

### 5. Resume Builder (Python) — hanula/resume
- **GitHub**: https://github.com/hanula/resume
- **Stars**: ⭐108 | **语言**: Python
- **核心思路**: YAML → PDF/HTML 的 Python 简历生成器
- **可借鉴设计**:
  1. **YAML 作为数据源**: YAML 比 JSON 更易手写和维护，适合作为简历数据的"源格式"
  2. **多输出格式管道**: 同一份 YAML 数据 → PDF、静态 HTML、Markdown

---

## 三、AI 改写与优化（AI Rewriting）

### 1. Resume Matcher — srbhr/Resume-Matcher
- **GitHub**: https://github.com/srbhr/Resume-Matcher
- **Stars**: ⭐27,458 | **语言**: TypeScript/Python | **许可**: Apache-2.0
- **核心思路**: 上传主简历 + 粘贴 JD → AI 分析匹配度、关键词高亮、生成针对性改写建议和求职信。支持多 LLM 提供商（Ollama 本地/OpenAI/Anthropic/Gemini/DeepSeek）。
- **可借鉴设计**:
  1. **"主简历"概念**: 用户维护一份全面的"主简历"，每次针对不同 JD 生成定制版本。这解决了"一份简历投所有岗位"和"每次从头写"的矛盾
  2. **关键词高亮 + 匹配度评分**: 将 AI 分析结果可视化，展示哪些 JD 关键词已在简历中覆盖、哪些缺失
  3. **多 LLM 提供商抽象**: 通过 LiteLLM 统一 OpenAI/Anthropic/Ollama 的调用接口，用户可以自由选择或切换
  4. **TinyDB (JSON 文件存储)**: 后端使用极轻量的 JSON 文件数据库，部署简单——适合个人工具场景
  5. **PDF 导出**: Headless Chromium (Playwright) 生成 PDF，排版效果可靠

### 2. ResuLLMe — IvanIsCoding/ResuLLMe
- **GitHub**: https://github.com/IvanIsCoding/ResuLLMe
- **Stars**: ⭐469 | **语言**: Python (Jinja/LaTeX) | **许可**: MIT
- **核心思路**: 用 LLM 改进简历：PDF/Word 上传 → LLM 根据名校简历指南优化 → 输出 JSON Resume → LaTeX 渲染为精美 PDF
- **可借鉴设计**:
  1. **"基于权威指南"的 prompt 策略**: 在 prompt 中嵌入哈佛/MIT 等名校的简历写作指南，让 LLM 输出符合最佳实践的简历
  2. **JSON Resume 作为中间格式**: 解析 → JSON → LaTeX 渲染，中间格式使流程可中断、可手动编辑
  3. **LaTeX 渲染**: 提供专业排版质量的 PDF 输出
  4. **Streamlit 前端**: 用纯 Python 快速搭建交互界面

### 3. Resume AI — resume-llm/resume-ai
- **GitHub**: https://github.com/resume-llm/resume-ai
- **Stars**: ⭐375 | **语言**: JavaScript/Node.js
- **核心思路**: 本地优先的简历工作空间——Kanban 看板跟踪投递 + AI 生成简历版本 + Markdown 编辑 + Pandoc 导出 DOCX
- **可借鉴设计**:
  1. **简历 + 投递追踪一体化**: 每个职位卡片关联多个简历版本，可对比、可切换——将简历管理和求职管理合一
  2. **Markdown → DOCX 管道**: 用 Pandoc 将 LLM 生成的 Markdown 转为 ATS 友好的 DOCX——DOCX 格式对 ATS 更友好，且 LLM 生成 Markdown 最可靠
  3. **ATS 隐藏内容警告**: 生成简历时检测并警告可能导致 ATS 解析失败的内容（如图片、复杂表格）
  4. **完全本地运行**: Docker Compose 一键部署，支持 Ollama 本地模型

### 4. Resume Builder AIHawk — feder-cr/resume_render_from_job_description
- **GitHub**: https://github.com/feder-cr/resume_render_from_job_description
- **Stars**: ⭐409 | **语言**: Python
- **核心思路**: 给定 LinkedIn 职位 URL → 自动抓取 JD → AI 定制简历 → 多模板选择 → 导出
- **可借鉴设计**:
  1. **URL 输入即用**: 粘贴 JD 链接即可自动抓取，减少用户操作摩擦
  2. **交互式 CLI**: 提供命令行交互界面，逐步引导用户选择模板和选项
  3. **LangChain 编排**: 使用 LangChain 组织 LLM 调用链

### 5. ResumeSkills — Paramchoudhary/ResumeSkills  
- **GitHub**: https://github.com/Paramchoudhary/ResumeSkills
- **Stars**: ⭐836 | **语言**: Claude Code Plugin
- **核心思路**: Claude Code 的 AI Agent 技能集，用于简历优化、ATS 优化、面试准备、求职策略
- **可借鉴设计**:
  1. **Agent Skill 模式**: 将每个功能设计为独立的"技能"，可组合调用
  2. **Claude Cowork 集成**: 作为 AI 编码助手的插件存在，面向求职者而非开发者

### 6. Career Ops Plugin — andrew-shwetzer/career-ops-plugin
- **GitHub**: https://github.com/andrew-shwetzer/career-ops-plugin
- **Stars**: ⭐406 | **语言**: HTML/JavaScript
- **核心思路**: Claude Cowork 插件，9 个 AI 技能：评估 JD、生成 ATS 优化简历、扫描公司招聘门户、跟踪投递、起草外联邮件
- **可借鉴设计**:
  1. **全流程覆盖**: 从 JD 评估 → 简历生成 → 投递追踪 → 外联邮件，端到端闭环
  2. **通用行业适配**: 声称适用于任何行业

---

## 四、岗位匹配（Job Matching）

### 1. Resume Matcher — srbhr/Resume-Matcher（重复，归类于此）
- 同上。其核心价值在于 **简历与 JD 的相似度计算**，使用向量搜索（vector-search）和词嵌入（word-embeddings）

### 2. FindJobs Agent — he-yufeng/FindJobs-Agent
- **GitHub**: https://github.com/he-yufeng/FindJobs-Agent
- **Stars**: ⭐232 | **语言**: Python/React
- **核心思路**: LLM 驱动的求职工具包——技能分析、AI 面试、简历评分、岗位结构化。自动化技能分类和自适应难度面试。
- **可借鉴设计**:
  1. **技能分类学**: 自动构建专业技能分类体系（taxonomy），将散乱的技能标签组织成层级结构
  2. **自适应难度面试**: 根据回答质量动态调整问题难度
  3. **爬虫 + LLM 岗位分析**: 爬取招聘信息后由 LLM 结构化提取关键需求

### 3. 双向推荐系统 — Shailja-Jindal/Bidirectional-Job-Resume-Recommender-System
- **GitHub**: https://github.com/Shailja-Jindal/Bidirectional-Job-Resume-Recommender-System
- **Stars**: ⭐36 | **语言**: Python
- **核心思路**: 基于 Doc2Vec 的文本内容匹配 + 余弦相似度。求职者可找到匹配岗位，招聘方可找到匹配简历。
- **可借鉴设计**:
  1. **Doc2Vec 嵌入**: 将简历和 JD 映射到同一向量空间中做相似度计算
  2. **双向匹配**: 同一系统同时服务求职者和招聘方

### 4. Smart Career Advisor — Vedang1801/Smart-Career-Advisor
- **GitHub**: https://github.com/Vedang1801/Smart-Career-Advisor
- **Stars**: ⭐8 | **语言**: Python
- **核心思路**: XGBoost ML 模型 (78.14% 准确率)，6000+ 简历-岗位对训练，NLP 技能提取 + GPT-4 简历增强 + 智能岗位匹配
- **可借鉴设计**:
  1. **ML + LLM 混合**: 传统 ML 做快速分类和匹配，LLM 做精细化内容增强
  2. **训练数据集**: 积累简历-岗位配对的标注数据可显著提升匹配准确率

### 5. JobHuntr — lookr-fyi/job-application-bot-by-ollama-ai
- **GitHub**: https://github.com/lookr-fyi/job-application-bot-by-ollama-ai
- **Stars**: ⭐449
- **核心思路**: 端到端求职代理——语义过滤、ATS 优化简历、自动投递、推荐人引荐
- **可借鉴设计**:
  1. **全自动求职管道**: 搜索 → 过滤 → 定制简历 → 回答问题 → 提交申请 → 跟踪，完全自动化
  2. **语义过滤**: 不是简单关键词匹配，而是理解岗位描述语义后决定是否投递
  3. **迭代学习**: 前 10 次需要人工审核，之后可自主运行

---

## 五、数据模型（Data Models）

### 1. JSON Resume 标准
- **GitHub**: https://github.com/jsonresume/resume-schema
- **Stars**: ⭐5,000+
- **核心思路**: 社区驱动的 JSON 简历标准格式，定义了简历的完整 schema
- **被广泛采用**: Reactive Resume、OpenResume、ResuLLMe、OpResume 等均使用或兼容此标准
- **可借鉴设计**:
  1. **标准化数据模型**: 
     - `basics`（基本信息：姓名、邮箱、电话、网站、社交链接）
     - `work`（工作经历：公司、职位、起止日期、描述、亮点）
     - `education`（教育背景）
     - `skills`（技能：名称、等级、关键词列表）
     - `projects`（项目）
     - `certificates`（证书）
     - `languages`（语言能力）
     - `interests`（兴趣爱好）
     - `references`（推荐人）
  2. **扩展性**: schema 允许自定义字段，不破坏互操作性
  3. **工具生态**: 围绕 JSON Resume 有大量解析/渲染/导入导出工具

### 2. 自定义结构化 Profile 设计模式总结

基于以上项目分析，一个理想的"结构化个人画像"应包含：

```
Profile (结构化个人画像)
├── basics (基本信息)
│   ├── name, email, phone, location
│   ├── links[] (LinkedIn, GitHub, 个人网站)
│   └── headline/summary
├── skills[] (技能)
│   ├── name (技能名称)
│   ├── level (熟练度: beginner/intermediate/advanced/expert)
│   ├── category (分类: 编程语言/框架/工具/软技能/领域知识)
│   ├── years_of_experience
│   └── keywords[] (相关关键词，用于匹配)
├── experience[] (工作经历)
│   ├── company, position, start_date, end_date
│   ├── description (Markdown)
│   └── highlights[] (量化成果)
├── education[] (教育背景)
│   ├── institution, degree, field, start_date, end_date
│   └── gpa, highlights
├── projects[] (项目)
│   ├── name, description, url
│   ├── technologies[]
│   └── highlights[]
├── certifications[] (证书)
├── languages[] (语言能力)
└── metadata (元数据)
    ├── last_updated
    ├── version
    └── tags[] (用于分类和检索)
```

**关键设计原则（从以上项目中提炼）**:

1. **数据与渲染分离**: 同一份数据可渲染为多种模板/格式（PDF、HTML、DOCX、Markdown）
2. **Markdown 作为描述字段格式**: 比纯文本更丰富，比富文本更可控，且 LLM 天然擅长生成
3. **技能标签化 + 分类**: 技能不应是自由文本，而应是结构化标签，支持按类别分组和匹配计算
4. **版本管理**: 支持同一份基础数据生成多个"定制版本"（针对不同 JD 的变体）
5. **本地优先 (local-first)**: 数据存本地，隐私可控，离线可用
6. **标准化互操作**: 支持 JSON Resume 导入导出，与生态打通
7. **可扩展自定义区块**: 允许用户添加自定义 section（如出版物、志愿者经历等）

---

## 六、总结：核心技术趋势与可借鉴方向

### 技术栈收敛趋势

| 层次 | 主流选择 | 趋势 |
|------|---------|------|
| 前端 | React/Next.js + Tailwind CSS | TypeScript 全栈成为标配 |
| 后端 | FastAPI (Python) / Node.js | Python 用于 AI 管道，TS 用于 Web 服务 |
| 数据库 | SQLite (轻量) / PostgreSQL (生产) | 双模式：零配置入门 + 可扩展生产 |
| AI/LLM | 多提供商抽象层 (LiteLLM / Vercel AI SDK) | 不绑定单一 LLM，支持 Ollama 本地 + 云端 |
| PDF | Playwright / Puppeteer / LaTeX | 追求排版可控性 |
| 部署 | Docker 一键 | 降低使用门槛 |
| 数据格式 | JSON Resume / YAML / Markdown | 标准化 + 人可读 |

### 核心可借鉴设计决策 Top 10

1. **"主简历 + AI 定制"模式**：用户维护一份完整的主简历，AI 根据 JD 生成针对性版本 —— 解决真实性和定制化的矛盾
2. **Markdown 作为 LLM 与排版的桥梁**：LLM 输出 Markdown（可靠），Pandoc/渲染器转为 DOCX/PDF（美观）
3. **JSON Resume 标准遵循**：采用社区标准 schema，获得生态兼容性
4. **多 ATS 平台差异化评分**：不是单一分数，而是模拟不同 ATS 的评分逻辑
5. **local-first 隐私架构**：浏览器端解析 + 本地存储，文件不上传
6. **多 LLM 提供商抽象**：支持 Ollama 本地免费 + OpenAI/Anthropic 云端高性能
7. **简历管理 + 求职追踪一体化**：Kanban 看板 + 简历版本 + 投递记录
8. **技能标签结构化**：名称 + 等级 + 分类 + 关键词列表，便于匹配计算
9. **拖拽可视化编辑**：dnd-kit 实现直观的区块排序
10. **YAML 作为手写数据源**：比 JSON 更适合人工编辑，再转换为标准格式

### 项目评级速览

| 项目 | Stars | 综合推荐度 | 最值得借鉴 |
|------|-------|----------|----------|
| Resume Matcher | 27K | ⭐⭐⭐⭐⭐ | AI 匹配 + 多 LLM 抽象 |
| Reactive Resume | 39K | ⭐⭐⭐⭐⭐ | 数据模型 + 模板分离 |
| OpenResume | 8.7K | ⭐⭐⭐⭐ | 简历解析 + ATS 测试 |
| JadeAI | 1.8K | ⭐⭐⭐⭐ | AI 功能完整性 |
| ATS Screener | 67 | ⭐⭐⭐⭐ | 多平台评分引擎 |
| Resume AI | 375 | ⭐⭐⭐⭐ | Markdown→DOCX 管道 |
| ResuLLMe | 469 | ⭐⭐⭐ | LaTeX 排版质量 |
| Oh My CV! | 610 | ⭐⭐⭐ | Markdown 极简方案 |
| FindJobs Agent | 232 | ⭐⭐⭐ | 技能分类学 |
| JobHuntr | 449 | ⭐⭐⭐ | 全自动求职管道 |
