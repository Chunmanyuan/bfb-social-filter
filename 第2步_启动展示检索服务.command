#!/usr/bin/env bash

# 进入脚本所在目录（项目根目录）
cd "$(dirname "$0")"

echo "=================================================="
echo "      展示检索服务 - 启动中 (DashboardQuerying)      "
echo "=================================================="

if [ ! -d "venv" ]; then
    echo "错误：找不到 venv 虚拟环境！"
    echo "请先运行【第1步_首次运行前安装系统所需依赖环境.command】"
    read -p "按回车键退出..."
    exit 1
fi

PYTHON_BIN="./venv/bin/python"
SERVICE_URL="http://127.0.0.1:8090/"
HEALTH_URL="http://127.0.0.1:8090/api/health"

# 若服务已在运行，直接打开页面
if command -v curl >/dev/null 2>&1; then
    if curl -fs "$HEALTH_URL" >/dev/null 2>&1; then
        echo "检测到服务已在运行，直接打开页面。"
        open "$SERVICE_URL"
        read -p "按回车键退出..."
        exit 0
    fi
fi

echo "正在启动 DashboardQuerying 服务..."
"$PYTHON_BIN" DashboardQuerying/app.py &
SERVER_PID=$!

echo "等待服务就绪..."
for i in {1..30}; do
    if command -v curl >/dev/null 2>&1; then
        if curl -fs "$HEALTH_URL" >/dev/null 2>&1; then
            break
        fi
    else
        sleep 1
    fi
    sleep 1
done

echo "打开页面: $SERVICE_URL"
open "$SERVICE_URL"

echo "=================================================="
echo "服务已启动，PID=$SERVER_PID"
echo "保持此窗口开启即可持续运行；关闭窗口会停止服务。"
echo "=================================================="

wait "$SERVER_PID"
