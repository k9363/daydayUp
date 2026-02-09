@echo off
REM Flask后端启动脚本 (Windows)

REM 进入后端目录
cd /d "%~dp0"

REM 检查并创建虚拟环境
if not exist venv (
    echo 创建虚拟环境...
    python -m venv venv
)

REM 激活虚拟环境
call venv\Scripts\activate.bat

REM 安装依赖
echo 安装Python依赖...
pip install -r requirements.txt

REM 复制环境变量文件
if not exist .env (
    copy .env.example .env
    echo 请编辑 .env 文件配置数据库连接
)

REM 初始化数据库
echo 初始化数据库...
python init_db.py

REM 启动服务
echo 启动Flask服务...
python app.py

