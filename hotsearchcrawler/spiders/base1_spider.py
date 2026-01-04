import scrapy
from hotsearchcrawler.items import HotItem


class HotSearchBaseSpider(scrapy.Spider):
    name = "hotsearch_base"
    platform_id = None

    def start_requests(self):
        raise NotImplementedError("Subclasses must implement start_requests")

    def parse(self, response):
        raise NotImplementedError("Subclasses must implement parse")

    def create_item(self, title, author, url):
        return HotItem(
            platform_id=self.platform_id,
            title=title,
            author=author,
            url=url,
            crawl_time=None
        )
