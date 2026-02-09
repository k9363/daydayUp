#!/bin/bash
# Flask后端启动脚本

# 进入后端目录
cd "$(dirname "$0")"

# 检查并创建虚拟环境
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
echo "安装Python依赖..."
pip install -r requirements.txt

# 复制环境变量文件
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "请编辑 .env 文件配置数据库连接"
fi

# 启动服务
echo "启动Flask服务..."
python app.py

