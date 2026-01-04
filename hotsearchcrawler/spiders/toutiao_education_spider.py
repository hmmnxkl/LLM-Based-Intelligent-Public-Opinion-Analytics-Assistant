from urllib.parse import urljoin
from datetime import time
from .base_spider import BaseHotSpider


class ToutiaoHotSpider3(BaseHotSpider):
    name = 'Toutiao_education_hot'
    platform_id = 13
    custom_settings = {
        'DOWNLOADER_MIDDLEWARES': {
            'hotsearchcrawler.fakemiddlewares.SeleniumMiddleware': 400,
        }
    }
    start_url = 'https://tophub.today/n/nBe0NJDv37'
    start_url_1 = 'https://www.toutiao.com'

    topics_xpath = '/html/body/div[1]/div[3]/div/div[2]/div[2]/div[2]/div/div[1]/table/tbody/tr/td[2]/a/@href'
    article_title_xpath = '//div[@class=\'info\']//h2'
    article_author_xpath = '(//div[@class=\'left-tools\']//a)[1]'
    article_url_xpath = '(//div[@class=\'topic-blocks-wrapper\']//@href)[1]'

    def parse_topic(self, response):
        base_item_generator = super().parse_topic(response)

        try:
            item = next(base_item_generator)
        except StopIteration:
            self.logger.error("基类未生成任何 item")
            return

        article_url = response.xpath(self.article_url_xpath).get()
        if article_url:
            item['url'] = urljoin(self.start_url_1, article_url)

        yield item