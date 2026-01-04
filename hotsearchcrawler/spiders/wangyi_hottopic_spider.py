import json
from .base1_spider import HotSearchBaseSpider
import scrapy


class NetEaseSpider3(HotSearchBaseSpider):
    name = "wangyi_hottopic_hot"
    platform_id = 7
    custom_settings = {
        'DOWNLOADER_MIDDLEWARES': {
            'hotsearchcrawler.wangyimiddlewares.RotateUserAgentMiddleware': 543,
            'hotsearchcrawler.wangyimiddlewares.NetEaseCookieMiddleware': 600,
            'hotsearchcrawler.wangyimiddlewares.ErrorHandleMiddleware': 800,
        }
    }

    def start_requests(self):
        url = "https://gw.m.163.com/nc/api/v1/feed/dynamic/topic/hotList"
        yield scrapy.Request(url, callback=self.parse)

    def parse(self, response):
        raw_data = response.text
        self.logger.debug(f"原始响应内容: {raw_data[:1000]}...")

        try:
            data = json.loads(raw_data)
            self.logger.info(f"解析到的JSON数据: {data}")

            articles = data.get("data", {}).get("items", [])
            if not articles:
                self.logger.warning("未找到文章列表，可能接口结构已变更")
                return

            for idx, article in enumerate(articles, start=1):
                title = article.get("title")
                author = "网易博主"
                detail_url = article.get("url")

                if not detail_url:
                    self.logger.error("文章详情页URL缺失")
                    continue

                item = self.create_item(title, author, detail_url)
                if item:
                    item['rank'] = idx
                    self.logger.info(f"成功生成Item: {item}")
                    yield item
                else:
                    self.logger.error("create_item 返回了 None，跳过当前文章")
        except Exception as e:
            self.logger.error(f"解析文章详情页失败: {e}\nURL: {response.url}")
