#!/usr/bin/env bash

# 进入脚本所在的目录（新项目的根目录）
cd "$(dirname "$0")"

echo "=================================================="
echo "          社媒内容提取系统 - 环境一键安装          "
echo "=================================================="

# 1. 检查是不是已经有 venv 了
if [ -d "venv" ]; then
    echo "发现已存在的虚拟环境 (venv)。"
else
    echo "正在为您创建独立的隔离环境 (venv)..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "创建失败！请检查您的系统是否已安装 Python3。"
        read -p "按回车键退出..."
        exit 1
    fi
fi

# 2. 激活环境并安装依赖
echo "正在为您安装系统所需的全部依赖库，这可能需要几分钟时间，请喝杯水稍候..."
source venv/bin/activate

# 升级 pip 到最新版
python -m pip install --upgrade pip

# 根据根目录的总清单批量安装
pip install -r requirements_all.txt

echo "=================================================="
echo "环境安装完成！以后您无需再运行此脚本。"
echo "请双击运行 【第2步_启动展示检索服务.command】 来启动系统。"
echo "=================================================="

read -p "按回车键退出..."
