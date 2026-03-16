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
    if 'k' in text.lower():
        return int(float(text.lower().replace('k', '')) * 1000)
    nums = re.findall(r'\d+', text)
    return int(nums[0]) if nums else 0


def scrape_with_precise_selector():
    print("🚀 启动精确抓取...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        context = browser.new_context(
            storage_state="channels_auth.json",
            viewport={'width': 1400, 'height': 900}
        )
        page = context.new_page()

        # 访问首页（截图显示你在首页的"最近视频"区域）
        print("🌐 访问视频号首页...")
        page.goto("https://channels.weixin.qq.com/pc/pc/instrumentation/dashboard", timeout=60000)
        time.sleep(5)

        current_url = page.url
        print(f"📍 当前页面：{current_url}")

        # 截图确认
        page.screenshot(path='check_page.png')

        # 精确提取：基于截图中的"最近视频"结构
        print("🔍 提取最近视频数据...")

        videos = page.evaluate("""() => {
            const results = [];

            // 根据截图结构，尝试多种可能的选择器组合
            // 视频号首页的"最近视频"通常是 .video-item 或 .recent-video 或 [class*="video"]
            const containerSelectors = [
                '.recent-video-list',      // 最近视频列表容器
                '.video-list', 
                '.content-list',
                '[class*="recent"]',
                '[class*="video-list"]',
                'div[role="list"]',        // ARIA列表
                '.dashboard .video-item'   // 首页视频项
            ];

            let items = [];

            // 尝试找到视频项
            for (let containerSel of containerSelectors) {
                const container = document.querySelector(containerSel);
                if (container) {
                    // 在容器内找子项
                    const children = container.querySelectorAll('.item, .video-item, .content-item, > div');
                    if (children.length > 0) {
                        items = children;
                        console.log('找到容器:', containerSel, '子项数:', children.length);
                        break;
                    }
                }
            }

            // 如果容器方式失败，直接查找所有可能的视频项
            if (items.length === 0) {
                const itemSelectors = [
                    '.video-item', 
                    '.content-item',
                    '.finder-item',
                    '.weui-desktop-media__item',
                    '[class*="video-card"]',
                    '.dashboard .item'  // 首页的通用item
                ];

                for (let sel of itemSelectors) {
                    items = document.querySelectorAll(sel);
                    if (items.length > 0) {
                        console.log('使用选择器:', sel, '数量:', items.length);
                        break;
                    }
                }
            }

            // 处理每个视频项
            items.forEach((item, index) => {
                try {
                    // 提取标题：通常包含话题标签 #汾杏#白酒
                    const titleSelectors = [
                        '.title', 
                        '.video-title',
                        '.desc',
                        '.description',
                        'h3', 'h4',
                        '.content-title',
                        '.text'  // 可能是纯文本容器
                    ];

                    let title = '';
                    for (let ts of titleSelectors) {
                        const el = item.querySelector(ts);
                        if (el) {
                            title = el.innerText.trim();
                            if (title && title.length > 5) break;  // 确保拿到有效标题
                        }
                    }

                    // 如果没找到，尝试获取整个item的第二行文本（通常是标题）
                    if (!title) {
                        const allText = item.innerText.split('\\n');
                        if (allText.length > 1) {
                            title = allText[1];  // 第一行可能是封面，第二行是标题
                        }
                    }

                    // 提取数据：从文本中匹配图标后的数字
                    // 截图显示格式：👁 303 ❤ 0 💬 0 ↗ 0 👍 1
                    const fullText = item.innerText;

                    // 方法1：按图标/关键词分割提取
                    // 播放(👁/浏览/观看)、点赞(❤/👍/赞)、评论(💬/评论)、转发(↗/分享/转发)
                    const dataPatterns = [
                        {key: 'views', patterns: ['浏览', '播放', '观看', '👁', '👀']},
                        {key: 'likes', patterns: ['赞', '喜欢', '❤', '👍', '♥']},
                        {key: 'comments', patterns: ['评论', '回复', '💬']},
                        {key: 'shares', patterns: ['分享', '转发', '↗', '➡']}
                    ];

                    const data = {};

                    // 先尝试用正则提取所有"图标+数字"对
                    // 匹配模式：图标字符（可选空格）+ 数字（可能带万）
                    const iconNumberPattern = /(?:👁|👀|❤|👍|♥|💬|↗|➡|分享|转发|评论|赞|浏览|播放|观看)\s*(\d+(?:\.\d+)?(?:万|w)?)/gi;
                    const matches = fullText.matchAll(iconNumberPattern);
                    const extractedNumbers = [];

                    for (const match of matches) {
                        extractedNumbers.push(parseNumber(match[1]));
                    }

                    // 如果正则提取失败，用行分割法
                    if (extractedNumbers.length === 0) {
                        const lines = fullText.split('\\n');
                        // 找包含数字的行
                        const numberLines = lines.filter(line => /\\d/.test(line));
                        numberLines.forEach(line => {
                            const nums = line.match(/(\\d+(?:\\.\\d+)?(?:万|w)?)/g);
                            if (nums) {
                                nums.forEach(n => extractedNumbers.push(parseNumber(n)));
                            }
                        });
                    }

                    // 分配数字（通常顺序是：播放、点赞、评论、转发）
                    if (extractedNumbers.length >= 2) {
                        data.views = extractedNumbers[0] || 0;
                        data.likes = extractedNumbers[1] || 0;
                        data.comments = extractedNumbers[2] || 0;
                        data.shares = extractedNumbers[3] || 0;
                    }

                    // 获取发布时间（如果有）
                    const timeMatch = fullText.match(/(\\d{4}年\\d{2}月\\d{2}日|\\d{4}-\\d{2}-\\d{2}|\\d{2}月\\d{2}日|\\d{2}:\\d{2})/);
                    const publishTime = timeMatch ? timeMatch[0] : '';

                    if (title && (data.views > 0 || data.likes > 0)) {
                        results.push({
                            title: title.substring(0, 100),  // 限制长度
                            views: data.views,
                            likes: data.likes,
                            comments: data.comments,
                            shares: data.shares,
                            publishTime: publishTime,
                            rawText: fullText.substring(0, 200)  // 调试信息
                        });
                    }
                } catch (e) {
                    console.error('处理第' + index + '项出错:', e);
                }
            });

            return results;
        }""")

        print(f"📊 提取到 {len(videos)} 条视频数据")

        if videos and len(videos) > 0:
            # 整理数据
            data = []
            for v in videos:
                data.append({
                    '视频标题': v['title'],
                    '发布时间': v.get('publishTime', ''),
                    '播放量': v['views'],
                    '点赞量': v['likes'],
                    '评论量': v.get('comments', 0),
                    '转发量': v.get('shares', 0),
                    '平台': '视频号'
                })

            df = pd.DataFrame(data)

            # 计算互动指标
            df['点赞率%'] = (df['点赞量'] / df['播放量'] * 100).round(2)
            df['互动率%'] = ((df['点赞量'] + df['评论量'] + df['转发量']) / df['播放量'] * 100).round(2)

            # 导出
            today = datetime.now().strftime('%Y%m%d')
            filename = f'视频号周报_{today}.xlsx'
            df.to_excel(filename, index=False)

            print(f"\n✅ 成功导出：{filename}")
            print(f"📈 共 {len(df)} 条视频")
            print(f"👁️ 总播放：{df['播放量'].sum():,}")
            print(f"❤️ 总点赞：{df['点赞量'].sum():,}")
            print(f"💬 总评论：{df['评论量'].sum():,}")
            print(f"🔄 总转发：{df['转发量'].sum():,}")
            print(f"\n📋 数据预览：")
            print(df[['视频标题', '播放量', '点赞量', '评论量']].to_string())

        else:
            print("❌ 未能提取数据，尝试调试模式...")

            # 调试：输出页面所有文本内容
            debug_info = page.evaluate("""() => {
                // 获取"最近视频"区域的HTML
                const sections = document.querySelectorAll('div, section');
                let recentVideoSection = null;

                for (let s of sections) {
                    if (s.innerText.includes('最近视频') && s.innerText.includes('播放')) {
                        recentVideoSection = s;
                        break;
                    }
                }

                if (recentVideoSection) {
                    return {
                        text: recentVideoSection.innerText.substring(0, 1000),
                        html: recentVideoSection.outerHTML.substring(0, 2000)
                    };
                }
                return {text: '未找到最近视频区域', html: ''};
            }""")

            print("调试信息：", debug_info['text'])

            # 保存调试HTML
            with open('debug_final.html', 'w', encoding='utf-8') as f:
                f.write(debug_info['html'])
            print("💡 已保存调试HTML到 debug_final.html")

        browser.close()


if __name__ == "__main__":
    scrape_with_precise_selector()