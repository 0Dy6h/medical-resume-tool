# 履历导入模块重构

## 当前状态（阶段2完成）

### ✅ 已完成：合同与模型（阶段1）

1. **新数据结构** (`facts.py`)
   - `DocumentLine`: 文档行，保留来源位置
   - `DocumentBlock`: 语义块
   - `ExtractedFact`: 识别出的履历事实（带置信度和来源）
   - `ProfileImportContract`: 导入预览合同

2. **扩展的 API 响应** (`schemas.py`, `types.ts`)
   - 保留原有字段：`education`, `experiences`, `projects` 等
   - 新增字段：
     - `review_items`: 待用户确认的低置信事实
     - `unassigned_blocks`: 未归类的文本块
     - `import_meta`: 解析元信息（文件类型、提取器、文本质量）
     - `warnings`: 警告信息

3. **模块化结构**
   ```
   backend/app/services/profile_import/
   ├── __init__.py          # 公共接口
   ├── facts.py             # 数据结构
   ├── legacy.py            # 旧解析器（重命名自 profile_import.py）
   ├── adapter.py           # 适配器：旧格式 → 新合同
   ├── normalization.py     # 文本归一化
   ├── extraction.py        # 增强的文档提取
   └── README.md            # 文档
   ```

### ✅ 已完成：文本归一化（阶段2）

1. **时间范围解析** (`normalization.py`)
   - 支持多种格式：`2021.09-2024.06`、`2021-2024`、`2021年9月至2024年6月`
   - 支持"至今"、"现在"
   - 归一化为统一格式：`YYYY.MM` 或 `YYYY`

2. **标题识别**
   - 中文序号：`一、教育经历`、`二. 工作经历`
   - 阿拉伯数字：`1. 教育经历`、`2）工作经历`
   - 方括号：`【教育经历】`
   - Markdown：`# 教育经历`、`## 工作经历`
   - 纯文本标题：`教育经历`

3. **Bullet 处理**
   - 识别并去除 bullet 标记：`-`、`•`、`*`、`1.`
   - 将连续 bullet 与父条目合并成块

4. **增强的文档提取** (`extraction.py`)
   - **DOCX**: 识别段落、表格、标题样式
   - **Markdown**: 识别 `#` 标题、`-` 列表、段落
   - **PDF**: 使用 `get_text("blocks")` 而非纯文本，保留位置信息

5. **测试覆盖**
   - 15 个归一化测试 ✓
   - 5 个文档提取测试 ✓
   - 10 个原有导入测试 ✓
   - **总计 30 个测试全部通过**

### 验收标准

- [x] 时间范围支持多种格式并归一化
- [x] 标题识别不依赖单一格式
- [x] Markdown 文件能识别标题和列表
- [x] DOCX 表格能正确提取
- [x] PDF 使用 blocks 提取保留结构
- [x] 所有测试通过（30/30）

## 下一步：阶段3 - 事实抽取器 v1

目标：解决"只能识别教育经历"的核心问题

计划改动：
- `extractors.py`: 工作/实习/项目/技能/证书/论文识别
- `sectioning.py`: 板块识别（不唯一依赖）
- `scoring.py`: 置信度评分
- `assembler.py`: 事实合并与合同生成
- 测试：无标题文本识别验收样例

关键点：
- 不只依赖板块标题
- 从文本特征识别事实类型
- 每个事实保留 `source_text` 和 `confidence`
- 未识别内容不丢弃

## 技术债务

- [ ] `legacy.py` 仍然依赖标题切分（阶段3会替换）
- [ ] OCR 仍使用 Tesseract（计划换成 RapidOCR）
- [ ] 没有事实抽取器（教育经历之外的识别率低）← **阶段3目标**
