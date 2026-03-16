from playwright.sync_api import sync_playwright
import time

print("🚀 正在启动浏览器...")

with sync_playwright() as p:
    # 启动浏览器（headless=False表示可见窗口，方便调试）
    browser = p.chromium.launch(headless=False, slow_mo=1000)

    # 创建新页面
    page = browser.new_page(viewport={'width': 1280, 'height': 800})

    # 访问视频号助手
    print("🌐 正在打开视频号助手...")
    page.goto("https://channels.weixin.qq.com/pc/pc/instrumentation/dashboard")

    print("📱 请查看浏览器窗口，应该已经出现微信登录二维码")
    print("⏳ 等待60秒供你扫码（仅测试，先不登录也行）...")

    # 等待60秒，看看是否成功加载
    time.sleep(60)

    print("✅ 测试完成！如果看到二维码，说明第一步成功")
    browser.close()