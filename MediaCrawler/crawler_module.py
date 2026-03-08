# -*- coding: utf-8 -*-
# @Desc: 爬虫模块统一入口。供调度模块、调试网站等外部调用。

import time
import random
import string
from typing import List, Optional, Dict


def generate_task_id() -> str:
    """
    生成批次号，格式: YYYYMMDD-XXXX (日期-4位随机码)
    例如: 20260228-A3F7
    """
    date_part = time.strftime("%Y%m%d")
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"{date_part}-{random_part}"


def run(
    platform: str,
    keywords: str,
    time_range_start_s: int = 0,
    time_range_end_s: int = 0,
    max_notes: int = 10,
    max_video_size_mb: int = 100,
    task_id: Optional[str] = None,
    headless: bool = True,
    crawler_type: str = "search",
    login_type: str = "qrcode",
    save_data_option: str = "json",
) -> str:
    """
    爬虫模块统一入口函数。

    Args:
        platform:           平台标识 ("xhs" / "bili")
        keywords:           搜索关键词，多个用英文逗号分隔
        time_range_start_s: 时间窗口起始 (Unix秒级时间戳)，0=不限
        time_range_end_s:   时间窗口结束 (Unix秒级时间戳)，0=不限
        max_notes:          最大爬取数量 (通过初筛的)
        max_video_size_mb:  视频大小限制 (MB)，0=不限
        task_id:            批次号，None=自动生成
        headless:           是否无头模式运行浏览器
        crawler_type:       爬取类型 ("search" / "detail" / "creator")
        login_type:         登录方式 ("qrcode" / "phone" / "cookie")
        save_data_option:   数据保存方式 ("json" / "csv" / "db")

    Returns:
        task_id: 本次运行的批次号
    """
    import config
    from main import main, async_cleanup
    from tools.app_runner import run as app_run
    from tools import utils

    # 生成或使用传入的 task_id
    if task_id is None:
        task_id = generate_task_id()
    config.TASK_ID = task_id

    # 写入 config（兼容现有代码）
    config.PLATFORM = platform
    config.KEYWORDS = keywords
    config.CRAWLER_TYPE = crawler_type
    config.HEADLESS = headless
    config.CRAWLER_MAX_NOTES_COUNT = max_notes
    config.MAX_VIDEO_SIZE_MB = max_video_size_mb
    config.LOGIN_TYPE = login_type
    config.SAVE_DATA_OPTION = save_data_option

    # 硬编码 CDP 模式配置：小红书必须开启以绕过风控，B 站关闭
    if platform == "xhs":
        config.ENABLE_CDP_MODE = True
    elif platform == "bili":
        config.ENABLE_CDP_MODE = False

    # 时间窗口
    enable_time = (time_range_start_s > 0 or time_range_end_s > 0)
    config.FILTER_TIME_RANGE = {
        "enable": enable_time,
        "start_timestamp_s": time_range_start_s,
        "end_timestamp_s": time_range_end_s,
    }

    utils.logger.info(f"[CrawlerModule] Starting crawl task_id={task_id}, "
                      f"platform={platform}, keywords={keywords}, max={max_notes}")

    # 启动爬虫
    def _force_stop():
        from main import crawler
        if crawler and hasattr(crawler, "cdp_manager") and getattr(crawler, "cdp_manager"):
            try:
                getattr(crawler.cdp_manager, "launcher").cleanup()
            except Exception:
                pass

    app_run(main, async_cleanup, cleanup_timeout_seconds=15.0, on_first_interrupt=_force_stop)

    utils.logger.info(f"[CrawlerModule] Crawl task_id={task_id} finished.")
    return task_id
