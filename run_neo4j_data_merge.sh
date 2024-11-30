#!/bin/bash

# 要执行的 Python 脚本路径
APP_HOME="$(cd "$(dirname "$0")" && pwd)"
echo "APP_HOME:$APP_HOME"

cd $APP_HOME
source .venv/bin/activate

export PYTHONPATH=$(pwd)

nohup python graphrag/db/update.py >> logs/neo4j_data_merge.log 2>&1 &
