#!/bin/bash
# 数据库初始化脚本
# 使用方法: ./init_db.sh [mysql_password]

set -e

MYSQL_PASSWORD=${1:-""}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=================================="
echo "  DayDayUp 数据库初始化脚本"
echo "=================================="
echo ""

# 读取 .env 配置
if [ -f "$PROJECT_ROOT/backend/.env" ]; then
    source "$PROJECT_ROOT/backend/.env"
    echo ">> 已加载 .env 配置"
else
    echo ">> 未找到 .env 文件，请先配置数据库连接信息"
    echo "   请复制 .env.example 为 .env 并填写密码"
    echo ""
    echo "   cp backend/.env.example backend/.env"
    echo "   vi backend/.env"
    exit 1
fi

# 检查 MySQL 命令行工具
if ! command -v mysql &> /dev/null; then
    echo "错误: 未找到 mysql 命令，请安装 MySQL 客户端"
    exit 1
fi

# 创建数据库
echo ""
echo ">> 创建数据库 daydayup..."
mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASSWORD" << EOF
CREATE DATABASE IF NOT EXISTS daydayup DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
EOF
echo "   数据库创建成功!"

# 执行 schema.sql
echo ""
echo ">> 创建数据表..."
mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASSWORD" daydayup < "$SCRIPT_DIR/schema.sql"
echo "   数据表创建成功!"

echo ""
echo "=================================="
echo "  数据库初始化完成!"
echo "=================================="
echo "  数据库名: $DB_NAME"
echo "  用户名: $DB_USER"
echo "  主机: $DB_HOST:$DB_PORT"
echo "=================================="

