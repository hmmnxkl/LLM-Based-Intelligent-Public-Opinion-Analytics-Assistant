import scrapy
from datetime import datetime
from urllib.parse import quote
from hotsearchcrawler.items import HotItem


class ZhihuSearchSpider(scrapy.Spider):
    name = 'zhihu_search_spider'
    start_urls = ['https://www.zhihu.com/topsearch']

    custom_settings = {
        'DEFAULT_REQUEST_HEADERS': {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.zhihu.com/',
            'Host': 'www.zhihu.com'
        }
    }

    def start_requests(self):
        zhihu_cookies = self.settings.get('ZHIHU_COOKIES', {})

        for url in self.start_urls:
            yield scrapy.Request(
                url=url,
                cookies=zhihu_cookies,
                callback=self.parse
            )

    def parse(self, response):
        search_items = response.xpath('//div[@class="TopSearchMain"]//div[contains(@class, "TopSearchMain-item")]')

        for idx, item in enumerate(search_items, start=1):
            title = item.xpath('.//div[@class="TopSearchMain-title"]/text()').get()
            if title:
                title = title.strip()
            else:
                title_text_list = item.xpath('.//div[@class="TopSearchMain-title"]//text()').getall()
                if title_text_list:
                    title = ''.join([text.strip() for text in title_text_list if text.strip()])
                else:
                    continue

            hot_item = HotItem()
            hot_item['platform_id'] = 22
            hot_item['rank'] = idx
            hot_item['title'] = title
            hot_item['author'] = '知乎博主'
            encoded_title = quote(title)
            hot_item['url'] = f"https://www.zhihu.com/search?type=content&q={encoded_title}"
            hot_item['crawl_time'] = datetime.now().isoformat()

            hot_item = hot_item.process_item()
            yield hot_item
