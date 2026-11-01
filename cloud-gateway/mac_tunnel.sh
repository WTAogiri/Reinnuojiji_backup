#!/bin/bash
set -e
echo "=========================================="
echo "🌉 正在打通 MacBook -> 首尔云服务器 (43.108.90.138) 永久隧道..."
echo "（把 Mac 的 8787 Aru Host 与 9223 专属 Chrome 映射到云端）"
echo "=========================================="

# Keep Mac awake
caffeinate -dimsu &

# Establish persistent SSH reverse tunnel to 43.108.90.138
# -R 0.0.0.0:8787:127.0.0.1:8787 -> Aru Host
# -R 127.0.0.1:9223:127.0.0.1:9223 -> Reinhard's Chrome for Cloud Gateway
while true; do
  ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes \
    -N -R 0.0.0.0:8787:127.0.0.1:8787 -R 127.0.0.1:9223:127.0.0.1:9223 root@43.108.90.138
  echo "⚠️ 隧道断开，3秒后自动重连..."
  sleep 3
done
