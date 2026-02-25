#!/bin/bash

# 部署脚本 - 在服务器上执行

echo "=== 开始部署 daydayup ==="

# 1. 构建前端
echo ">>> 构建前端..."
cd frontend
npm run build
cd ..

# 2. 复制前端构建文件
echo ">>> 复制前端构建文件..."
rm -rf frontend/dist/assets/*.css frontend/dist/assets/*.js
cp -r frontend/dist/* ./dist_temp/

# 3. 使用 docker-compose 构建并启动
echo ">>> 构建并启动 Docker 容器..."
docker-compose up -d --build

echo "=== 部署完成 ==="
echo "服务地址: http://服务器IP"
echo "API地址: http://服务器IP/api"
