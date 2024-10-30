#!/bin/bash

# 要执行的 Python 脚本路径
APP_HOME="$(cd "$(dirname "$0")" && pwd)"
echo "APP_HOME:$APP_HOME"

cd $APP_HOME
source .venv/bin/activate

export CUDA_VISIBLE_DEVICES=0 
export PYTHONPATH=$(pwd)

nohup python graphrag/graph2neo4j.py sync > logs/graph2neo4j.log 2>&1 &
