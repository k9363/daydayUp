#!/bin/bash
# 服务器关闭脚本

USER="c646860306"
PASS="Jxh646860306."
SERVER="192.168.31.123"
LOG_DIR="/home/$USER/logs"

echo "=================================="
echo "  服务器关闭脚本"
echo "=================================="

echo ""
echo ">> 关闭后端服务 (gunicorn)..."
sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no $USER@$SERVER "
    pkill -f 'gunicorn.*app' 2>/dev/null && echo '    ✓ gunicorn 已停止' || echo '    ✓ 无运行中的 gunicorn'
    sleep 1
"

echo ""
echo "=================================="
echo "  后端服务已关闭"
echo "  (nginx 保持运行)"
echo "=================================="
