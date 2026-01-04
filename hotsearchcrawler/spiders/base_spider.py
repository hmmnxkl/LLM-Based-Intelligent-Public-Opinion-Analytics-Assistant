import scrapy
import datetime
from hotsearchcrawler.items import HotItem


class BaseHotSpider(scrapy.Spider):
    custom_settings = {
        'DOWNLOAD_DELAY': 5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1
    }

    def start_requests(self):
        yield scrapy.Request(
            self.start_url,
            meta={'selenium': True},
            callback=self.parse_ranking
        )

    def parse_ranking(self, response):
        all_topics = response.xpath(self.topics_xpath).getall()

        if not all_topics:
            self.logger.error(f"未找到话题元素: {self.topics_xpath}")
            return

        max_topics = 50
        for i, topic_url in enumerate(all_topics[:max_topics]):
            rank = i + 1

            yield response.follow(
                topic_url,
                meta={
                    'selenium': True,
                    'rank': rank
                },
                callback=self.parse_topic
            )

    def parse_topic(self, response):
        item = HotItem()
        item['platform_id'] = self.platform_id
        item['rank'] = response.meta['rank']

        raw_title = response.xpath(self.article_title_xpath).get()
        item['title'] = raw_title if raw_title else ""

        raw_author = response.xpath(self.article_author_xpath).get()
        item['author'] = raw_author if raw_author else ""

        url = response.xpath(self.article_url_xpath).get()
        item['url'] = url if url else ""

        yield item
