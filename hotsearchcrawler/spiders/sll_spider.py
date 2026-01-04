from datetime import time
from urllib.parse import urljoin
import scrapy
from .base5_spder import BaseHotSpider


class SllHotSpider(BaseHotSpider):
    name = 'sll_hot'
    platform_id = 19
    custom_settings = {
        'DOWNLOADER_MIDDLEWARES': {
            'hotsearchcrawler.fakemiddlewares.SeleniumMiddleware1': 500,
        }
    }

    start_url = 'https://news.so.com/hotnews?src=hotnews'

    topics_xpath = '//div[@class="hotnews-main"]//li/a/@href'
    topic_title_xpath = '//div[@class="hotnews-main"]//li/a/span[@class="title"]/text()'
    article_author_xpath = '//li[@class="res-list"]//div[@class="mh-caption-inner"]//div[@class="mh-news-source"]'
    article_url_xpath = '(//li[@class="res-list"]//@href)[2]'

    def start_requests(self):
        yield scrapy.Request(
            self.start_url,
            meta={
                'selenium': True,
                'all_topics': [],
                'all_titles': [],
                'page': 1
            },
            callback=self.parse_ranking
        )

    def parse_ranking(self, response):
        all_topics = response.meta.get('all_topics', [])
        all_titles = response.meta.get('all_titles', [])
        current_page = response.meta.get('page', 1)

        self.logger.info(f"正在处理第 {current_page} 页")

        topics = response.xpath(self.topics_xpath).getall()
        titles = response.xpath(self.topic_title_xpath).getall()

        if not topics:
            self.logger.warning(f"第 {current_page} 页未找到话题链接")
        if not titles:
            self.logger.warning(f"第 {current_page} 页未找到话题标题")

        all_topics.extend(topics)
        all_titles.extend(titles)

        next_button = response.xpath('//button[contains(@class, "next") and not(contains(@class, "disabled"))]')

        if next_button:
            self.logger.info(f"发现下一页按钮，准备翻页到第 {current_page + 1} 页")

            yield scrapy.Request(
                self.start_url,
                meta={
                    'selenium': True,
                    'all_topics': all_topics,
                    'all_titles': all_titles,
                    'page': current_page + 1,
                    'click_xpath': '//button[@id="hot-next" and not(contains(@class, "disabled"))]'
                },
                dont_filter=True,
                callback=self.parse_ranking
            )
        else:
            self.logger.info(f"已到达最后一页，共 {current_page} 页，总计 {len(all_topics)} 条数据")

            for i, (topic_url, title) in enumerate(zip(all_topics, all_titles), 1):
                if not topic_url.startswith('http'):
                    topic_url = urljoin(self.start_url, topic_url)

                yield response.follow(
                    topic_url,
                    meta={
                        'selenium': True,
                        'rank': i,
                        'title': title.strip() if title else f"话题{i}",
                        'topic_url': topic_url
                    },
                    callback=self.parse_topic
                )
