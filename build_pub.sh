#!/bin/bash
set -e  # 如果任意命令出错，脚本将立即退出

# 要执行的 Python 脚本路径
APP_HOME="$(cd "$(dirname "$0")" && pwd)"
echo "APP_HOME:$APP_HOME"

cd "$APP_HOME"
source .venv/bin/activate

# 编译前端
cd "$APP_HOME/web"
if [ ! -d dist ] || [ "$(find src -type f -newer dist | wc -l)" -gt 0 ]; then
    npm i --force && npm run build; 
else 
    echo 'Build is up-to-date'; 
fi


OLD_VERSION=dev4
NEW_VERSION=dev5

cd "$APP_HOME"

#构建容器
docker buildx build -t infiniflow/ragflow:$NEW_VERSION -f Dockerfile.cuda .

# 关闭之前容器的内容
cd docker
sed -i "s/RAGFLOW_VERSION=$OLD_VERSION/RAGFLOW_VERSION=$NEW_VERSION/" .env

docker compose -f docker-compose.yml down

#启动新容器
docker compose -f docker-compose.yml up -d

