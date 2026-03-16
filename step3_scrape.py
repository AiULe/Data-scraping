from playwright.sync_api import sync_playwright
import pandas as pd
import json
import time
from datetime import datetime
import re


class ChannelsDataScraper:
    def __init__(self):
        self.auth_file = "channels_auth.json"
        self.data = []

    def parse_number(self, text):
        """处理带单位的数字"""
        if not text or text in ['-', '']:
            return 0
        text = str(text).replace(',', '').strip()
        if '万' in text:
            return int(float(text.replace('万', '')) * 10000)
        if 'w' in text.lower():
            return int(float(text.lower().replace('w', '')) * 10000)
        if 'k' in text.lower():
            return int(float(text.lower().replace('k', '')) * 1000)
        nums = re.findall(r'\d+', text)
        return int(nums[0]) if nums else 0

    def scrape(self):
        print("🚀 启动数据抓取...")

        with sync_playwright() as p:
            # 验证登录文件
            try:
                with open(self.auth_file, 'r') as f:
                    auth_data = json.load(f)
                print(f"✅ 登录状态有效（大小：{len(str(auth_data))} 字符）")
            except Exception as e:
                print(f"❌ 登录文件读取失败：{e}")
                return

            # 启动浏览器
            browser = p.chromium.launch(
                headless=False,
                slow_mo=500,
                args=['--disable-blink-features=AutomationControlled']
            )

            context = browser.new_context(
                storage_state=self.auth_file,
                viewport={'width': 1280, 'height': 900}
            )

            page = context.new_page()

            try:
                # 关键修复1：去掉networkidle，使用load或完全不等待
                print("🌐 访问视频号助手...")
                page.goto("https://channels.weixin.qq.com/pc/pc/instrumentation/dashboard",
                          timeout=60000)  # 只等60秒，不严格要求networkidle

                # 等待几秒让页面渲染
                time.sleep(5)

                current_url = page.url
                print(f"📍 当前页面：{current_url}")

                # 检查是否被踢到登录页
                if "login" in current_url or "qr" in current_url:
                    print("❌ 登录已失效，请重新运行 step2_fixed.py 扫码")
                    browser.close()
                    return

                # 关键修复2：多种方式进入作品数据页
                print("🔍 寻找作品数据入口...")

                # 方式A：直接点击左侧菜单"作品数据"（如果可见）
                menu_selectors = [
                    'text=作品数据',
                    'text=内容分析',
                    'text=数据中心',
                    '[data-key="opus"]',
                    '[data-key="content"]',
                    'a:has-text("作品")',
                    'a:has-text("内容")'
                ]

                clicked = False
                for selector in menu_selectors:
                    try:
                        if page.is_visible(selector, timeout=2000):
                            print(f"   点击菜单：{selector}")
                            page.click(selector)
                            clicked = True
                            time.sleep(5)  # 等待页面切换
                            break
                    except:
                        continue

                # 方式B：如果找不到菜单，直接访问URL（备用）
                if not clicked:
                    print("   尝试直接访问作品数据URL...")
                    # 尝试多个可能的URL
                    urls = [
                        "https://channels.weixin.qq.com/pc/pc/instrumentation/opus",
                        "https://channels.weixin.qq.com/pc/pc/instrumentation/content",
                        "https://channels.weixin.qq.com/pc/pc/opus/manage"  # 另一个可能的路径
                    ]

                    for url in urls:
                        try:
                            page.goto(url, timeout=30000)
                            time.sleep(5)
                            if "login" not in page.url:
                                print(f"   ✅ 成功进入：{page.url}")
                                clicked = True
                                break
                        except:
                            continue

                if not clicked:
                    print("⚠️ 未能自动导航，请手动在浏览器中点击'作品数据'，然后按回车继续...")
                    input("按回车继续...")

                # 关键修复3：宽松等待列表加载
                print("⏳ 等待视频列表加载（最多30秒）...")

                # 截图看看当前状态
                page.screenshot(path='before_scrape.png')

                # 尝试多种可能的选择器（视频号经常改版）
                possible_selectors = [
                    '.opus-item',  # 新版作品卡片
                    '.content-item',  # 旧版
                    '.video-item',
                    '.data-row',
                    'tr[class*="data"]',  # 表格行
                    '[class*="opus"]',
                    '[class*="video"]',
                    '.list-item',
                    'table tbody tr'  # 如果是表格
                ]

                found_selector = None
                for selector in possible_selectors:
                    try:
                        # 宽松等待：只要有一个元素就行
                        page.wait_for_selector(selector, timeout=10000)
                        # 检查是否真的有内容（不只一个空元素）
                        elements = page.query_selector_all(selector)
                        if len(elements) > 0:
                            found_selector = selector
                            print(f"✅ 检测到列表元素：{selector}（共{len(elements)}个）")
                            break
                    except:
                        continue

                if not found_selector:
                    print("⚠️ 未能自动检测，尝试通用方法...")
                    # 最后尝试：获取页面所有文本，看是否有"播放量"等关键词
                    page_text = page.inner_text('body')
                    if '播放量' in page_text or '点赞' in page_text:
                        print("✅ 页面包含数据关键词，尝试通用抓取...")
                        found_selector = 'body'  # 从body里解析
                    else:
                        print("❌ 页面似乎没有加载数据，截图保存为 before_scrape.png，请查看")
                        return

                # 开始抓取
                print("📊 开始提取视频数据...")
                self._extract_data(page, found_selector)

                # 导出
                if self.data:
                    self._export()
                else:
                    print("❌ 未能提取到数据")

            except Exception as e:
                print(f"❌ 错误：{str(e)[:200]}")
                page.screenshot(path='error.png')
                print("📸 错误截图已保存为 error.png")

            finally:
                browser.close()

    def _extract_data(self, page, selector):
        """提取数据（适配多种可能的结构）"""
        try:
            if selector == 'body':
                # 通用方法：通过文本正则提取（兜底方案）
                # 这比较粗糙，但兼容性好
                print("   使用通用文本提取...")
                html = page.content()
                # 这里可以添加正则提取逻辑
                # 暂时先尝试通过JavaScript执行获取数据
                videos = page.evaluate("""() => {
                    // 尝试从页面JavaScript变量或DOM中提取
                    const items = [];
                    const rows = document.querySelectorAll('tr, .item, [class*="item"], [class*="opus"]');
                    rows.forEach(row => {
                        const text = row.innerText || '';
                        const title = row.querySelector('[class*="title"], h3, h4, .title')?.innerText || '';
                        if (title && text.includes('播放')) {
                            items.push({
                                title: title,
                                text: text.substring(0, 200)  // 前200字符用于解析
                            });
                        }
                    });
                    return items;
                }""")

                for v in videos[:20]:
                    # 从text中解析数字
                    text = v['text']
                    numbers = re.findall(r'(\d+(?:\.\d+)?(?:万|w|k)?)', text)
                    self.data.append({
                        'title': v['title'],
                        'views': self.parse_number(numbers[0]) if len(numbers) > 0 else 0,
                        'likes': self.parse_number(numbers[1]) if len(numbers) > 1 else 0,
                        'comments': self.parse_number(numbers[2]) if len(numbers) > 2 else 0,
                        'shares': self.parse_number(numbers[3]) if len(numbers) > 3 else 0,
                        'platform': '视频号'
                    })
            else:
                # 正常DOM提取
                items = page.query_selector_all(selector)
                print(f"   找到 {len(items)} 个元素")

                for i, item in enumerate(items[:30]):  # 最多30条
                    try:
                        # 智能提取：尝试多种可能的选择器
                        title = self._safe_get_text(item, [
                            '.title', '[class*="title"]', 'h3', 'h4', '.opus-title', '.video-title'
                        ])

                        views = self._safe_get_number(item, [
                            '.play-count', '.view-count', '[class*="play"]', '[class*="view"]', 'td:nth-child(2)'
                        ])

                        likes = self._safe_get_number(item, [
                            '.like-count', '[class*="like"]', '.praise', '[class*="good"]', 'td:nth-child(3)'
                        ])

                        comments = self._safe_get_number(item, [
                            '.comment-count', '[class*="comment"]', 'td:nth-child(4)'
                        ])

                        shares = self._safe_get_number(item, [
                            '.share-count', '[class*="share"]', '[class*="forward"]', 'td:nth-child(5)'
                        ])

                        if title:  # 只有拿到标题才算有效
                            self.data.append({
                                'title': title[:50],  # 限制长度
                                'views': views,
                                'likes': likes,
                                'comments': comments,
                                'shares': shares,
                                'platform': '视频号'
                            })
                            print(f"   ✓ [{i + 1}] {title[:20]}... 播放:{views}")

                    except Exception as e:
                        # 单条失败继续
                        continue

        except Exception as e:
            print(f"   提取过程出错：{e}")

    def _safe_get_text(self, parent, selectors):
        """安全获取文本（尝试多个选择器）"""
        for sel in selectors:
            try:
                elem = parent.query_selector(sel)
                if elem:
                    text = elem.inner_text().strip()
                    if text:
                        return text
            except:
                continue
        return ""

    def _safe_get_number(self, parent, selectors):
        """安全获取数字"""
        text = self._safe_get_text(parent, selectors)
        return self.parse_number(text)

    def _export(self):
        """导出Excel"""
        today = datetime.now().strftime('%Y%m%d')
        filename = f'视频号周报_{today}.xlsx'

        df = pd.DataFrame(self.data)

        # 列名美化
        rename = {
            'title': '视频标题',
            'views': '播放量',
            'likes': '点赞量',
            'comments': '评论量',
            'shares': '转发量',
            'platform': '平台'
        }
        df.rename(columns={k: v for k, v in rename.items() if k in df.columns}, inplace=True)

        # 计算点赞率
        if '播放量' in df.columns and '点赞量' in df.columns:
            df['点赞率%'] = (df['点赞量'] / df['播放量'] * 100).round(2)

        df.to_excel(filename, index=False)

        print(f"\n✅ 成功导出：{filename}")
        print(f"📊 共 {len(df)} 条视频")
        if '播放量' in df.columns:
            print(f"   总播放：{df['播放量'].sum():,}")
        if '点赞量' in df.columns:
            print(f"   总点赞：{df['点赞量'].sum():,}")


if __name__ == "__main__":
    scraper = ChannelsDataScraper()
    scraper.scrape()

    print("\n💡 如果数据为空，请检查 before_scrape.png 截图，看是否已登录")