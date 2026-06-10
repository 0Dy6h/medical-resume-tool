#!/bin/bash
# 医疗岗位简历工具 - 一键部署脚本

set -e
echo "=== 开始部署 ==="

# 1. 安装依赖
echo "📦 安装系统依赖..."
apt-get update
apt-get install -y python3.11 python3.11-venv python3-pip nodejs npm git nginx

# 2. 克隆代码
echo "📥 拉取代码..."
cd /opt
git clone https://github.com/0Dy6h/medical-resume-tool.git
cd medical-resume-tool

# 3. 后端部署
echo "🐍 部署后端..."
cd backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. 前端构建
echo "⚛️ 构建前端..."
cd ../frontend
npm install
npm run build

# 5. 配置 Nginx
echo "🌐 配置 Nginx..."
cat > /etc/nginx/sites-available/medical-resume <<'EOF'
server {
    listen 80;
    server_name _;

    # 前端
    location / {
        root /opt/medical-resume-tool/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # 后端 API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /health {
        proxy_pass http://127.0.0.1:8000;
    }
}
EOF

ln -sf /etc/nginx/sites-available/medical-resume /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# 6. 配置后端服务
echo "🚀 配置后端服务..."
cat > /etc/systemd/system/medical-resume.service <<EOF
[Unit]
Description=Medical Resume Tool Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/medical-resume-tool/backend
Environment="PATH=/opt/medical-resume-tool/backend/venv/bin"
ExecStart=/opt/medical-resume-tool/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable medical-resume
systemctl start medical-resume

echo "✅ 部署完成！"
echo "访问地址: http://$(curl -s ifconfig.me)"
echo "后端健康检查: http://$(curl -s ifconfig.me)/health"
