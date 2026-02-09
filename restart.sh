#!/bin/bash
# ============================================================================
# DayDayUp 服务重启脚本
# ============================================================================
# 功能: 重启后端和前端服务
# ============================================================================

# 获取项目根目录
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}>> $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# ============================================================================
# 查找并停止进程
# ============================================================================
stop_service() {
    local service_name=$1
    local process_pattern=$2
    
    print_info "停止 $service_name 服务..."
    
    # 查找进程
    local pids=$(pgrep -f "$process_pattern" 2>/dev/null)
    
    if [ -n "$pids" ]; then
        for pid in $pids; do
            print_info "  终止进程 PID: $pid"
            kill -9 $pid 2>/dev/null
        done
        print_success "$service_name 已停止"
    else
        print_warning "$service_name 未运行"
    fi
}

# ============================================================================
# 停止所有服务
# ============================================================================
stop_all() {
    echo ""
    echo "=================================="
    echo "  停止服务"
    echo "=================================="
    
    # 停止后端服务
    stop_service "后端服务 (Flask)" "python.*app.py"
    stop_service "后端服务 (Flask)" "flask.*app.py"
    
    # 停止前端服务
    stop_service "前端服务 (Vite)" "vite"
    stop_service "前端服务 (Node)" "npm.*dev"
    
    # 查找可能遗漏的进程
    stop_service "其他相关进程" "daydayup"
    
    echo ""
}

# ============================================================================
# 启动服务
# ============================================================================
start_backend() {
    print_info "启动后端服务..."
    
    cd "$BACKEND_DIR"
    
    # 检查虚拟环境
    if [ ! -d "venv" ]; then
        print_warning "未找到虚拟环境，创建中..."
        python3 -m venv venv
    fi
    
    # 激活虚拟环境
    source venv/bin/activate
    
    # 安装依赖
    print_info "检查Python依赖..."
    pip install -r requirements.txt -q 2>/dev/null
    
    # 启动后端
    print_info "启动 Flask 服务..."
    python app.py &
    BACKEND_PID=$!
    
    echo $BACKEND_PID > "$BACKEND_DIR/.backend_pid"
    print_success "后端已启动 (PID: $BACKEND_PID)"
    
    # 等待服务启动
    sleep 3
    
    # 检查服务是否正常运行
    if kill -0 $BACKEND_PID 2>/dev/null; then
        print_success "后端服务运行正常"
    else
        print_error "后端服务启动失败"
        return 1
    fi
}

start_frontend() {
    print_info "启动前端服务..."
    
    cd "$FRONTEND_DIR"
    
    # 安装npm依赖
    if [ ! -d "node_modules" ]; then
        print_warning "未找到 node_modules，安装中..."
        npm install
    fi
    
    # 启动前端
    print_info "启动 Vite 开发服务器..."
    npm run dev &
    FRONTEND_PID=$!
    
    echo $FRONTEND_PID > "$FRONTEND_DIR/.frontend_pid"
    print_success "前端已启动 (PID: $FRONTEND_PID)"
    
    # 等待服务启动
    sleep 3
    
    # 检查服务是否正常运行
    if kill -0 $FRONTEND_PID 2>/dev/null; then
        print_success "前端服务运行正常"
    else
        print_error "前端服务启动失败"
        return 1
    fi
}

start_all() {
    echo ""
    echo "=================================="
    echo "  启动服务"
    echo "=================================="
    
    # 启动后端
    start_backend
    if [ $? -ne 0 ]; then
        print_error "后端启动失败，退出"
        exit 1
    fi
    
    # 启动前端
    start_frontend
    if [ $? -ne 0 ]; then
        print_error "前端启动失败"
        exit 1
    fi
    
    echo ""
    echo "=================================="
    echo "  服务已全部启动"
    echo "=================================="
    echo -e "  ${GREEN}后端: http://localhost:5001${NC}"
    echo -e "  ${GREEN}前端: http://localhost:5173${NC}"
    echo ""
    echo "  按 Ctrl+C 停止所有服务"
    echo "=================================="
}

# ============================================================================
# 重启服务
# ============================================================================
restart() {
    echo ""
    echo "=================================="
    echo "  DayDayUp 服务重启脚本"
    echo "=================================="
    
    # 先停止所有服务
    stop_all
    
    # 等待片刻
    print_info "等待服务完全停止..."
    sleep 2
    
    # 启动所有服务
    start_all
}

# ============================================================================
# 仅停止
# ============================================================================
stop_only() {
    stop_all
}

# ============================================================================
# 仅启动
# ============================================================================
start_only() {
    start_all
}

# ============================================================================
# 查看状态
# ============================================================================
status() {
    echo ""
    echo "=================================="
    echo "  服务状态"
    echo "=================================="
    
    # 检查后端
    local backend_pid=$(cat "$BACKEND_DIR/.backend_pid" 2>/dev/null)
    if [ -n "$backend_pid" ] && kill -0 $backend_pid 2>/dev/null; then
        echo -e "  ${GREEN}✓ 后端服务运行中 (PID: $backend_pid)${NC}"
    else
        echo -e "  ${RED}✗ 后端服务未运行${NC}"
    fi
    
    # 检查前端
    local frontend_pid=$(cat "$FRONTEND_DIR/.frontend_pid" 2>/dev/null)
    if [ -n "$frontend_pid" ] && kill -0 $frontend_pid 2>/dev/null; then
        echo -e "  ${GREEN}✓ 前端服务运行中 (PID: $frontend_pid)${NC}"
    else
        echo -e "  ${RED}✗ 前端服务未运行${NC}"
    fi
    
    echo ""
    
    # 检查端口占用
    echo "  端口占用情况:"
    lsof -i :5001 2>/dev/null | grep -v COMMAND | awk '{print "    后端(5001):", $9}' | head -1 || echo "    后端(5001): 未占用"
    lsof -i :5173 2>/dev/null | grep -v COMMAND | awk '{print "    前端(5173):", $9}' | head -1 || echo "    前端(5173): 未占用"
    
    echo ""
}

# ============================================================================
# 显示帮助
# ============================================================================
show_help() {
    echo ""
    echo "用法: $0 [命令]"
    echo ""
    echo "命令:"
    echo "  restart   重启所有服务 (默认)"
    echo "  start     仅启动服务"
    echo "  stop      仅停止服务"
    echo "  status    查看服务状态"
    echo "  help      显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0              # 重启所有服务"
    echo "  $0 start        # 启动服务"
    echo "  $0 stop         # 停止服务"
    echo "  $0 status       # 查看状态"
    echo ""
}

# ============================================================================
# 主程序
# ============================================================================
main() {
    # 默认命令
    command=${1:-restart}
    
    case $command in
        restart)
            restart
            ;;
        start)
            start_only
            ;;
        stop)
            stop_only
            ;;
        status)
            status
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "未知命令: $command"
            show_help
            exit 1
            ;;
    esac
}

# 等待用户中断
trap "echo ''; echo '正在停止服务...'; stop_all; exit" INT

main "$@"
wait

