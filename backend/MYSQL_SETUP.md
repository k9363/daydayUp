# MySQL 数据库初始化说明

## 1. 创建数据库

请确保 MySQL 服务已启动，然后执行以下命令创建数据库和表：

```bash
# 登录 MySQL
mysql -u root -p

# 执行初始化脚本
source /Users/jxh/Public/gugu/daydayUp/backend/schema_mysql.sql
```

或者直接在命令行执行：

```bash
mysql -u root -p < /Users/jxh/Public/gugu/daydayUp/backend/schema_mysql.sql
```

## 2. 配置环境变量

创建 `.env` 文件（从 backend 目录）：

```bash
cd /Users/jxh/Public/gugu/daydayUp/backend
cp .env.example .env
```

然后编辑 `.env` 文件，修改 MySQL 连接配置：

```env
# 数据库配置 (MySQL)
DB_TYPE=mysql
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password  # 修改为你的 MySQL 密码
DB_NAME=daydayup

# 其他配置
SECRET_KEY=your-secret-key-change-in-production
DEBUG=True

# 文件上传配置
UPLOAD_FOLDER=uploads
MAX_CONTENT_LENGTH=52428800
```

## 3. 安装依赖并启动

```bash
# 安装 Python 依赖
pip install -r requirements.txt

# 初始化数据库表
python init_db.py

# 启动后端服务
python app.py
```

## 4. 默认数据库配置

- 数据库名: `daydayup`
- 用户名: `root`
- 密码: `password` (请根据实际情况修改)
- 主机: `localhost`
- 端口: `3306`

## 注意事项

1. 确保 MySQL 服务已启动
2. 确保创建的数据库用户有足够的权限
3. 如果使用其他数据库用户，请相应修改 `.env` 文件
4. MySQL 8.0+ 需要确保密码认证方式兼容（或者使用 `mysql_native_password`）

