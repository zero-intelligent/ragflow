#!/bin/bash

# 要执行的 Python 脚本路径
SCRIPT_PATH="./deepdoc/pdf2txt.py"
APP_HOME=$(dirname "$0")

INPUT_DIR=""
INSTALL=false

# 解析命令行参数
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --install) 
            INSTALL=true 
            ;;
        --input_dir) 
            shift
            INPUT_DIR="$1" 
            ;;
        *) 
            echo "Unknown parameter: $1"
            exit 1 
            ;;
    esac
    shift
done


# 检查 INPUT_DIR 是否为空
if [[ -z "$INPUT_DIR" ]]; then
    INPUT_DIR="/mnt/disk5/dataset/800本宠物医学电子书"
fi


# 激活虚拟环境
cd $APP_HOME
source ~/anaconda3/bin/activate ragflow

# 确保依赖so文件能找到
export LD_LIBRARY_PATH=/home/admin/anaconda3/lib/python3.11/site-packages/nvidia/cudnn/lib:$LD_LIBRARY_PATH
export LD_LIBRARY_PATH=/usr/local/cuda-12.1/targets/x86_64-linux/lib:$LD_LIBRARY_PATH

check_depends() {
    files=(
        "libcublas.so"
        "libcudnn.so"
        "libcudnn_cnn_infer.so.8"
        "libcudnn_ops_infer.so.8"
    )

    for file in "${files[@]}"; do
        found=$(find ${LD_LIBRARY_PATH//:/ } -name "$file" -print -quit)
        if [ -z "$found" ]; then
            echo "Could not find $file in directories specified by LD_LIBRARY_PATH."
            exit 1
        fi
    done

}

# 循环执行直到不再出现 ModuleNotFoundError 错误
install_missing_modules() {
    while true; do
        # 执行 Python 脚本并将标准错误输出重定向到标准输出
        output=$(python $SCRIPT_PATH $INPUT_DIR 2>&1)
        echo "$output"
        
        # 检查输出中是否存在 ModuleNotFoundError
        if echo "$output" | grep -q "ModuleNotFoundError: No module named"; then
            # 获取缺失模块的名称，并去掉单引号
            missing_module=$(echo "$output" | grep "ModuleNotFoundError: No module named" | awk '{print $NF}' | tr -d "'")
            
            # 安装缺失的模块
            echo "Detected missing module: $missing_module"
            pip install $missing_module
        else
            # 如果没有 ModuleNotFoundError 错误，则退出循环
            break
        fi
    done
}

if $INSTALL;then
    install_missing_modules
fi

check_depends

while true; do
    # 如果 pdf2txt 少于5个，就启动新的
    if [ $(pgrep -f "pdf2txt" | wc -l) -lt 5 ]; then
        nohup python $SCRIPT_PATH $INPUT_DIR 2>&1 &
    fi

    sleep 60

    pdf_cnt=$(find $INPUT_DIR -type f -name "*.pdf" | wc -l) 
    pdf_cnt=$((pdf_cnt + $(find $INPUT_DIR -type f -name "*.PDF" | wc -l)))
    txt_cnt=$(find $INPUT_DIR -type f -name "*.txt" | wc -l)

    if (($txt_cnt >= $pdf_cnt));then
        break
    fi

done

