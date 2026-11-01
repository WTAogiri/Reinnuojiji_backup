#!/bin/bash
set -e
echo "=========================================="
echo "🌐 正在首尔云服务器 (43.108.90.138) 部署 24h 云端 Chromium + 遥控桥..."
echo "=========================================="

# 1. Merge Chrome bridge routes into cloud gateway
mkdir -p ~/reinhard-gateway
cd ~/reinhard-gateway
curl -sL "https://raw.githubusercontent.com/WTAogiri/Reinnuojiji_backup/main/cloud-gateway/gateway.py" -o ~/reinhard-gateway/base.py
curl -sL "https://raw.githubusercontent.com/WTAogiri/Reinnuojiji_backup/main/cloud-gateway/chrome_patch.py" -o ~/reinhard-gateway/patch.py

python3 -c '
base = open("base.py").read()
patch = open("patch.py").read()
if "/chrome/tabs" not in base:
    chrome_routes = patch.split("@app.get(\"/chrome/tabs\")")[1]
    target = "@app.get(\"/\", response_class=HTMLResponse)"
    merged = base.replace(target, "@app.get(\"/chrome/tabs\")" + chrome_routes + "\n\n" + target)
    open("gateway.py", "w").write(merged)
else:
    open("gateway.py", "w").write(base)
'

sudo systemctl restart reinhard-gateway
echo "✅ 1/2: 云端网关 Chrome 遥控桥 (/chrome/tabs & /chrome/eval) 已激活！"

# 2. Install Docker & launch 24/7 Cloud Chromium if no tunnel is active
if ! command -v docker >/dev/null 2>&1; then
    sudo apt-get update && sudo apt-get install -y docker.io
    sudo systemctl enable --now docker
fi

echo "✅ 2/2: Docker 环境已就绪！"
