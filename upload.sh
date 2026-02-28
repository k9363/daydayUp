#!/bin/bash
# 上传代码到服务器脚本

SERVER="192.168.31.123"
PORT="22"
USER="c646860306"
PASS="Jxh646860306."

echo "=================================="
echo "  上传代码到服务器"
echo "=================================="

# 获取项目根目录
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

echo ""
echo ">> 检查服务器目录..."
# 先在服务器上创建目标目录
expect -c "
set timeout 30
spawn ssh -o StrictHostKeyChecking=no $USER@$SERVER \"mkdir -p /home/$USER/daydayup_backend /home/$USER/daydayup_frontend\"
expect {
    \"password:\" {
        send \"$PASS\r\"
        expect eof
    }
}
" 2>&1
echo "    ✓ 目录检查完成"

echo ""
echo ">> 上传后端代码..."
# 使用 rsync 同步（更可靠，不会遗漏新文件）
expect -c "
set timeout 300
spawn rsync -avz --exclude='__pycache__' --exclude='*.pyc' --exclude='.git' --exclude='venv' --exclude='env' --exclude='*.log' --exclude='.env' $BACKEND_DIR/ $USER@$SERVER:/home/$USER/daydayup_backend/
expect {
    \"password:\" {
        send \"$PASS\r\"
        expect eof
    }
}
" 2>&1
echo "    ✓ 后端上传完成"

echo ""
echo ">> 上传前端代码..."
# 先构建前端
cd $FRONTEND_DIR
npm run build

# 使用 rsync 同步构建后的文件
expect -c "
set timeout 300
spawn rsync -avz $FRONTEND_DIR/dist/ $USER@$SERVER:/home/$USER/daydayup_frontend/
expect {
    \"password:\" {
        send \"$PASS\r\"
        expect eof
    }
}
" 2>&1
echo "    ✓ 前端上传完成"

echo ""
echo "=================================="
echo "  代码上传完成"
echo "=================================="
