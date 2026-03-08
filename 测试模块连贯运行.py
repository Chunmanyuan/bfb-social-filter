import argparse
import os
import subprocess
import sys
import time
from datetime import datetime

# 强制标准输出使用 utf-8，避免 Windows 控制台无法打印 Emoji 而崩溃
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')


def str_to_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def run_pipeline(
    keywords: str,
    hours_back: int,
    max_notes: int,
    max_video_size_mb: int,
    num_frames: int,
    threshold: int,
    ocr_device: str,
    ocr_workers: int,
    headless: bool,
    enable_mkldnn: bool = False,
    task_id: str | None = None,
) -> str:
    project_root = os.path.dirname(os.path.abspath(__file__))
    crawler_dir = os.path.join(project_root, "MediaCrawler")
    screenshot_dir = os.path.join(project_root, "VideoScreenshotter")
    ocr_dir = os.path.join(project_root, "PaddleOCRProcessor")

    current_time = int(time.time())
    hours_back = max(1, int(hours_back))
    start_time = current_time - hours_back * 3600

    run_task_id = task_id or ("E2E-" + datetime.now().strftime("%Y%m%d%H%M"))

    print("=" * 60)
    print("🚀 开始端到端自动化测试流水线")
    print(f"📌 Task ID: {run_task_id}")
    print(
        f"🕒 时间窗口: {datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S')} "
        f"至 {datetime.fromtimestamp(current_time).strftime('%Y-%m-%d %H:%M:%S')}"
    )
    print(f"🔑 搜索词: {keywords}")
    print("=" * 60)

    crawler_runner_path = os.path.join(crawler_dir, "_temp_e2e_runner.py")
    with open(crawler_runner_path, "w", encoding="utf-8") as f:
        f.write(
            f"""
import crawler_module

print("\\n>>> [1/4] 启动爬虫模块 - 抓取目标: B站")
crawler_module.run(
    platform="bili",
    keywords={keywords!r},
    time_range_start_s={start_time},
    time_range_end_s={current_time},
    max_notes={max_notes},
    max_video_size_mb={max_video_size_mb},
    task_id={run_task_id!r},
    headless={headless}
)

print("\\n>>> [2/4] 启动爬虫模块 - 抓取目标: 小红书")
crawler_module.run(
    platform="xhs",
    keywords={keywords!r},
    time_range_start_s={start_time},
    time_range_end_s={current_time},
    max_notes={max_notes},
    max_video_size_mb={max_video_size_mb},
    task_id={run_task_id!r},
    headless={headless}
)
"""
        )

    if sys.platform == "win32":
        python_executable = os.path.join(project_root, "venv", "Scripts", "python.exe")
    else:
        python_executable = os.path.join(project_root, "venv", "bin", "python")

    try:
        subprocess.run(
            [python_executable, "_temp_e2e_runner.py"],
            cwd=crawler_dir,
            check=True,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.CalledProcessError as e:
        print(f"\n❌ 爬虫模块运行发生错误, 流水线中断。错误码: {e.returncode}")
        if os.path.exists(crawler_runner_path):
            os.remove(crawler_runner_path)
        raise
    finally:
        if os.path.exists(crawler_runner_path):
            os.remove(crawler_runner_path)

    print("\n>>> [3/4] 启动视频截图模块对刚落盘的视频进行抽帧排重...")
    subprocess.run(
        [
            python_executable,
            "screenshot_module.py",
            "--task_id",
            run_task_id,
            "--num_frames",
            str(num_frames),
            "--threshold",
            str(threshold),
        ],
        cwd=screenshot_dir,
        check=True,
        encoding="utf-8",
        errors="replace",
    )

    print("\n>>> [4/4] 启动 OCR 模块提取小红书图片与视频截图文字...")
    ocr_cmd = [
        python_executable,
        "ocr_module.py",
        "--task_id",
        run_task_id,
        "--device",
        ocr_device,
        "--workers",
        str(max(1, int(ocr_workers))),
    ]
    if enable_mkldnn:
        ocr_cmd.append("--enable_mkldnn")

    subprocess.run(
        ocr_cmd,
        cwd=ocr_dir,
        check=True,
        encoding="utf-8",
        errors="replace",
    )

    print("\n" + "=" * 60)
    print("🎉 端到端自动化测试流水线 (Crawler -> Screenshotter -> OCR) 运行完毕！")
    print(f"👉 本批次的所有数据均已绑在 {run_task_id} 上存储至 SQLite。")
    print("=" * 60)

    return run_task_id


def main():
    parser = argparse.ArgumentParser(description="Run end-to-end crawler/screenshot/OCR pipeline")
    parser.add_argument("--keywords", type=str, default="bfb", help="Keywords for both platforms")
    parser.add_argument("--hours-back", type=int, default=24, help="Time window size in hours")
    parser.add_argument("--max-notes", type=int, default=30, help="Max crawl count per platform")
    parser.add_argument("--max-video-size-mb", type=int, default=100, help="Max allowed video size")
    parser.add_argument("--num-frames", type=int, default=40, help="Frames sampled by screenshot module")
    parser.add_argument("--threshold", type=int, default=5, help="Dedup threshold for screenshot module")
    parser.add_argument("--ocr-device", type=str, default="auto", help="OCR device: auto/cpu/gpu")
    parser.add_argument("--ocr-workers", type=int, default=1, help="OCR workers, default 1")
    parser.add_argument("--headless", type=str, default="true", help="Headless mode: true/false")
    parser.add_argument("--task-id", type=str, default=None, help="Optional fixed task_id")
    parser.add_argument(
        "--enable-mkldnn",
        action="store_true",
        help="启用 MKLDNN CPU 加速（在部分 Windows/新版 Paddle 上可能导致崩溃，默认关闭）",
    )
    args = parser.parse_args()

    run_pipeline(
        keywords=args.keywords,
        hours_back=args.hours_back,
        max_notes=args.max_notes,
        max_video_size_mb=args.max_video_size_mb,
        num_frames=args.num_frames,
        threshold=args.threshold,
        ocr_device=args.ocr_device,
        ocr_workers=args.ocr_workers,
        headless=str_to_bool(args.headless),
        enable_mkldnn=args.enable_mkldnn,
        task_id=args.task_id,
    )


if __name__ == "__main__":
    main()
