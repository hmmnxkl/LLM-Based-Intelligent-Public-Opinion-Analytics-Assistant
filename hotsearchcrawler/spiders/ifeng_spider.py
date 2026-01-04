import scrapy
import json
import re
from datetime import datetime
from ..items import HotItem


class IfengSpider(scrapy.Spider):
    name = 'ifeng'
    start_urls = [
        'https://nine.ifeng.com/hotspotlist?page=1&gv=7.9.1&av=7.9.1&uid=ZkFHxz8WBsmwHTN&deviceid=ee988cd23e3159dc&proid=ifengnewsh5&os=android_29&df=androidphone&vt=5&screen=1080x1794&publishid=develop&nw=wifi&st=15712118293739&sn=0a19d617448ff2f0bd9df7497f80a4e3&dlt=40.011686&dln=116.497205&dcy=%2525E5%25258C%252597%2525E4%2525BA%2525AC%2525E5%2525B8%252582&dpr=%2525E5%25258C%252597%2525E4%2525BA%2525AC%2525E5%2525B8%252582&skinid=default&isnoad=1&nosign=1&callback=getHotNewsDataCallback'
    ]

    def parse(self, response):
        try:
            raw_data = response.text

            if raw_data.startswith('getHotNewsDataCallback(') and raw_data.endswith(');'):
                json_str = raw_data[23:-2]
                data = json.loads(json_str)
            else:
                self.logger.error(f"响应格式异常，前500字符: {raw_data[:500]}")
                return

            if data.get('code') != 0:
                self.logger.error(f"凤凰API返回错误: {data.get('msg')}")
                return

            hot_list = data.get('data', {}).get('list', [])
            if not hot_list:
                self.logger.error("凤凰热榜未获取到数据")
                return

            crawl_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            for index, item in enumerate(hot_list):
                title = item.get('title', '').strip()
                author = item.get('source', '').strip()

                link_data = item.get('link', {})
                url = (
                    link_data.get('weburl', '')
                    or item.get('shareInfo', {}).get('weburl', '')
                )

                if not title:
                    self.logger.warning(f"跳过标题为空的热搜项")
                    continue

                if not url:
                    self.logger.warning(f"跳过URL为空的热搜项: {title}")
                    continue

                hot_item = HotItem()
                hot_item['platform_id'] = 18
                hot_item['rank'] = index + 1
                hot_item['title'] = title
                hot_item['author'] = author if author else '凤凰新闻'
                hot_item['url'] = url
                hot_item['crawl_time'] = crawl_time

                hot_item = hot_item.process_item()

                yield hot_item

        except Exception as e:
            self.logger.error(f"解析凤凰热榜数据时出错: {str(e)}")
