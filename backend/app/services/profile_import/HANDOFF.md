# 履历导入优化 - 开发日志

## 2026-06-11 进度

### 已完成：阶段1 + 阶段2（共2个阶段）

#### 阶段1：合同与模型 ✅
**目标**：定义正确的数据合同，扩展 API 响应格式

**改动文件**：
- `backend/app/schemas.py` - 新增 `ReviewItem`, `UnassignedBlock`, `ImportMeta`
- `frontend/src/types.ts` - TypeScript 类型同步
- `backend/app/services/profile_import/__init__.py` - 新模块入口
- `backend/app/services/profile_import/facts.py` - 核心数据结构
- `backend/app/services/profile_import/legacy.py` - 旧解析器重命名
- `backend/app/services/profile_import/adapter.py` - 格式转换适配器
- `backend/app/main.py` - API endpoint 更新使用新合同

**验收**：
- [x] API 返回新字段：`review_items`, `unassigned_blocks`, `import_meta`
- [x] 向后兼容：旧字段仍存在
- [x] 测试通过：10/10

---

#### 阶段2：文本归一化 ✅
**目标**：增强文档提取，支持多种格式，归一化时间和标题

**新增文件**：
- `backend/app/services/profile_import/normalization.py` - 时间/标题/bullet 归一化
- `backend/app/services/profile_import/extraction.py` - 增强的 DOCX/Markdown/PDF 提取
- `backend/tests/test_normalization.py` - 15 个归一化测试
- `backend/tests/test_extraction.py` - 5 个文档提取测试

**核心功能**：
- **时间解析**：支持 `2021.09-2024.06`, `2021-2024`, `2021年9月至2024年6月`, `至今`
- **标题识别**：`一、教育经历`, `1. 教育经历`, `【教育经历】`, `# 教育经历`, `教育经历`
- **Bullet 处理**：识别 `-`, `•`, `*`, `1.` 并与父条目合并
- **DOCX 增强**：识别段落、表格、标题样式
- **Markdown 增强**：识别 `#` 标题、`-` 列表
- **PDF 增强**：使用 `get_text("blocks")` 保留结构

**验收**：
- [x] 多种时间格式归一化
- [x] 多种标题格式识别
- [x] Markdown/DOCX/PDF 结构化提取
- [x] 测试通过：30/30（10 旧 + 15 归一化 + 5 提取）

---

### 当前模块结构

```
backend/app/services/profile_import/
├── __init__.py          # 公共接口
├── facts.py             # 数据结构（DocumentLine, DocumentBlock, ExtractedFact, ProfileImportContract）
├── legacy.py            # 旧解析器（标题切分，阶段3将替换）
├── adapter.py           # 旧格式 → 新合同转换
├── normalization.py     # 文本归一化（时间、标题、bullet）✅ 阶段2
├── extraction.py        # 增强的文档提取（DOCX/Markdown/PDF）✅ 阶段2
└── README.md            # 开发文档

backend/tests/
├── test_profile_import.py   # 原有测试（10个）
├── test_normalization.py    # 归一化测试（15个）✅ 阶段2
└── test_extraction.py        # 文档提取测试（5个）✅ 阶段2
```

---

## 明天计划：阶段3 - 事实抽取器 v1

### 目标
**解决"只能识别教育经历"的核心问题**

### 技术方案

#### 1. 待创建文件
```
backend/app/services/profile_import/
├── extractors.py        # 教育/工作/项目/技能/证书识别器
├── scoring.py           # 置信度评分
└── assembler.py         # 事实合并 → ProfileImportContract

backend/tests/
├── test_extractors.py   # 事实识别测试
└── fixtures/
    └── profile_import/
        ├── plain_unsectioned_resume.txt    # 无标题简历
        ├── medical_experience.txt          # 医疗工作经历
        └── ...
```

#### 2. 核心识别逻辑（extractors.py）

**教育经历识别**：
- 触发词：`大学`, `学院`, `医学部` + `博士`, `硕士`, `本科`, `学士`
- 提取：学校、专业、学历、时间

**工作/实习经历识别**：
- 触发词：`医院`, `中心`, `研究所` + `医师`, `护士`, `科研助理`, `实习生`
- 提取：机构、科室、角色、时间、highlights
- 从 highlights 提取技能（`SPSS`, `伦理`, `随访`）

**项目经历识别**：
- 触发词：`项目`, `课题`, `研究`, `队列`, `平台`
- 提取：项目名、角色、highlights

**技能识别**：
- 词表：`SPSS`, `R语言`, `Python`, `SAS`, `数据清洗`, `统计分析`, `临床研究`, `GCP`, `PCR`, `护理文书`
- 不只从"技能"板块提取，也从工作/项目 highlights 提取

**证书识别**：
- 触发词：`执业医师`, `护士资格证`, `GCP`, `CET-6`, `规范化培训`, `计算机二级`

#### 3. 置信度评分（scoring.py）

```python
基础分 0.4
+ 命中 section 标题 +0.15
+ 命中时间范围 +0.1
+ 命中核心实体 +0.15
+ 命中角色/学历/证书 +0.1
+ 有 bullet/highlight +0.05
- 字段缺失较多 -0.1
- 来源文本过短 -0.1

阈值：
>= 0.75: 自动放入已识别
0.45 - 0.75: 放入待确认（review_items）
< 0.45: 放入未归类（unassigned_blocks）
```

#### 4. 最小可用验收样例

系统必须能从以下**无标题**文本识别出所有事实：

```text
2021.09-2024.06 复旦大学 临床医学 硕士
2023.01-2024.06 上海某三甲医院 临床研究中心 科研助理
参与伦理材料整理、维护随访数据库、使用SPSS完成统计分析
慢病队列随访项目 项目成员 完成300例随访记录核查，输出数据质量报告
已取得GCP证书、大学英语六级
熟悉 Python、R语言、SPSS、数据清洗
```

预期输出：
- education: 1条（复旦大学）
- experiences: 1条（上海某三甲医院，含3个highlights，提取4个技能）
- projects: 1条（慢病队列）
- certificates: 1条（GCP）
- languages: 1条（英语六级）
- skills: 至少6个（Python, R, SPSS, 数据清洗, 伦理材料, 随访）

---

## 技术边界提醒

- **不生成**：不能生成用户资料中没有的事实
- **不自动导入低置信项**：< 0.75 的必须进入 `review_items`，等用户确认
- **保留来源**：每个 `ExtractedFact` 必须有 `source_text`
- **不丢弃未识别内容**：放入 `unassigned_blocks`，让用户能看到

---

## 当前状态

- **测试通过**：30/30 ✅
- **API 兼容**：前后端都能正常工作 ✅
- **模块化完成**：归一化和提取已独立 ✅
- **待实现**：事实抽取器（阶段3）

---

## 运行测试命令

```bash
cd "D:/开发/螃蟹的简历撰写工具/backend"
source .venv/Scripts/activate

# 运行所有导入相关测试
python -m pytest tests/test_profile_import.py tests/test_normalization.py tests/test_extraction.py -v

# 运行单个测试文件
python -m pytest tests/test_normalization.py -v
```

---

## 关键文件位置

- 后端 Schema：`backend/app/schemas.py`
- 前端 Types：`frontend/src/types.ts`
- API Endpoint：`backend/app/main.py` 第199行
- 导入模块：`backend/app/services/profile_import/`
- 测试：`backend/tests/test_*.py`

---

## 明天开始命令

```bash
cd "D:/开发/螃蟹的简历撰写工具"
# 阅读本文件：backend/app/services/profile_import/HANDOFF.md
# 继续：阶段3 - 事实抽取器 v1
```
