#!/usr/bin/env bash

# 进入脚本所在的目录（新项目的根目录）
cd "$(dirname "$0")"

DB_PATH="MediaCrawler/data/media_items.db"

if [ ! -f "$DB_PATH" ]; then
    echo "未找到数据库文件：$DB_PATH"
    echo "请确认爬虫是否已经成功运行过。"
    echo "--------------------------------------------------"
    read -p "按回车键退出..."
    exit 1
fi

echo "=================================================="
echo "          媒体数据源查看器 (最新10条数据)          "
echo "=================================================="
echo ""

# 使用 line 模式输出，这样每一列都会单独换行显示，适合展示所有字段而不至于挤在一起
sqlite3 -line "$DB_PATH" "SELECT * FROM media_items ORDER BY created_at DESC LIMIT 10;"

echo "\n=================================================="
echo "数据库概况统计 (仅限制于最新一次任务批次)："
LATEST_TASK_ID=$(sqlite3 "$DB_PATH" "SELECT task_id FROM media_items ORDER BY created_at DESC LIMIT 1;")
echo ">> 当前最新任务批次号: $LATEST_TASK_ID"

sqlite3 "$DB_PATH" "SELECT '本批次总抓取条目数：', count(*) FROM media_items WHERE task_id = '$LATEST_TASK_ID';"
sqlite3 "$DB_PATH" "SELECT '本批次已通过初筛视频数：', count(*) FROM media_items WHERE task_id = '$LATEST_TASK_ID' AND initial_passed = 1 AND content_type = 'video';"
sqlite3 "$DB_PATH" "SELECT '本批次已完成截图抽取数：', count(*) FROM media_items WHERE task_id = '$LATEST_TASK_ID' AND video_screenshots IS NOT NULL AND video_screenshots != '';"
echo "=================================================="
echo ""
read -p "按回车键退出..."
