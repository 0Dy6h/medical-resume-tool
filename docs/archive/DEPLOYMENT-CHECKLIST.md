# 云服务器部署清单 — 2026-06-18

## 当前线上版本

- **公网地址：** `http://110.42.136.106/`
- **健康检查：** `http://110.42.136.106/health`
- **服务器：** `ubuntu@110.42.136.106`
- **应用路径：** `/opt/medical-resume-tool`
- **服务名：** `medical-resume`
- **已部署提交：** `1aee7126c46fa4720f2074f8a3e058c7d94fe35e`
- **部署记录：** `docs/deployments/tencent-cloud-cvm-2026-06-18/`
- **回滚备份：** `/opt/backups/medical-resume-tool-2026-06-18-213905`

## 本次上线内容

2026-06-18 线上版本包含主开发整改：

- 总览页首次使用路径：稳定 fixture 演示入口 + 私密履历入口。
- 私有岗位工作流状态：每个登录用户可独立保存岗位状态、备注和截止日期。
- 简历生成证据链增强：展示岗位要求、履历来源、证据强度和匹配词。
- 导出安全默认值：面向投递的 DOCX/PDF 默认不包含内部缺口诊断；诊断版需显式选择。
- 兼容旧 SQLite：`profiles` 和 `resume_drafts` 自动迁移到 `user_id` 作用域，无法匹配的旧行保留到 `*_legacy` 表。

## 快速重新部署

```bash
# 本地重新打包
git archive --format=zip -o medical-resume-tool-deploy-2026-06-18.zip HEAD

# 本地上传
scp medical-resume-tool-deploy-2026-06-18.zip ubuntu@110.42.136.106:/tmp/
scp docs/deployments/tencent-cloud-cvm-2026-06-18/deploy.sh ubuntu@110.42.136.106:/tmp/

# 服务器执行
ssh ubuntu@110.42.136.106
bash /tmp/deploy.sh /tmp/medical-resume-tool-deploy-2026-06-18.zip
```

脚本流程：备份 → 解压 → 检查/安装 Tesseract OCR → `uv sync --project backend --all-groups` → `pytest` → `pnpm build` → 重启 `medical-resume` → reload nginx → 健康检查。

## 验证

```bash
curl http://127.0.0.1:8000/health
curl -i http://127.0.0.1:8000/api/profile
curl http://110.42.136.106/health
curl http://110.42.136.106/api/jobs?limit=1
curl http://110.42.136.106/api/analytics/summary
```

期望：

- `/health` 返回 `{"status":"ok"}`。
- 未带 token 的 `/api/profile` 返回 `401`。
- 公网岗位和分析接口返回 200。
- 首页 HTML 引用当前构建出的 `frontend/dist/assets/*` 资源。

## 人工验收

打开 `http://110.42.136.106/`，注册/登录测试账号后检查：

1. 总览页显示“稳定演示入口”和“私密履历入口”。
2. 岗位库可加载岗位，岗位状态控件只影响当前用户。
3. 我的履历可保存或导入结构化事实。
4. 简历生成页展示证据链、缺口和导出入口。
5. 投递版导出不包含内部缺口诊断，诊断版导出需显式选择。

## 回滚

```bash
sudo systemctl stop medical-resume
sudo rm -rf /opt/medical-resume-tool
sudo cp -r /opt/backups/medical-resume-tool-2026-06-18-213905 /opt/medical-resume-tool
sudo chown -R ubuntu:ubuntu /opt/medical-resume-tool
sudo systemctl start medical-resume
```
