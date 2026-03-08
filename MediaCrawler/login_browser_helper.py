from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def find_chrome() -> str | None:
    candidates = [
        Path(os.environ.get("ProgramFiles", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LocalAppData", "")) / "Google/Chrome/Application/chrome.exe",
    ]

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    found = shutil.which("chrome")
    if found:
        return found
    return None


def open_window(chrome_path: str, user_data_dir: Path, url: str) -> None:
    user_data_dir.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(
        [
            chrome_path,
            f"--user-data-dir={user_data_dir}",
            "--new-window",
            url,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main() -> int:
    module_root = Path(__file__).resolve().parent
    browser_data_dir = module_root / "browser_data"

    chrome_path = find_chrome()
    if not chrome_path:
        print("未检测到 Google Chrome，请先安装后再重试。")
        return 1

    xhs_dir = browser_data_dir / "cdp_xhs_user_data_dir"
    bili_dir = browser_data_dir / "bili_user_data_dir"

    open_window(chrome_path, xhs_dir, "https://www.xiaohongshu.com/")
    open_window(chrome_path, bili_dir, "https://www.bilibili.com/")

    print("已打开小红书和B站登录窗口。")
    print("小红书使用目录: MediaCrawler/browser_data/cdp_xhs_user_data_dir")
    print("B站使用目录: MediaCrawler/browser_data/bili_user_data_dir")
    return 0


if __name__ == "__main__":
    sys.exit(main())
