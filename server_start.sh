#!/bin/bash
# 服务器启动脚本 - 后台执行，无debug日志，日志大小限制100M

USER="c646860306"
PASS="Jxh646860306."
BACKEND_DIR="/home/$USER/daydayup_backend"
LOG_DIR="/home/$USER/logs"

echo "=================================="
echo "  服务器启动脚本"
echo "=================================="

# 创建日志目录
echo ""
echo ">> 创建日志目录..."
sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no $USER@192.168.31.123 "mkdir -p $LOG_DIR"

# 配置日志轮转 (100M) - 简单版
echo ">> 配置日志轮转 (100M)..."
sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no $USER@192.168.31.123 "
# 创建日志轮转脚本
cat > /tmp/rotate_logs.sh << 'SCRIPT'
#!/bin/bash
LOG_DIR='/home/c646860306/logs'
MAX_SIZE=104857600  # 100MB

for logfile in \$LOG_DIR/backend_*.log; do
    if [ -f \"\$logfile\" ]; then
        size=\$(stat -f%z \"\$logfile\" 2>/dev/null || stat -c%s \"\$logfile\" 2>/dev/null)
        if [ \"\$size\" -gt \$MAX_SIZE ]; then
            mv \"\$logfile\" \"\$logfile.\$(date +%Y%m%d%H%M%S)\"
            touch \"\$logfile\"
            gzip \"\$logfile.\"* &
        fi
    fi
done
SCRIPT
chmod +x /tmp/rotate_logs.sh

# 添加到 crontab 每小时检查
(crontab -l 2>/dev/null | grep -v rotate_logs; echo '0 * * * * /tmp/rotate_logs.sh') | crontab - 2>/dev/null || true

# 立即执行一次日志轮转
/tmp/rotate_logs.sh

echo '    ✓ 日志轮转已配置'
"

# 创建虚拟环境并安装依赖（如果不存在）
echo ""
echo ">> 检查并创建虚拟环境..."
sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no $USER@192.168.31.123 "
    cd $BACKEND_DIR
    
    # 如果虚拟环境不存在或有问题，重新创建
    # （可能是本地虚拟环境上传的，shebang 指向错误路径）
    if [ ! -d 'venv' ] || ! $BACKEND_DIR/venv/bin/python --version &>/dev/null; then
        echo '    删除旧虚拟环境...'
        rm -rf venv
        echo '    创建新虚拟环境...'
        python3 -m venv venv
    fi
    
    # 使用虚拟环境的 pip 安装依赖（绝对路径，避免 PEP 668 限制）
    # 使用阿里云镜像源
    if [ -f 'requirements.txt' ]; then
        echo '    安装依赖...'
        $BACKEND_DIR/venv/bin/pip install -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt
    fi
    
    echo '    ✓ 环境准备完成'
"

# 停止已有服务
echo ""
echo ">> 检查并停止已有服务..."
sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no $USER@192.168.31.123 "
    # 强制杀死所有相关进程
    pkill -9 -f 'gunicorn.*app' 2>/dev/null || true
    pkill -9 -f 'python.*app.py' 2>/dev/null || true
    sleep 2
    
    # 检查端口是否被占用，循环等待释放
    for i in {1..10}; do
        if lsof -i:5000 &>/dev/null; then
            echo '    端口 5000 被占用，尝试释放...'
            fuser -k 5000/tcp 2>/dev/null || true
            sleep 1
        else
            echo '    ✓ 端口 5000 已释放'
            break
        fi
    done
    
    # 最后确认一次
    if lsof -i:5000 &>/dev/null; then
        echo '    ⚠ 端口仍被占用，强制杀死进程...'
        fuser -k -9 5000/tcp 2>/dev/null || true
        sleep 2
    fi
    
    echo '    ✓ 已停止已有服务'
"

# 启动后端
echo ""
echo ">> 启动后端服务..."
sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no $USER@192.168.31.123 "
    cd $BACKEND_DIR
    
    # 使用虚拟环境的 gunicorn 启动（绝对路径）
    # -w 4 workers
    # --log-level info: gunicorn 自身日志级别
    # --capture-output: 捕获 worker 的 stdout/stderr 到日志文件
    # --timeout 300: 请求超时时间 300秒（避免数据同步超时）
    # --graceful-timeout 30: 优雅关闭超时时间
    nohup $BACKEND_DIR/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 \
        --log-level info \
        --capture-output \
        --timeout 300 \
        --graceful-timeout 30 \
        --log-file $LOG_DIR/backend_error.log \
        --access-logfile $LOG_DIR/backend_access.log \
        app:app &
    
    sleep 2
    if curl -s http://127.0.0.1:5000 > /dev/null 2>&1; then
        echo '    ✓ 后端启动成功'
    else
        echo '    ✗ 后端启动失败，请查看日志'
    fi
"

echo ""
echo "=================================="
echo "  服务启动完成"
echo "=================================="
echo "  后端: http://192.168.31.123:5000"
echo "  日志: $LOG_DIR/"
echo "=================================="
