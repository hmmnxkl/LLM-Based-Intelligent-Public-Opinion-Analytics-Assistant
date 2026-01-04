import scrapy
import json
from hotsearchcrawler.items import HotItem
import time


class BaseHotSpider(scrapy.Spider):
    platform_id = None
    name = None
    allowed_domains = []
    start_urls = []

    def parse(self, response):
        try:
            data = json.loads(response.text)
            if data['code'] != 0:
                self.logger.error(f"API返回错误: {data['message']}")
                return

            rank_list = data['data'].get('rank_list', [])
            if not rank_list:
                self.logger.warning("未找到普通榜数据")
                return

            crawl_time = int(time.time())

            for rank_item in rank_list:
                item = HotItem()
                item['platform_id'] = self.platform_id
                item['title'] = rank_item.get('title', '')
                original_url = rank_item.get('url', '')
                item['url'] = original_url
                item['rank'] = int(rank_item.get('rank', 0)) + 1
                item['crawl_time'] = crawl_time

                if (hasattr(self, 'NEED_AUTHOR') and self.NEED_AUTHOR) or \
                   (hasattr(self, 'NEED_FINAL_URL') and self.NEED_FINAL_URL):
                    yield scrapy.Request(
                        url=original_url,
                        callback=self.parse_detail_page,
                        meta={
                            'item': item,
                            'dont_redirect': True,
                            'handle_httpstatus_list': [301, 302]
                        },
                        dont_filter=True
                    )
                else:
                    yield item.process_item()

        except Exception as e:
            self.logger.error(f"解析JSON失败: {e}")

    def parse_detail_page(self, response):
        item = response.meta['item']

        final_url = self.extract_final_url(response)
        if final_url:
            item['url'] = final_url
        else:
            item['url'] = response.url
            self.logger.warning(f"无法通过XPath提取最终URL，使用响应URL: {response.url}")

        if hasattr(self, 'NEED_AUTHOR') and self.NEED_AUTHOR:
            item = self.extract_author(item, response)

        yield item.process_item()

    def extract_final_url(self, response):
        raise NotImplementedError("子类必须实现extract_final_url方法")

    def extract_author(self, item, response):
        raise NotImplementedError("子类必须实现extract_author方法")
