from playwright.sync_api import sync_playwright
import pandas as pd
import json
import time
from datetime import datetime
import re


def scrape_with_manual_help():
    print("🚀 启动半自动抓取（需要你在浏览器里点几下）...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        context = browser.new_context(
            storage_state="channels_auth.json",
            viewport={'width': 1400, 'height': 900}
        )
        page = context.new_page()

        # 进入后台
        print("🌐 进入视频号助手...")
        page.goto("https://channels.weixin.qq.com/pc/pc/instrumentation/dashboard", timeout=60000)
        time.sleep(3)

        print("\n" + "=" * 60)
        print("📢 请现在在浏览器中操作：")
        print("1. 点击左侧菜单的'作品数据'或'内容分析'")
        print("2. 等待视频列表出现（能看到播放量数字）")
        print("3. 如果数据没出来，滚动一下页面")
        print("4. 确认看到视频列表后，回到这里按回车")
        print("=" * 60)

        input("\n👆 确认浏览器中已显示视频列表，按回车继续...")

        # 截图看当前状态
        page.screenshot(path='manual_page.png')
        print("✅ 已截图保存为 manual_page.png")

        # 获取页面HTML结构（分析用）
        html = page.content()
        with open('page_source.html', 'w', encoding='utf-8') as f:
            f.write(html[:10000])  # 保存前1万字符
        print("✅ 已保存页面源码到 page_source.html")

        # 尝试智能提取
        print("\n🔍 尝试提取视频数据...")
        data = []

        # 方法1：通过JavaScript执行获取（绕过选择器问题）
        videos = page.evaluate("""() => {
            const results = [];
            // 尝试多种可能的选择器
            const selectors = [
                '.opus-item', '.content-item', '.video-card', 
                '[class*="opus"]', '[class*="video-item"]',
                'table tbody tr', '.list-item', '.data-item'
            ];

            for (let sel of selectors) {
                const items = document.querySelectorAll(sel);
                if (items.length > 0) {
                    items.forEach((item, index) => {
                        // 提取标题
                        const titleEl = item.querySelector('h3, h4, .title, [class*="title"], .video-title');
                        const title = titleEl ? titleEl.innerText.trim() : '';

                        // 提取所有数字（播放、点赞、评论、转发）
                        const text = item.innerText;
                        const numbers = text.match(/(\\d+(?:\\.\\d+)?(?:万|w)?)/g) || [];

                        if (title && numbers.length >= 2) {
                            results.push({
                                title: title,
                                rawText: text.substring(0, 100),
                                numbers: numbers
                            });
                        }
                    });
                    if (results.length > 0) break;
                }
            }
            return results;
        }""")

        if videos and len(videos) > 0:
            print(f"✅ 通过JS提取到 {len(videos)} 条数据")
            for v in videos[:20]:
                nums = v['numbers']
                data.append({
                    'title': v['title'],
                    'views': parse_number(nums[0]) if len(nums) > 0 else 0,
                    'likes': parse_number(nums[1]) if len(nums) > 1 else 0,
                    'comments': parse_number(nums[2]) if len(nums) > 2 else 0,
                    'shares': parse_number(nums[3]) if len(nums) > 3 else 0,
                    'platform': '视频号'
                })
        else:
            print("⚠️ JS提取失败，尝试暴力文本匹配...")
            # 兜底：从整个页面文本中提取视频块
            full_text = page.inner_text('body')
            # 这里可以添加正则提取逻辑

        if data:
            # 导出
            df = pd.DataFrame(data)
            today = datetime.now().strftime('%Y%m%d')
            filename = f'视频号数据_{today}.xlsx'
            df.to_excel(filename, index=False)
            print(f"\n✅ 成功导出 {len(data)} 条数据到 {filename}")
            print(df.head())
        else:
            print("❌ 未能提取数据，请检查 manual_page.png")
            print("💡 建议：把 page_source.html 发给我，我帮你写精确的选择器")

        browser.close()


def parse_number(text):
    """解析数字"""
    if not text:
        return 0
    text = str(text).replace(',', '').strip()
    if '万' in text or 'w' in text.lower():
        num = text.replace('万', '').replace('w', '').replace('W', '')
        return int(float(num) * 10000)
    nums = re.findall(r'\d+', text)
    return int(nums[0]) if nums else 0


if __name__ == "__main__":
    scrape_with_manual_help()