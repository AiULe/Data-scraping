from playwright.sync_api import sync_playwright
import pandas as pd
import json
import time
from datetime import datetime
import re


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


def scrape_channels():
    print("🚀 启动视频号数据抓取（微前端版）...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            slow_mo=800,
            args=['--disable-blink-features=AutomationControlled']
        )

        context = browser.new_context(
            storage_state="channels_auth.json",
            viewport={'width': 1400, 'height': 900}
        )

        page = context.new_page()

        # 关键修复：直接访问微前端内容管理页（不是instrumentation路径）
        urls_to_try = [
            "https://channels.weixin.qq.com/micro/content/",  # 内容管理/作品数据
            "https://channels.weixin.qq.com/micro/statistic/",  # 数据中心
            "https://channels.weixin.qq.com/micro/opus/"  # 可能的作品页
        ]

        success = False
        for url in urls_to_try:
            try:
                print(f"\n🌐 尝试访问：{url}")
                page.goto(url, timeout=60000)

                # 等待加载（微前端需要时间较长）
                time.sleep(8)

                current_url = page.url
                print(f"📍 当前URL：{current_url}")

                # 检查是否被重定向到登录页
                if "login" in current_url or "qr" in current_url:
                    print("⚠️ 登录态失效，需要重新扫码")
                    continue

                # 截图看状态
                page.screenshot(path=f'try_{url.split("/")[-2]}.png')

                # 检查是否有数据（通过寻找关键文本）
                page_text = page.inner_text('body')
                if '视频' in page_text and ('播放' in page_text or '点赞' in page_text or '数据' in page_text):
                    print(f"✅ 成功进入数据页面：{url}")
                    success = True
                    break

            except Exception as e:
                print(f"❌ {url} 访问失败：{str(e)[:100]}")
                continue

        if not success:
            print("\n❌ 所有URL都失败，请检查登录状态")
            browser.close()
            return

        # 等待数据完全加载（微前端通常有加载动画）
        print("⏳ 等待数据加载（10秒）...")
        time.sleep(10)

        # 再次截图确认
        page.screenshot(path='data_page_loaded.png')
        print("✅ 页面已截图保存为 data_page_loaded.png")

        # 提取数据
        print("\n🔍 开始提取视频数据...")
        data = []

        # 方法1：通过JavaScript获取（最适合微前端）
        videos = page.evaluate("""() => {
            const results = [];

            // 微前端常见的列表选择器
            const selectors = [
                '.content-item', '.opus-item', '.video-item', 
                '.weui-desktop-media__item', '.finder-item',
                '[class*="content"] [class*="item"]',
                '[class*="opus"]',
                'table tbody tr', 
                '.list .item'
            ];

            for (let sel of selectors) {
                const items = document.querySelectorAll(sel);
                console.log('尝试选择器:', sel, '找到:', items.length);

                if (items.length > 0) {
                    items.forEach(item => {
                        // 获取标题
                        const titleSelectors = ['.title', 'h3', 'h4', '.video-title', '.content-title', '.name', 'td:nth-child(1)'];
                        let title = '';
                        for (let ts of titleSelectors) {
                            const el = item.querySelector(ts);
                            if (el) {
                                title = el.innerText.trim();
                                if (title) break;
                            }
                        }

                        // 获取所有数字（播放、点赞、评论、转发）
                        const text = item.innerText || '';
                        // 匹配数字（支持 1.2万 格式）
                        const matches = text.match(/(\\d+(?:\\.\\d+)?(?:万|w)?)/gi) || [];

                        // 过滤掉时长（如 01:23）只保留数字
                        const numbers = matches.filter(m => !m.includes(':') && parseFloat(m.replace(/万|w/gi, '')) > 0);

                        if (title && numbers.length >= 2) {
                            results.push({
                                title: title,
                                numbers: numbers,
                                rawText: text.substring(0, 150)
                            });
                        }
                    });

                    if (results.length > 0) break;
                }
            }

            // 如果没找到，尝试从整个页面提取表格数据
            if (results.length === 0) {
                const tables = document.querySelectorAll('table');
                tables.forEach(table => {
                    const rows = table.querySelectorAll('tbody tr');
                    rows.forEach(row => {
                        const cells = row.querySelectorAll('td');
                        if (cells.length >= 3) {
                            const title = cells[0].innerText.trim();
                            const nums = [];
                            for (let i = 1; i < cells.length; i++) {
                                const text = cells[i].innerText;
                                const match = text.match(/(\\d+(?:\\.\\d+)?(?:万|w)?)/);
                                if (match) nums.push(match[1]);
                            }
                            if (title && nums.length > 0) {
                                results.push({title, numbers: nums});
                            }
                        }
                    });
                });
            }

            return results;
        }""")

        print(f"📊 提取到 {len(videos)} 条原始数据")

        if videos and len(videos) > 0:
            for i, v in enumerate(videos[:20]):  # 最多20条
                nums = v.get('numbers', [])

                # 智能分配数字（通常是：播放、点赞、评论、转发）
                data.append({
                    '视频标题': v['title'][:60],
                    '播放量': parse_number(nums[0]) if len(nums) > 0 else 0,
                    '点赞量': parse_number(nums[1]) if len(nums) > 1 else 0,
                    '评论量': parse_number(nums[2]) if len(nums) > 2 else 0,
                    '转发量': parse_number(nums[3]) if len(nums) > 3 else 0,
                    '原始数据': str(nums)  # 调试用，确认数字对应关系
                })

            # 导出Excel
            df = pd.DataFrame(data)
            today = datetime.now().strftime('%Y%m%d')
            filename = f'视频号数据_{today}.xlsx'

            # 计算互动率
            if len(df) > 0 and df['播放量'].sum() > 0:
                df['点赞率%'] = (df['点赞量'] / df['播放量'] * 100).round(2)

            df.to_excel(filename, index=False)

            print(f"\n✅ 成功导出：{filename}")
            print(f"📈 共 {len(df)} 条视频")
            print(f"👁️ 总播放：{df['播放量'].sum():,}")
            print(f"❤️ 总点赞：{df['点赞量'].sum():,}")
            print("\n前3条预览：")
            print(df[['视频标题', '播放量', '点赞量']].head(3).to_string())

        else:
            print("❌ 未提取到数据，可能：")
            print("   1. 该页面没有视频（新账号？）")
            print("   2. 数据是异步加载的，需要更长的等待时间")
            print("   3. 需要滚动加载（试试把time.sleep(10)改成20）")

            # 保存页面源码供分析
            html = page.content()
            with open('debug_micro.html', 'w', encoding='utf-8') as f:
                f.write(html[:15000])
            print("💡 已保存页面源码到 debug_micro.html")

        browser.close()


if __name__ == "__main__":
    scrape_channels()