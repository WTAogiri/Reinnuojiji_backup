#!/bin/bash
set -e
echo "=========================================="
echo "🌉 正在打通 MacBook -> 首尔云服务器 (43.108.90.138) 永久隧道..."
echo "=========================================="

# Kill any existing local ssh tunnel to 43.108.90.138
pkill -f "43.108.90.138" 2>/dev/null || true

# Keep Mac awake
caffeinate -dimsu &

# Single SSH connection: first clean up any zombie sshd port 8787 on VPS, then hold tunnel open
while true; do
  echo "👉 请输入一次云服务器密码（连接成功后会显示『✅ 隧道已连通』并保持安静）："
  ssh -o ServerAliveInterval=15 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes \
    -R 0.0.0.0:8787:127.0.0.1:8787 -R 127.0.0.1:9223:127.0.0.1:9223 root@43.108.90.138 \
    "fuser -k 8787/tcp 2>/dev/null || true; echo '✅ 隧道已100%连通！请保持此窗口最小化，快去睡觉吧宝宝！'; tail -f /dev/null"
  echo "⚠️ 隧道断开，3秒后自动重连..."
  sleep 3
done
