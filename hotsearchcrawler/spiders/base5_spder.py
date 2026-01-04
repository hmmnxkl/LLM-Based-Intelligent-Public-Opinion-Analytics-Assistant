import scrapy
import datetime
from urllib.parse import urljoin
from hotsearchcrawler.items import HotItem


class BaseHotSpider(scrapy.Spider):
    custom_settings = {
        'DOWNLOAD_DELAY': 5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1
    }

    topic_title_xpath = None

    def start_requests(self):
        yield scrapy.Request(
            self.start_url,
            meta={'selenium': True},
            callback=self.parse_ranking
        )

    def parse_ranking(self, response):
        all_topics = response.xpath(self.topics_xpath).getall()
        all_titles = response.xpath(self.topic_title_xpath).getall()

        if not all_topics:
            self.logger.error(f"未找到话题元素: {self.topics_xpath}")
            return
        if not all_titles:
            self.logger.error(f"未找到标题元素: {self.topic_title_xpath}")
            return

        min_count = min(len(all_topics), len(all_titles))
        max_topics = min(50, min_count)
        for i in range(max_topics):
            topic_url = all_topics[i]
            title = all_titles[i]
            rank = i + 1

            if not topic_url.startswith('http'):
                topic_url = urljoin(self.start_url, topic_url)

            yield response.follow(
                topic_url,
                meta={
                    'selenium': True,
                    'rank': rank,
                    'title': title,
                    'topic_url': topic_url
                },
                callback=self.parse_topic
            )

    def parse_topic(self, response):
        item = HotItem()
        item['platform_id'] = self.platform_id
        item['rank'] = response.meta['rank']
        item['title'] = response.meta['title']

        raw_author = response.xpath(self.article_author_xpath).get()
        item['author'] = raw_author if raw_author else "未知来源"

        article_url = response.xpath(self.article_url_xpath).get()
        if article_url:
            if not article_url.startswith('http'):
                article_url = urljoin(self.start_url, article_url)
            item['url'] = article_url
        else:
            item['url'] = response.meta['topic_url']
            self.logger.warning(f"文章URL为空，使用话题页URL: {item['url']}")

        yield item
