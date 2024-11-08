#!/bin/bash

# 要执行的 Python 脚本路径
APP_HOME="$(cd "$(dirname "$0")" && pwd)"
echo "APP_HOME:$APP_HOME"

cd $APP_HOME
source .venv/bin/activate

export CUDA_VISIBLE_DEVICES=0 
export PYTHONPATH=$(pwd)

task_num=${1:-1}  # 参数1 并发数量
start_idx=${2:-1} # 参数2 初始任务id， 当多次运行此脚本时，需要配置此参数，确保第二次生成的 python task id 和第一次是区别的

export BATCH_QUERY_INTERVAL=$((16 * (start_idx + task_num)))
for ((i=start_idx;i<=task_num;i++)); do
    echo "run task_executor $i"
    nohup python rag/svr/task_executor.py $i >> logs/task_executor_$i.log 2>&1 &
    sleep 20
done
