import abc
import scrapy
from ..items import HotItem


class DouyinHotSearchBaseSpider(scrapy.Spider, abc.ABC):

    @property
    @abc.abstractmethod
    def platform_id(self):
        pass

    @property
    @abc.abstractmethod
    def hotlist_url(self):
        pass

    @abc.abstractmethod
    def parse_hotlist(self, response):
        pass

    @abc.abstractmethod
    def construct_detail_url(self, title, group_id, rank):
        pass

    @abc.abstractmethod
    def parse_detail(self, response):
        pass

    def start_requests(self):
        yield scrapy.Request(
            url=self.hotlist_url,
            callback=self.parse_hotlist,
            meta={'platform_id': self.platform_id}
        )

    def create_hot_item(self, response, title, author, rank):
        item = HotItem()
        item['platform_id'] = response.meta['platform_id']
        item['rank'] = rank
        item['title'] = title
        item['author'] = author
        item['url'] = response.url
        return item
