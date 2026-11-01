#!/bin/bash
set -e
mkdir -p ~/reinhard-gateway
cd ~/reinhard-gateway
curl -sL "https://raw.githubusercontent.com/WTAogiri/Reinnuojiji_backup/main/cloud-gateway/gateway.py" -o ~/reinhard-gateway/base.py
curl -sL "https://raw.githubusercontent.com/WTAogiri/Reinnuojiji_backup/main/cloud-gateway/chrome_patch.py" -o ~/reinhard-gateway/patch.py

python3 -c '
base = open("base.py").read()
patch = open("patch.py").read()
chrome_routes = patch.split("@app.get(\"/chrome/tabs\")")[1]
target = "@app.get(\"/\", response_class=HTMLResponse)"
merged = base.replace(target, "@app.get(\"/chrome/tabs\")" + chrome_routes + "\n\n" + target)
open("gateway.py", "w").write(merged)
'

sudo systemctl restart reinhard-gateway
echo "✅ 云端网关已加入 Chrome 遥控桥！"
