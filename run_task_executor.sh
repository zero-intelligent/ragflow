#!/bin/bash

# 要执行的 Python 脚本路径
APP_HOME=$(dirname "$0")
cd "$APP_HOME"
source .venv/bin/activate

export CUDA_VISIBLE_DEVICES=0 
export PYTHONPATH=$(pwd)

task_num=${1:-1}
for ((i=1;i<=task_num;i++)); do
    python rag/svr/task_executor.py $i
done
