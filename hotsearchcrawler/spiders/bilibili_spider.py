import scrapy
import json
from datetime import datetime
from ..items import HotItem


class BilibiliSpider(scrapy.Spider):
    name = 'bilibili'

    start_urls = [
        'https://app.bilibili.com/x/v2/search/trending/ranking?limit=30'
    ]

    custom_settings = {
        'DEFAULT_REQUEST_HEADERS': {
            'Referer': 'https://www.bilibili.com/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    }

    def parse(self, response):
        try:
            data = json.loads(response.text)

            if data.get('code') != 0:
                self.logger.error(f"API返回错误: {data.get('message')}")
                return

            hot_list = data.get('data', {}).get('list', [])

            if not hot_list:
                self.logger.error("未获取到热搜数据")
                return

            crawl_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            for item in hot_list:
                keyword = item.get('keyword', '').strip()
                if not keyword:
                    self.logger.warning("遇到空关键词，跳过该条目")
                    continue

                hot_item = HotItem()
                hot_item['platform_id'] = 17
                hot_item['rank'] = item.get('position', 0)
                hot_item['title'] = keyword
                hot_item['author'] = 'bilibili博主'
                hot_item['url'] = f'https://search.bilibili.com/all?keyword={keyword}&from_source=webtop_search&spm_id_from=333.934&search_source=4'
                hot_item['crawl_time'] = crawl_time

                hot_item = hot_item.process_item()

                yield hot_item

        except Exception as e:
            self.logger.error(f"解析数据时出错: {str(e)}")
