import json
import time
import re
from datetime import datetime
from urllib.parse import quote
from selenium import webdriver
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .base1_spider import HotSearchBaseSpider
from hotsearchcrawler.items import HotItem
import scrapy


class NetEaseSpider2(HotSearchBaseSpider):
    name = "wangyi_hotsearch_hot"
    platform_id = 6
    custom_settings = {
        'DOWNLOADER_MIDDLEWARES': {
            'hotsearchcrawler.wangyimiddlewares.RotateUserAgentMiddleware': 543,
            'hotsearchcrawler.wangyimiddlewares.NetEaseCookieMiddleware': 600,
            'hotsearchcrawler.wangyimiddlewares.ErrorHandleMiddleware': 800,
        },
        'RETRY_ENABLED': True,
        'RETRY_TIMES': 3,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        try:
            from selenium.webdriver.edge.options import Options as EdgeOptions

            edge_options = EdgeOptions()
            edge_options.add_argument("--headless")
            edge_options.add_argument("--no-sandbox")
            edge_options.add_argument("--disable-dev-shm-usage")
            edge_options.add_argument("--disable-gpu")
            edge_options.add_argument("--window-size=1920,1080")
            edge_options.add_argument("user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1")

            self.driver = webdriver.Edge(options=edge_options)
            self.logger.info("✅ Edge浏览器驱动初始化成功")

        except Exception as edge_error:
            self.logger.warning(f"❌ Edge浏览器驱动初始化失败: {edge_error}")
            self.logger.info("尝试使用Chrome/Chromium浏览器...")

            try:
                from selenium.webdriver.chrome.options import Options as ChromeOptions

                chrome_options = ChromeOptions()
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")
                chrome_options.add_argument("--disable-gpu")
                chrome_options.add_argument("--window-size=1920,1080")
                chrome_options.add_argument("user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1")

                self.driver = webdriver.Chrome(options=chrome_options)
                self.logger.info("✅ Chrome/Chromium浏览器驱动初始化成功")

            except Exception as chrome_error:
                self.logger.error(f"❌ Chrome/Chromium浏览器驱动初始化失败: {chrome_error}")
                raise Exception("所有浏览器驱动初始化都失败，请安装Edge或Chrome浏览器并配置相应驱动")

        self.wait = WebDriverWait(self.driver, 15)

    def closed(self, spider):
        try:
            if hasattr(self, 'driver') and self.driver:
                self.driver.quit()
        except Exception as e:
            self.logger.error(f"关闭浏览器时出错: {e}")

    def extract_clean_title(self, raw_html):
        if not raw_html:
            return ""

        clean_title = re.sub(r'<em>|</em>', '', raw_html)
        clean_title = re.sub(r'\s+', ' ', clean_title).strip()
        return clean_title

    def get_detail_url_from_card(self, card_element):
        try:
            link_elements = card_element.find_elements(By.CSS_SELECTOR, "a[href]")
            for link in link_elements:
                href = link.get_attribute("href")
                if href and ("163.com" in href or "news.163.com" in href) and "keyword=" not in href:
                    return href
        except Exception as e:
            self.logger.debug(f"查找卡片内a标签失败: {e}")

        try:
            parent_link = card_element.find_element(By.XPATH, "./ancestor::a[@href]")
            if parent_link:
                href = parent_link.get_attribute("href")
                if href and ("163.com" in href or "news.163.com" in href) and "keyword=" not in href:
                    return href
        except Exception as e:
            self.logger.debug(f"查找父级a标签失败: {e}")

        return None

    def get_first_news_detail_url(self, keyword):
        try:
            search_url = f"https://m.163.com/search?keyword={quote(keyword)}"
            self.driver.get(search_url)
            self.logger.info(f"加载搜索页: {search_url}")

            search_result_section = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "article.searchResult"))
            )

            time.sleep(2)

            news_cards = self.driver.find_elements(By.CSS_SELECTOR, "article.searchResult .newsCard")
            if not news_cards:
                self.logger.warning("未找到新闻卡片")
                return None

            first_card = news_cards[0]
            self.logger.info("找到第一个新闻卡片")

            detail_url = self.get_detail_url_from_card(first_card)

            if not detail_url:
                self.logger.info("直接获取URL失败，尝试点击卡片")
                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", first_card)
                time.sleep(1)

                main_window = self.driver.current_window_handle

                card_title = ""
                try:
                    title_element = first_card.find_element(By.CSS_SELECTOR, ".card-title .s-title")
                    card_title = title_element.get_attribute("innerHTML")
                except:
                    pass

                try:
                    clickable_elements = first_card.find_elements(By.CSS_SELECTOR, "a")
                    clicked = False
                    for element in clickable_elements:
                        try:
                            element.click()
                            clicked = True
                            break
                        except:
                            continue

                    if not clicked:
                        self.driver.execute_script("arguments[0].click();", first_card)

                    time.sleep(2)

                    if len(self.driver.window_handles) > 1:
                        for handle in self.driver.window_handles:
                            if handle != main_window:
                                self.driver.switch_to.window(handle)
                                detail_url = self.driver.current_url
                                self.driver.close()
                                self.driver.switch_to.window(main_window)
                                break
                    else:
                        current_url = self.driver.current_url
                        if current_url != search_url:
                            detail_url = current_url
                            self.driver.back()
                            time.sleep(1)

                except Exception as e:
                    self.logger.error(f"点击卡片失败: {e}")

            if detail_url and ("163.com" in detail_url or "news.163.com" in detail_url) and "keyword=" not in detail_url:
                self.logger.info(f"✅ 成功获取详情页URL: {detail_url}")
                return detail_url
            else:
                self.logger.warning(f"获取的URL无效: {detail_url}")
                return None

        except Exception as e:
            self.logger.error(f"❌ 获取热词 '{keyword}' 的第一个新闻详情页失败: {e}")
            try:
                screenshot_path = f"/tmp/netease_error_{int(time.time())}.png"
                self.driver.save_screenshot(screenshot_path)
                self.logger.info(f"错误截图已保存至: {screenshot_path}")
            except:
                pass
            return None

    def start_requests(self):
        url = "https://gw.m.163.com/search/api/v2/hot-search"
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
            "Referer": "https://m.163.com/",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        yield scrapy.Request(url, callback=self.parse, headers=headers)

    def parse(self, response):
        try:
            data = json.loads(response.text)
            articles = data.get("data", {}).get("hotRank", [])
            if not articles:
                self.logger.warning("⚠️ 未找到热榜文章列表")
                return

            crawl_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            for idx, article in enumerate(articles, start=1):
                raw_title = article.get("searchWord")
                if not raw_title:
                    self.logger.error(f"第 {idx} 条热词标题为空，跳过")
                    continue

                self.logger.info(f"🔍 正在处理第 {idx} 名热词: {raw_title}")

                clean_title = self.extract_clean_title(raw_title)
                self.logger.debug(f"清理后的标题: {clean_title}")

                detail_url = self.get_first_news_detail_url(clean_title)

                search_url = f"https://m.163.com/search?keyword={quote(clean_title)}"

                if not detail_url:
                    detail_url = search_url
                    self.logger.warning(f"⚠️ 使用搜索页URL作为备用: {search_url}")

                try:
                    item = self.create_item(
                        title=clean_title,
                        author="网易新闻",
                        url=detail_url
                    )

                    if not item:
                        item = HotItem()
                        item['platform_id'] = self.platform_id
                        item['title'] = clean_title
                        item['author'] = "网易新闻"
                        item['url'] = detail_url
                        item['crawl_time'] = crawl_time

                except Exception as e:
                    self.logger.error(f"创建项目时出错: {e}")
                    item = HotItem()
                    item['platform_id'] = self.platform_id
                    item['title'] = clean_title
                    item['author'] = "网易新闻"
                    item['url'] = detail_url
                    item['crawl_time'] = crawl_time

                item['rank'] = idx
                self.logger.info(f"✅ 成功生成 Item: {dict(item)}")
                yield item

        except json.JSONDecodeError as e:
            self.logger.error(f"❌ JSON 解析失败: {e}\n响应内容片段: {response.text[:500]}")
        except Exception as e:
            self.logger.error(f"❌ 处理热榜数据时发生意外错误: {e}")
