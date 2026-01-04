import scrapy
import json
from datetime import datetime
from ..items import HotItem


class UCVideoSpider(scrapy.Spider):
    name = 'uc_video'
    PLATFORM_ID = 16
    API_URL = "https://iflow.uczzd.cn/iflow/api/v1/article/aggregation?page=1&count=20&auto=0&uc_param_str=dnnivebichfrmintcpgidsudsvmedizbssnwlobdpf&aggregation_id=10154620599484913764&enable_ad=0&type=21&bottom_pos=0&ss=360x719&de=AAS5GPX7YYvBw6xLfvKbvQS8dasjbJFuvvavqLudt%2BvWng%3D%3D&gi=bTkwBH2CsEgvjWiXXTZNHk%2Bdzw6I&bd=honor&sv=ucrelease&lo=AAQRAtQtd9XY54gmHPf775eHbuf%2BYbC9eehroE%2BrJhJ2hVnH8IpdbEg5gELNRVLXEQK8gX8h9OTHH7qf8GbaVImqKr1K74KaFD9MesZ3JdaxW07A5ogQxoY8LavvUKdMU2I%3D&ch=yzappstore%40&nt=2&bi=34464&zb=00000&nw=WIFI&dn=61177343034-ea334173&fr=android&ve=15.1.2.1202&ds=bTkwBEkwqZ1Xr3dJctxJ6etWgpZ%2Bc4ABBSP0732Z9rxUWw%3D%3D&pc=AAQRAtQtd9XY54gmHPf775eHbuf%2BYbC9eehroE%2BrJhJ2hVnH8IpdbEg5gELNRVLXEQLbXw0JGarhS15SUL8Z6ZUD&pf=145&ni=bTkwBAt%2BwXzj2hzR1j8DlAqoEqTw6zAjhGIkBu%2BbtrolLjY%3D&mi=OXF-AN10"

    headers = {
        'Accept': 'application/json',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Host': 'iflow.uczzd.cn',
        'Referer': 'https://www.uc.cn/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    def start_requests(self):
        yield scrapy.Request(
            url=self.API_URL,
            headers=self.headers,
            callback=self.parse
        )

    def parse(self, response):
        try:
            data = json.loads(response.text)
            articles = data['data']['articles']

            for idx, article in enumerate(articles, start=1):
                title = article.get('title', '')
                author = article.get('wm_author', {}).get('name', '未知作者')
                url = article.get('url', '')

                item = HotItem()
                item['platform_id'] = self.PLATFORM_ID
                item['rank'] = idx
                item['title'] = title
                item['author'] = author
                item['url'] = url
                item['crawl_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                item = item.process_item()
                yield item

        except (KeyError, IndexError, json.JSONDecodeError) as e:
            self.logger.error(f"解析数据失败: {e}，响应内容: {response.text[:200]}")
