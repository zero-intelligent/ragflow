#!/bin/bash
set -e  # 如果任意命令出错，脚本将立即退出

# 要执行的 Python 脚本路径
APP_HOME=$(dirname "$0")
cd "$APP_HOME"
source .venv/bin/activate

# 编译前端
npm i --force && npm run build


OLD_VERSION=dev4
NEW_VERSION=dev5

#构建容器
docker buildx build -t infiniflow/ragflow:$RAGFLOW_VERSION -f Dockerfile.cuda .

# 关闭之前容器的内容
cd docker
sed -i 's/RAGFLOW_VERSION=$OLD_VERSION/RAGFLOW_VERSION=$NEW_VERSION/' .venv

docker compose -f docker-compose.yml down

#启动新容器
docker compose -f docker-compose.yml up -d

