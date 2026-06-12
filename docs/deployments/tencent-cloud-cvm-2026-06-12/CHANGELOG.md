# 更新日志 — 2026-06-12

## 版本信息
- **部署日期：** 2026-06-12
- **基线版本：** 3ba5dca (多用户登录)
- **目标版本：** 94d7234 (爬虫优化 + profile_import 重构 + UI 改进)
- **提交数量：** 8 个新提交

## 核心改进

### 1. 爬虫成功率优化 🔥

**背景：** 之前抓取任务常见失败：
- 中国科学院上海药物研究所：SSL: CERTIFICATE_VERIFY_FAILED (self-signed certificate)
- 中国中医科学院：SSL: Hostname mismatch
- 国家卫生健康委科学技术研究所：[Errno 11001] getaddrinfo failed
- 浙江大学医学院：All connection attempts failed

**解决方案：**
- ✅ 禁用 SSL 验证（`verify=False`）— 容忍自签名证书和主机名不匹配
- ✅ 增加重试次数：2 → 3 次
- ✅ 延长超时时间：20s → 30s
- ✅ 优化重试策略：1s 起始 + 指数退避（1s, 2s, 4s）
- ✅ 扩展重试范围：覆盖 TransportError、TimeoutException、HTTPStatusError

**影响文件：**
- `backend/app/config.py` — 默认配置调整
- `backend/app/services/crawler.py` — 重试逻辑增强
- `backend/app/services/adapters/adapter_base.py` — make_client 添加 verify=False
- `backend/app/services/adapters/nfyy.py` — 添加 verify=False
- `backend/app/services/adapters/z2hospital.py` — 添加 verify=False

**期望效果：** 显著降低 SSL 和网络相关的抓取失败率

### 2. profile_import 架构重构

**改动：**
- 从单文件 `profile_import.py` 重构为 `profile_import/` 模块
- 新增 4 个子模块：
  - `extraction.py` — 文本提取（docx/pdf/txt/image）
  - `normalization.py` — 规则解析
  - `adapter.py` — legacy-to-contract 转换
  - `facts.py` — 声明式字段规则

**新契约字段：**
```python
ProfileImportOut(
    ...原有字段...,
    review_items: list[ReviewItem],      # 识别结果供用户预览
    unassigned_blocks: list[UnassignedBlock],  # 未分类的文本块
    import_meta: ImportMeta              # 提取质量元数据
)
```

**好处：**
- 为 PDF/txt/markdown/图片导入做好架构准备
- 清晰的职责分离，易于测试和扩展
- 提供更透明的识别质量反馈

**影响文件：**
- `backend/app/main.py` — 导入端点使用新 API
- `backend/app/schemas.py` — 新增契约类型
- `backend/app/services/profile_import/` — 模块化重构
- `backend/tests/test_extraction.py` — 新增提取层测试
- `backend/tests/test_normalization.py` — 新增规范化测试
- `frontend/src/types.ts` — 同步前端类型

### 3. 前端 API 错误处理改进

**改动：**
- `api.ts` 新增 `errorMessage()` 函数
- 自动解析 FastAPI 的 `detail` 字段（支持字符串和数组）
- 提供更友好的错误提示

**示例：**
```javascript
// 之前：Request failed: 422
// 之后：字段 'username' 必填；字段 'password' 长度不足
```

**影响文件：**
- `frontend/src/lib/api.ts`

### 4. UI 改进

#### 登录页重新设计
- 从居中卡片布局改为左右分栏
- 左侧：品牌标识 + 特性网格（数据库、结构化履历、账号隔离）
- 右侧：登录/注册表单
- 更现代化的配色和间距

**影响文件：**
- `frontend/src/pages/LoginPage.tsx`
- `frontend/src/styles.css`

#### 文件导入 UI 扩展
- 文件选择器 `accept` 从 `.docx` 扩展到 `.docx,.pdf,.txt,.md,.markdown,.png,.jpg,.jpeg,.webp,.bmp,.tif,.tiff`
- 添加 tooltip 说明支持的格式
- 注：后端当前仅处理 docx，其他格式 UI 已准备好但功能未启用

**影响文件：**
- `frontend/src/pages/ProfilePage.tsx`

### 5. 依赖更新

新增后端依赖（为未来功能准备）：
- `pymupdf>=1.24.0` — PDF 文本提取
- `pillow>=10.0.0` — 图片处理
- `pytesseract>=0.3.13` — OCR（需系统安装 Tesseract）

**影响文件：**
- `backend/pyproject.toml`
- `backend/uv.lock`

**注意：** 这些依赖已添加但功能暂未启用，不影响现有功能运行。服务器端会自动安装 pymupdf 和 pillow，pytesseract 仅在启用 OCR 功能时才需要。

### 6. 文档更新

- 更新 `docs/project-principle-diagram.html`：
  - 反映爬虫优化（SSL 容忍、3 次重试）
  - 添加 profile_import 模块化说明
  - 更新技术栈（+ pymupdf）
  - 记录登录页重设计和多格式 UI 支持
- 更新 `README.md` — 同步最新特性
- 更新 `docs/runbook.md` — profile_import 模块路径

## 测试覆盖

**后端测试：** 新增测试文件
- `backend/tests/test_extraction.py` — 文本提取测试
- `backend/tests/test_normalization.py` — 规则解析测试
- 更新 `backend/tests/test_profile_import.py` — 适配新 API

**前端测试：** 类型定义同步，无破坏性变更

## 兼容性说明

### ✅ 数据库兼容
- 无表结构变更
- 无需重置数据库
- 用户数据和岗位数据完全保留

### ✅ API 兼容
- `/api/profile/import` 端点行为向后兼容
- 返回值新增可选字段（`review_items`、`unassigned_blocks`、`import_meta`）
- 前端可无缝升级

### ⚠️ 行为变化
- 爬虫 SSL 验证被禁用（安全性略降，但仅用于公开页面）
- 登录页视觉大幅改版（用户需适应）

## 已知限制

1. **多格式导入：** 前端 UI 已支持，但后端仅处理 docx，选择其他格式会报错
2. **OCR 依赖：** pytesseract 需要系统安装 Tesseract，服务器当前未安装
3. **SSL 安全：** 禁用验证后无法检测中间人攻击，仅适用于爬取公开页面场景

## 回归测试清单

部署后需验证：

- [ ] 登录/注册功能正常
- [ ] 用户数据隔离正常（A 用户看不到 B 用户的履历）
- [ ] 岗位库和分析功能正常
- [ ] 抓取任务成功率提升（特别是之前失败的机构）
- [ ] docx 导入功能正常
- [ ] 简历生成和导出功能正常
- [ ] 登录页新布局显示正常

## 性能影响

- 爬虫重试次数增加，单机构最长等待时间：~9s → ~14s（仅失败时）
- 前端打包体积变化：忽略不计
- 后端依赖增加：~10MB（pymupdf + pillow）

## 安全说明

**SSL 验证禁用的影响：**
- ✅ 仅影响爬虫出站请求（访问医院官网）
- ✅ 不影响用户访问本应用的安全性
- ⚠️ 理论上可能爬取到被篡改的招聘信息（MITM 攻击）
- ⚠️ 实际风险低（目标是公开页面，攻击者动机不足）

**建议：**
- 生产环境可考虑维护受信任机构白名单
- 对高价值机构使用证书固定（certificate pinning）

## 相关链接

- GitHub 仓库：https://github.com/0Dy6h/medical-resume-tool
- 服务器地址：http://110.42.136.106/
- 本次提交范围：3ba5dca..94d7234
