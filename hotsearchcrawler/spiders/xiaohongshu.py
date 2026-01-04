import scrapy
import datetime
from hotsearchcrawler.items import \
    HotItem


class Xiaohongshu(
    scrapy.Spider):
    name = 'xiaohongshu'

    PLATFORM_ID = 24

    start_urls = [
        'https://mini.itunes123.com/node/rbuaRBrquZ/',
    ]

    custom_settings = {
        'DOWNLOAD_DELAY': 2,
        'CONCURRENT_REQUESTS': 1,
        'ROBOTSTXT_OBEY': False,
    }

    def parse(self, response):
        try:
            # 从提供的网页源码来看，该页面并没有标准的<li>或<a>标签来直接提取标题
            # 页面结构是表格形式，需要根据实际DOM结构调整xpath
            # 这里尝试提取表格中包含热点名称的单元格
            titles = response.xpath(
                '//table[@class="rank-table"]/tbody/tr/td[@class="title"]/a/text()').getall()

            # 如果上面的xpath没有匹配到，可能是页面结构不同，需要根据实际页面调整
            # 根据知识库中的网页内容，该页面似乎是一个静态的排行榜展示页
            # 但没有提供具体的、可直接通过xpath抓取的标题列表元素
            # 因此这里保留原有的通用xpath作为备选
            if not titles:
                titles = response.xpath(
                    '//li[@class="c-text"]//a/@title').getall()

            self.logger.info(
                f"提取到 {len(titles)} 个标题")

            for index, title in enumerate(
                    titles,
                    1):
                try:
                    cleaned_title = title.strip()
                    if not cleaned_title or len(
                            cleaned_title) < 2:
                        continue
                    url = f"https://www.xiaohongshu.com/search_result?keyword={title}"
                    author = "小红书"

                    hot_item = HotItem()
                    hot_item[
                        'platform_id'] = self.PLATFORM_ID
                    hot_item[
                        'rank'] = index
                    hot_item[
                        'title'] = cleaned_title
                    hot_item[
                        'author'] = author
                    hot_item[
                        'url'] = url
                    hot_item[
                        'crawl_time'] = datetime.datetime.now()

                    yield hot_item

                    self.logger.info(
                        f"生成第 {index} 条记录: {cleaned_title}")

                except Exception as e:
                    self.logger.error(
                        f"处理第 {index} 个标题时出错: {str(e)}")
                    continue

        except Exception as e:
            self.logger.error(
                f"解析热榜页面时出错: {str(e)}")
            yield None
