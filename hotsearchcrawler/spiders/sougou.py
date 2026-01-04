import scrapy
import datetime
from hotsearchcrawler.items import HotItem


class Sougou(scrapy.Spider):
    name = 'sougou'

    PLATFORM_ID = 25

    start_urls = [
        'https://mini.itunes123.com/node/rfRMf23AFe/',
    ]

    custom_settings = {
        'DOWNLOAD_DELAY': 2,
        'CONCURRENT_REQUESTS': 1,
        'ROBOTSTXT_OBEY': False,
    }

    def parse(self, response):
        try:
            titles = response.xpath('//li[@class="c-text"]//a/@title').getall()

            self.logger.info(f"提取到 {len(titles)} 个标题")

            for index, title in enumerate(titles, 1):
                try:
                    cleaned_title = title.strip()
                    if not cleaned_title or len(cleaned_title) < 2:
                        continue
                    url = f"https://www.sogou.com/sogou?query={title}"
                    author = "搜狗"

                    hot_item = HotItem()
                    hot_item['platform_id'] = self.PLATFORM_ID
                    hot_item['rank'] = index
                    hot_item['title'] = cleaned_title
                    hot_item['author'] = author
                    hot_item['url'] = url
                    hot_item['crawl_time'] = datetime.datetime.now()

                    yield hot_item

                    self.logger.info(f"生成第 {index} 条记录: {cleaned_title}")

                except Exception as e:
                    self.logger.error(f"处理第 {index} 个标题时出错: {str(e)}")
                    continue

        except Exception as e:
            self.logger.error(f"解析热榜页面时出错: {str(e)}")
            yield None
