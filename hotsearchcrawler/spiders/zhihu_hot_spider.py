import scrapy
from datetime import datetime
from hotsearchcrawler.items import HotItem


class ZhihuHotSpider(scrapy.Spider):
    name = 'zhihu_spider'
    start_urls = ['https://www.zhihu.com/hot']

    custom_settings = {
        'DEFAULT_REQUEST_HEADERS': {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Connection': 'keep-alive',
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
        hot_items = response.xpath('//div[@class="HotList-list"]/section[contains(@class, "HotItem")]')

        for idx, item in enumerate(hot_items, start=1):
            title = item.xpath('.//h2[@class="HotItem-title"]/text()').get()
            if title:
                title = title.strip()

            url = item.xpath('.//a[@class="HotItem-img"]/@href').get() or \
                  item.xpath('.//div[@class="HotItem-content"]/a/@href').get()
            if url:
                url = response.urljoin(url)

            if title and url:
                hot_item = HotItem()
                hot_item['platform_id'] = 21
                hot_item['rank'] = idx
                hot_item['title'] = title
                hot_item['author'] = '知乎博主'
                hot_item['url'] = url
                hot_item['crawl_time'] = datetime.now().isoformat()

                hot_item = hot_item.process_item()
                yield hot_item
