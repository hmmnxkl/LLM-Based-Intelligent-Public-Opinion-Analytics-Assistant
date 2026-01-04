import scrapy
import datetime
from hotsearchcrawler.items import HotItem


class BaseHotSpider(scrapy.Spider):
    custom_settings = {
        'DOWNLOAD_DELAY': 5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,

        'PROXY_PROTOCOL': '',
        'PROXY_HOST': '',
        'PROXY_PORT': '',
        'PROXY_USER': '',
        'PROXY_PASS': ''
    }

    def start_requests(self):
        yield scrapy.Request(
            self.start_url,
            meta={'selenium': True},
            callback=self.parse_ranking
        )

    def parse_ranking(self, response):
        first_topic = response.xpath(self.first_topic_xpath).get()
        if first_topic:
            yield response.follow(
                first_topic,
                meta={'selenium': True},
                callback=self.parse_topic
            )
        else:
            self.logger.error(f"未找到话题元素: {self.first_topic_xpath}")

    def parse_topic(self, response):
        item = HotItem()
        item['platform_id'] = self.platform_id

        raw_title = response.xpath(self.article_title_xpath).get()
        item['title'] = raw_title if raw_title else ""

        raw_author = response.xpath(self.article_author_xpath).get()
        item['author'] = raw_author if raw_author else ""

        url = response.xpath(self.article_url_xpath).get()
        item['url'] = url if url else ""

        yield item
