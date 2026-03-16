from playwright.sync_api import sync_playwright
import json
from datetime import datetime, timedelta
import time

AUTH_FILE = "channels_auth.json"


def save_login_state():
    print("🚀 启动浏览器...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            slow_mo=1000,
            args=['--disable-blink-features=AutomationControlled']  # 隐藏自动化特征
        )

        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )

        page = context.new_page()

        print("🌐 打开视频号助手...")
        page.goto("https://channels.weixin.qq.com/pc/pc/instrumentation/dashboard")

        print("📱 请用微信扫描页面上的二维码...")
        print("⏳ 扫码后，等待页面跳转（出现数据中心或工作台即可）...")
        print("   （即使代码提示超时，只要页面显示后台数据，按Ctrl+C也能保存）")

        try:
            # 方案A：等待URL变化（登录后URL通常包含dashboard或workbench）
            print("🔍 检测方式1：等待URL变化...")
            page.wait_for_url("**/pc/pc/instrumentation/**", timeout=60000)
            print("✅ URL已变化，可能已登录")

        except:
            print("⚠️ URL检测超时，尝试检测页面内容...")

            try:
                # 方案B：等待页面包含特定文本（如"数据中心"、"昨日概况"等）
                # 使用body文本检测，不依赖特定CSS类名
                page.wait_for_function("""
                    () => document.body.innerText.includes('数据中心') 
                    || document.body.innerText.includes('昨日概况')
                    || document.body.innerText.includes('作品数据')
                    || document.body.innerText.includes('总览')
                """, timeout=60000)
                print("✅ 检测到后台页面关键词")

            except:
                print("⚠️ 文本检测也超时了，但可能已经登录...")

        # 无论检测是否成功，只要页面加载完成，就截图查看当前状态
        print("📸 正在截图查看当前页面状态...")
        page.screenshot(path='current_state.png', full_page=True)

        # 询问用户是否已登录成功
        print("\n" + "=" * 50)
        print("请查看弹出的浏览器窗口：")
        print("1. 如果已经显示视频号后台（有数据、有菜单），说明登录成功")
        print("2. 如果还停留在登录页，说明扫码失败或超时")
        print("=" * 50)

        # 等待用户确认（给你时间看页面）
        input_status = input("是否已看到视频号后台数据？(y/n): ")

        if input_status.lower() == 'y':
            # 保存登录状态
            context.storage_state(path=AUTH_FILE)

            meta = {
                'saved_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'expires_at': (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
            }
            with open('auth_meta.json', 'w') as f:
                json.dump(meta, f)

            print(f"\n✅ 登录状态已强制保存到 {AUTH_FILE}")
            print(f"📅 标记有效期至：{meta['expires_at']}")
            print("💡 即使自动检测超时，只要页面正常，状态就是有效的")

            # 再截一张图确认
            page.screenshot(path='login_success.png')

        else:
            print("❌ 登录未完成，请重新运行并扫码")

        browser.close()


if __name__ == "__main__":
    save_login_state()