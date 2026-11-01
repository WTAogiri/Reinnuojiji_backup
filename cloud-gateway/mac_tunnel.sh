#!/bin/bash
echo "=========================================="
echo "🌉 正在打通 MacBook -> 首尔云服务器 (43.108.90.138) 永久隧道..."
echo "=========================================="

# Kill old local tunnels ONLY by matching the port forward flag, never matching our own command!
pkill -f "8787:127.0.0.1:8787" 2>/dev/null || true

# Keep Mac awake
caffeinate -dimsu &

while true; do
  echo "👉 请输入一次云服务器密码："
  ssh -o ServerAliveInterval=15 -o ServerAliveCountMax=3 \
    -R 0.0.0.0:8787:127.0.0.1:8787 -R 127.0.0.1:9223:127.0.0.1:9223 root@43.108.90.138 \
    "echo '✅ 隧道已100%连通！保持这个窗口别关，快去睡觉吧宝宝！'; while true; do sleep 60; done"
  echo "⚠️ 隧道断开，3秒后自动重连..."
  sleep 3
done
