#!/bin/bash
set -e
echo "=========================================="
echo "🔒 正在为 43.108.90.138 自动配置 HTTPS (Caddy) 网关..."
echo "=========================================="
sudo apt update && sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl caddy

sudo tee /etc/caddy/Caddyfile > /dev/null <<EOF
https://43-108-90-138.sslip.io {
    reverse_proxy 127.0.0.1:8787
}

https://43-108-90-138.sslip.io:8443 {
    reverse_proxy 127.0.0.1:8788
}
EOF

sudo systemctl enable caddy
sudo systemctl restart caddy
echo "=========================================="
echo "✅ HTTPS 证书已自动签发完成！"
echo "👉 请在 Mac 节点设置 (HTTPS) 填入："
echo "https://43-108-90-138.sslip.io"
echo "=========================================="
