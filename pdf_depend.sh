#!/bin/bash

# 要执行的 Python 脚本路径
SCRIPT_PATH="/Users/mac/python_projects/ragflow/deepdoc/pdf2txt.py"
INPUT_DIR="/mnt/disk5/dataset/800本宠物医学电子书"

# 激活虚拟环境
source .venv/bin/activate  # 替换 path_to_your_env 为实际的路径

# 定义一个函数来检查并安装缺失的模块
install_missing_module() {
    missing_module=$1
    echo "Detected missing module: $missing_module"
    pip install $missing_module
}

# 循环执行直到不再出现 ModuleNotFoundError 错误
while true; do
    # 执行 Python 脚本并将标准错误输出重定向到标准输出
    output=$(python $SCRIPT_PATH INPUT_DIRR 2>&1)
    echo $output
    
    # 检查输出中是否存在 ModuleNotFoundError
    if echo "$output" | grep -q "ModuleNotFoundError: No module named"; then
        # 获取缺失模块的名称，并去掉单引号
        missing_module=$(echo "$output" | grep "ModuleNotFoundError: No module named" | awk '{print $NF}' | tr -d "'")
        
        # 安装缺失的模块
        install_missing_module "$missing_module"
    else
        # 如果没有 ModuleNotFoundError 错误，则退出循环
        break
    fi
done

# 退出虚拟环境
deactivate