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
# 停止所有已有服务
# ======================
echo ""
echo ">> 停止已有服务..."

# 1. 查找并杀死所有相关 Python 进程
echo "    查找 Python 进程..."
PYTHON_PIDS=$(ps aux | grep -E "python.*app.py|python.*daydayUp" | grep -v grep | awk '{print $2}')
if [ -n "$PYTHON_PIDS" ]; then
    echo "    终止 Python 进程: $PYTHON_PIDS"
    kill -9 $PYTHON_PIDS 2>/dev/null
fi

# 2. 查找并杀死所有相关 Node 进程
echo "    查找 Node 进程..."
NODE_PIDS=$(ps aux | grep -E "node.*dev|vite" | grep -v grep | awk '{print $2}')
if [ -n "$NODE_PIDS" ]; then
    echo "    终止 Node 进程: $NODE_PIDS"
    kill -9 $NODE_PIDS 2>/dev/null
fi

# 3. 查找占用 5001 端口的进程
echo "    检查端口 5001..."
PORT_5001_PID=$(lsof -ti :5001 2>/dev/null)
if [ -n "$PORT_5001_PID" ]; then
    echo "    终止占用 5001 端口的进程: $PORT_5001_PID"
    kill -9 $PORT_5001_PID 2>/dev/null
    sleep 1
fi

# 4. 查找占用 5173 端口的进程
echo "    检查端口 5173..."
PORT_5173_PID=$(lsof -ti :5173 2>/dev/null)
if [ -n "$PORT_5173_PID" ]; then
    echo "    终止占用 5173 端口的进程: $PORT_5173_PID"
    kill -9 $PORT_5173_PID 2>/dev/null
    sleep 1
fi

# 5. 再次检查确保端口释放
FINAL_PID=$(lsof -ti :5001 2>/dev/null)
if [ -n "$FINAL_PID" ]; then
    echo "    ⚠ 端口仍被占用，强制终止: $FINAL_PID"
    kill -9 $FINAL_PID 2>/dev/null
    sleep 1
fi

echo "    ✓ 已停止所有服务"

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

# 关闭 debug 模式避免自动重启导致多进程问题
export FLASK_ENV=production
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
echo "  后端 PID: $BACKEND_PID"
echo "  前端 PID: $FRONTEND_PID"
echo ""
echo "  按 Ctrl+C 停止所有服务"
echo "=================================="

# 等待用户中断
cleanup() {
    echo ""
    echo ">> 正在停止服务..."
    kill -9 $BACKEND_PID $FRONTEND_PID 2>/dev/null
    echo "    ✓ 所有服务已停止"
    exit
}
trap cleanup INT
wait
