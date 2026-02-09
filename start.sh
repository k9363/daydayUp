#!/bin/bash
# 全栈启动脚本 - 同时启动前后端

# 获取项目根目录
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

echo "=================================="
echo "  DayDayUp 全栈启动脚本"
echo "=================================="

# ======================
# 后端设置
# ======================
echo ""
echo ">> 检查后端环境..."
cd "$BACKEND_DIR"

# 检查并创建虚拟环境
if [ ! -d "venv" ]; then
    echo "    创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境并安装依赖
source venv/bin/activate
echo "    安装Python依赖..."
pip install -r requirements.txt -q

# ======================
# 前端设置
# ======================
echo ""
echo ">> 检查前端环境..."
cd "$FRONTEND_DIR"

# 检查并安装npm依赖
if [ ! -d "node_modules" ]; then
    echo "    安装npm依赖..."
    npm install
fi

# ======================
# 启动服务
# ======================
echo ""
echo ">> 启动后端服务..."
cd "$BACKEND_DIR"
source venv/bin/activate
python app.py &
BACKEND_PID=$!
echo "    后端已启动 (PID: $BACKEND_PID)"

echo ""
echo ">> 启动前端服务..."
cd "$FRONTEND_DIR"
npm run dev &
FRONTEND_PID=$!
echo "    前端已启动 (PID: $FRONTEND_PID)"

echo ""
echo "=================================="
echo "  服务已启动"
echo "=================================="
echo "  后端: http://localhost:5001"
echo "  前端: http://localhost:5173"
echo ""
echo "  按 Ctrl+C 停止所有服务"
echo "=================================="

# 等待用户中断
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT
wait
