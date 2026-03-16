# debug_helper.py - 用于查看页面实际HTML结构
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto("https://channels.weixin.qq.com/pc/pc/instrumentation/dashboard")

    input("请扫码登录，然后按回车继续...")

    # 获取页面标题
    print("页面标题:", page.title())

    # 获取当前URL
    print("当前URL:", page.url)

    # 截图保存
    page.screenshot(path='debug_page.png')

    # 保存HTML源码（前5000字符，方便查看关键元素）
    html = page.content()
    with open('page_source.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("HTML源码已保存到 page_source.html，请查看其中包含的关键类名或文本")

    browser.close()