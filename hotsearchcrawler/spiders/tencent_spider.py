import scrapy
import json
import datetime
from hotsearchcrawler.items import HotItem


class TencentSpider(scrapy.Spider):
    name = 'tencent_news'
    start_urls = [
        'https://r.inews.qq.com/getWeiboRankingList?chlid=news_recommend_hot&appver=28_android_6.8.00&devid=&qn-rid=&qn-sig=63b186047dc02809a9ec82e5c3ded91f&is_h5=1'
    ]

    def parse(self, response):
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            self.logger.error("响应不是有效的JSON格式")
            return

        if data.get('ret') != 0:
            self.logger.error(f"API返回错误: ret={data.get('ret')}")
            return

        news_list = data.get('idlist', [])
        if not news_list:
            self.logger.warning("未获取到新闻列表数据")
            return

        news_group = news_list[0] if news_list else {}
        news_items = news_group.get('newslist', [])

        if not news_items:
            self.logger.warning("未获取到新闻数据")
            return

        crawl_time = datetime.datetime.now().isoformat()

        for news in news_items:
            item = HotItem()
            item['platform_id'] = 20

            item['rank'] = news.get('ranking', 0)

            item['title'] = news.get('longtitle') or news.get('title') or ""

            item['url'] = news.get('url') or news.get('surl') or ""

            author = news.get('source') or ""
            if not author:
                card = news.get('card', {})
                author = card.get('chlname') or card.get('vip_desc') or ""
            item['author'] = author or "未知来源"

            item['crawl_time'] = crawl_time

            item = item.process_item()

            yield item