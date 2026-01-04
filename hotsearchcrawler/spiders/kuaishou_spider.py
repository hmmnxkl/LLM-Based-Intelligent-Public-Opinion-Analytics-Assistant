import scrapy
import re
import time
from hotsearchcrawler.items import HotItem
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from scrapy.http import HtmlResponse


class KuaishouHotSpider(scrapy.Spider):
    name = "kuaishou_hot"
    start_urls = ["https://www.kuaishou.com/brilliant"]

    custom_settings = {
        'CONCURRENT_REQUESTS': 1,
        'DOWNLOAD_DELAY': 3,
        'RETRY_TIMES': 3,
        'COOKIES_ENABLED': True
    }

    def __init__(self, *args, **kwargs):
        super(KuaishouHotSpider, self).__init__(*args, **kwargs)

        try:
            from selenium.webdriver.edge.options import Options as EdgeOptions
            from selenium.webdriver.edge.service import Service as EdgeService

            edge_options = EdgeOptions()
            edge_options.add_argument('--headless')
            edge_options.add_argument('--disable-gpu')
            edge_options.add_argument('--no-sandbox')
            edge_options.add_argument('--disable-dev-shm-usage')
            edge_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0')

            self.driver = webdriver.Edge(
                service=EdgeService(),
                options=edge_options
            )
            self.logger.info("✅ Edge浏览器驱动初始化成功")

        except Exception as edge_error:
            self.logger.warning(f"❌ Edge浏览器驱动初始化失败: {edge_error}")
            self.logger.info("尝试使用Chrome/Chromium浏览器...")

            try:
                from selenium.webdriver.chrome.options import Options as ChromeOptions
                from selenium.webdriver.chrome.service import Service as ChromeService

                chrome_options = ChromeOptions()
                chrome_options.add_argument('--headless')
                chrome_options.add_argument('--disable-gpu')
                chrome_options.add_argument('--no-sandbox')
                chrome_options.add_argument('--disable-dev-shm-usage')
                chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36')

                self.driver = webdriver.Chrome(
                    service=ChromeService(),
                    options=chrome_options
                )
                self.logger.info("✅ Chrome/Chromium浏览器驱动初始化成功")

            except Exception as chrome_error:
                self.logger.error(f"❌ Chrome/Chromium浏览器驱动初始化失败: {chrome_error}")
                raise Exception("所有浏览器驱动初始化都失败，请安装Edge或Chrome浏览器并配置相应驱动")

        try:
            self.driver.get("https://www.kuaishou.com")
            self.driver.add_cookie({
                'name': 'kpf',
                'value': 'PC_WEB',
                'domain': '.kuaishou.com'
            })
            self.driver.add_cookie({
                'name': 'clientid',
                'value': '3',
                'domain': '.kuaishou.com'
            })
        except Exception as e:
            self.logger.warning(f"设置Cookie时出错: {e}")

    def closed(self, reason):
        self.driver.quit()

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                callback=self.parse,
                meta={'dont_merge_cookies': True}
            )

    def parse(self, response):
        self.driver.get(response.url)

        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'rank-content'))
            )
        except Exception as e:
            self.logger.error(f"等待元素加载超时: {str(e)}")
            return

        has_pagination = False
        try:
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'page'))
            )
            has_pagination = True
            self.logger.info("检测到翻页控件，开始翻页操作")
        except:
            self.logger.info("未检测到翻页控件，直接爬取数据")

        if has_pagination:
            try:
                total_pages_element = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '.page .total'))
                )
                total_pages = int(total_pages_element.text)
                self.logger.info(f"总页码数: {total_pages}")
            except Exception as e:
                self.logger.error(f"获取总页码数失败: {str(e)}")
                total_pages = 1

            for page in range(1, total_pages):
                try:
                    try:
                        overlay = WebDriverWait(self.driver, 3).until(
                            EC.presence_of_element_located((By.XPATH, "//div[contains(@style, 'position: absolute') and contains(@style, 'inset: 0px')]"))
                        )
                        self.driver.execute_script("arguments[0].remove();", overlay)
                        self.logger.info("检测到并移除遮罩层")
                        time.sleep(1)
                    except:
                        pass

                    next_btn = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, '.page-btn.next'))
                    )

                    self.driver.execute_script("arguments[0].click();", next_btn)

                    WebDriverWait(self.driver, 5).until(
                        EC.text_to_be_present_in_element(
                            (By.CSS_SELECTOR, '.page .current'),
                            str(page + 1)
                        )
                    )

                    time.sleep(2)
                    self.logger.info(f"已翻到第 {page + 1} 页")

                except Exception as e:
                    self.logger.error(f"翻页到第 {page + 1} 页失败: {str(e)}")
                    break

            try:
                while True:
                    current_page_element = self.driver.find_element(By.CSS_SELECTOR, '.page .current')
                    current_page = int(current_page_element.text)
                    if current_page == 1:
                        break
                    prev_btn = self.driver.find_element(By.CSS_SELECTOR, '.page-btn.prev')
                    prev_btn.click()
                    time.sleep(1)
                time.sleep(2)
                self.logger.info("已返回第一页，准备开始爬取")
            except Exception as e:
                self.logger.error(f"返回第一页失败: {str(e)}")

        body = self.driver.page_source
        selenium_response = HtmlResponse(
            url=self.driver.current_url,
            body=body,
            encoding='utf-8'
        )

        return self.parse_hot_list(selenium_response)

    def parse_hot_list(self, response):
        rank_items = response.xpath('//div[@class="rank-content"]/div')

        if not rank_items:
            self.logger.error("未找到任何热榜条目")
            return

        crawl_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        for rank, item in enumerate(rank_items, start=1):
            try:
                title = item.xpath('.//div[@class="video-info"]//h5/text()').get()
                if title:
                    title = title.strip()
                else:
                    self.logger.warning(f"跳过标题为空的热搜项（排名 {rank}）")
                    continue

                img_src = item.xpath('.//img[@class="poster-img"]/@src').get()

                client_cache_key = None
                if img_src:
                    match = re.search(r'clientCacheKey=([^&]+)', img_src)
                    if match:
                        client_cache_key = match.group(1).replace('.jpg', '')

                if not client_cache_key:
                    self.logger.warning(f"无法从图片地址中提取clientCacheKey（标题：{title}）")
                    img_src = item.xpath('.//img[@class="poster-img"]/@data-ks-lazyload').get()
                    if img_src:
                        match = re.search(r'clientCacheKey=([^&]+)', img_src)
                        if match:
                            client_cache_key = match.group(1).replace('.jpg', '')
                    if not client_cache_key:
                        self.logger.warning(f"跳过无法提取clientCacheKey的热搜项: {title}")
                        continue

                url = f"https://www.kuaishou.com/short-video/{client_cache_key}?streamSource=hotrank&trendingId={title}&area=brilliantxxunknown"

                hot_item = HotItem()
                hot_item['platform_id'] = 14
                hot_item['rank'] = rank
                hot_item['title'] = title
                hot_item['author'] = "快手博主"
                hot_item['url'] = url
                hot_item['crawl_time'] = crawl_time

                hot_item = hot_item.process_item()

                yield hot_item

            except Exception as e:
                self.logger.error(f"处理排名 {rank} 的热搜项时出错: {str(e)}")
