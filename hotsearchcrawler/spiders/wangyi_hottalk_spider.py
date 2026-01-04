import json
from .base1_spider import HotSearchBaseSpider
import scrapy


class NetEaseSpider(HotSearchBaseSpider):
    name = "wangyi_hottalk_hot"
    platform_id = 4
    custom_settings = {
        'DOWNLOADER_MIDDLEWARES': {
            'hotsearchcrawler.wangyimiddlewares.RotateUserAgentMiddleware': 543,
            'hotsearchcrawler.wangyimiddlewares.NetEaseCookieMiddleware': 600,
            'hotsearchcrawler.wangyimiddlewares.ErrorHandleMiddleware': 800,
        }
    }

    def start_requests(self):
        url = "https://gw.m.163.com/gentie-web/api/v2/products/a2869674571f77b5a0867c3d71db5856/rankDocs/all/list?ibc=newsapph5&limit=30"
        yield scrapy.Request(url, callback=self.parse)

    def parse(self, response):
        raw_data = response.text
        self.logger.debug(f"原始响应内容: {raw_data[:1000]}...")

        try:
            data = json.loads(raw_data)
            self.logger.info(f"解析到的JSON数据: {data}")

            articles = data.get("data", {}).get("cmtDocs", [])
            if not articles:
                self.logger.warning("未找到文章列表，可能接口结构已变更")
                return

            for idx, article in enumerate(articles, start=1):
                doc_id = article.get("docId")
                title = article.get("doc_title")
                author = article.get("source")
                url = f"https://c.m.163.com/news/a/{doc_id}.html"

                if not all([doc_id, title]):
                    self.logger.error(f"字段缺失：doc_id={doc_id}, title={title}, author={author}")
                    continue

                item = self.create_item(title, author, url)
                if item:
                    item['rank'] = idx
                    self.logger.info(f"成功生成Item: {item}")
                    yield item
                else:
                    self.logger.error("create_item 返回了 None，跳过当前文章")

        except json.JSONDecodeError as e:
            self.logger.error(f"JSON解析失败: {e}\n响应内容: {response.text}")
