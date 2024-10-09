#!/bin/bash

# 要执行的 Python 脚本路径
APP_HOME=$(dirname "$0")
cd "$APP_HOME"
source .venv/bin/activate

export CUDA_VISIBLE_DEVICES=0 
export PYTHONPATH=$APP_HOME

python rag/svr/task_executor.py 1
