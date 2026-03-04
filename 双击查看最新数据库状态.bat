@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

set DB_PATH=MediaCrawler\data\media_items.db

if not exist "%DB_PATH%" (
    echo 未找到数据库文件：%DB_PATH%
    echo 请确认爬虫是否已经成功运行过。
    echo --------------------------------------------------
    pause
    exit /b 1
)

if not exist "venv\" (
    echo 错误：找不到 venv 虚拟环境！
    echo 请先运行【第1步_首次运行前安装系统所需依赖环境.bat】
    pause
    exit /b 1
)

set PYTHON_BIN=venv\Scripts\python.exe

echo ==================================================
echo           媒体数据源查看器 (最新10条数据)
echo ==================================================
echo.

"%PYTHON_BIN%" -c "import sqlite3, os; db=sqlite3.connect(r'%DB_PATH%'); db.row_factory=sqlite3.Row; cur=db.cursor(); rows=cur.execute('SELECT * FROM media_items ORDER BY created_at DESC LIMIT 10').fetchall(); [print('\n'.join(f'  {k} = {row[k]}' for k in row.keys())+'\n'+'-'*50) for row in rows]; tid=cur.execute('SELECT task_id FROM media_items ORDER BY created_at DESC LIMIT 1').fetchone(); print(f'\n>> 当前最新任务批次号: {tid[0]}') if tid else print('无数据'); total=cur.execute(f\"SELECT count(*) FROM media_items WHERE task_id='{tid[0]}'\").fetchone()[0] if tid else 0; passed=cur.execute(f\"SELECT count(*) FROM media_items WHERE task_id='{tid[0]}' AND initial_passed=1 AND content_type='video'\").fetchone()[0] if tid else 0; screenshots=cur.execute(f\"SELECT count(*) FROM media_items WHERE task_id='{tid[0]}' AND video_screenshots IS NOT NULL AND video_screenshots != ''\").fetchone()[0] if tid else 0; print(f'本批次总抓取条目数: {total}'); print(f'本批次已通过初筛视频数: {passed}'); print(f'本批次已完成截图抽取数: {screenshots}'); db.close()"

echo.
echo ==================================================
pause
