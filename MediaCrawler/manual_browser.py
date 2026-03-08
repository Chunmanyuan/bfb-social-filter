import asyncio
from playwright.async_api import async_playwright
import os
import sys

# 把 MediaCrawler 根目录加入 path，为了读取配置和日志
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from tools import utils

async def manual_browser():
    USER_DATA_DIR = os.environ.get(
        "PLAYWRIGHT_USER_DATA_DIR",
        str(os.path.join(os.path.dirname(os.path.abspath(__file__)), "browser_data", "xhs_user_data_dir"))
    )
    
    # 确保目录存在
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    
    print(f"=== 正在启动 Chromium ===")
    print(f"使用的用户数据目录 (含缓存和 Cookie): {USER_DATA_DIR}")
    print(f"请在弹出的浏览器中进行你的手动测试。")
    print(f"提示：即使你在终端按 Ctrl+C/终止命令，这个浏览器窗口也会一直开着，直到你手动关掉它。")
    
    async with async_playwright() as p:
        # 使用和 MediaCrawler 完全一致的启动参数
        browser_context = await p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            accept_downloads=True,
            headless=False,           # 必须有头
            viewport={"width": 1920, "height": 1080},
            args=[
                "--disable-blink-features=AutomationControlled", # 核心反爬伪装设置
                "--disable-infobars",
                "--start-maximized",
            ]
        )
        
        # 打开一个新页面进入小红书
        page = await browser_context.new_page()
        
        # 很多反机器人的脚本会在 load 前检测 webdriver，这里也像爬虫里一样抹除一下
        await page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        
        await page.goto("https://www.xiaohongshu.com/")
        print("=== 浏览器已打开，你可以开始操作了 ===")
        
        # 无限等待，让你有时间操作
        await asyncio.sleep(86400) # 等待一天
        
if __name__ == "__main__":
    try:
        asyncio.run(manual_browser())
    except KeyboardInterrupt:
        print("已退出脚本控制")
