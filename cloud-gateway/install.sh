#!/bin/bash
set -e
mkdir -p ~/reinhard-gateway
cd ~/reinhard-gateway
if [ ! -d "venv" ]; then
  python3 -m venv venv
  ./venv/bin/pip install fastapi uvicorn httpx websockets
fi
curl -sL "https://raw.githubusercontent.com/WTAogiri/Reinnuojiji_backup/main/cloud-gateway/gateway.py" -o ~/reinhard-gateway/gateway.py

sudo tee /etc/systemd/system/reinhard-gateway.service > /dev/null <<EOF
[Unit]
Description=Reinhard 24/7 Cloud Hub Gateway
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME/reinhard-gateway
ExecStart=$HOME/reinhard-gateway/venv/bin/uvicorn gateway:app --host 0.0.0.0 --port 8788
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable reinhard-gateway
sudo systemctl restart reinhard-gateway
echo "=========================================="
echo "⚔️ 莱茵哈鲁特 · 24h云端粮草总管已成功启动！"
echo "🌐 永久管理看板与API网关地址："
echo "👉 http://43.108.90.138:8788"
echo "=========================================="
