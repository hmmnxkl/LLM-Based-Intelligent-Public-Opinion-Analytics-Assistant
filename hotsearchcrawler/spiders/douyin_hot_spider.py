import json
import urllib.parse
from .base2_spider import DouyinHotSearchBaseSpider
import scrapy


class DouyinGeneralHotSpider(DouyinHotSearchBaseSpider):
    name = 'douyin_hot_hot'
    custom_settings = {
        'DOWNLOADER_MIDDLEWARES': {
            'hotsearchcrawler.douyinmiddlewares.RotateUserAgentMiddleware': 543,
            'hotsearchcrawler.douyinmiddlewares.DouyinAntiScrapMiddleware': 600,
        }
    }

    @property
    def platform_id(self):
        return 8

    @property
    def hotlist_url(self):
        return 'https://so-landing.douyin.com/aweme/v1/hot/search/list/?aid=581610&detail_list=1&board_type=0&board_sub_type=&need_board_tab=true&need_covid_tab=false&version_code=32.3.0'

    def parse_hotlist(self, response):
        try:
            data = json.loads(response.text)
            hot_items = data.get('data', {}).get('word_list', [])

            if not hot_items:
                self.logger.warning("未获取到热搜数据")
                return

            for item in hot_items:
                word = item.get('word', '').strip()
                group_id = item.get('group_id', '')
                rank = item.get('position', 0)

                if word and group_id:
                    detail_url = self.construct_detail_url(word, group_id, rank)
                    yield scrapy.Request(
                        url=detail_url,
                        callback=self.parse_detail,
                        meta={
                            'platform_id': response.meta['platform_id'],
                            'title': word,
                            'group_id': group_id,
                            'rank': rank
                        }
                    )
                else:
                    self.logger.warning("跳过无效的热搜项：缺少word或group_id")

        except Exception as e:
            self.logger.error(f"解析热榜JSON失败: {e}")

    def construct_detail_url(self, title, group_id, rank):
        base_url = "https://so.douyin.com/s"
        params = {
            "hideMiddlePage": 1,
            "needBack2Origin": 1,
            "from": "hot_list_page",
            "enter_method": "hot_list_page",
            "gid": group_id,
            "innerWidth": 1320,
            "innerHeight": 729,
            "reloadNavStart": 1753234048108,
            "is_no_width_reload": 0,
            "previous_page": "trending_board_page",
            "keyword": title,
            "hotlist_param": json.dumps({
                "board_type": 0,
                "rank": rank,
                "time": 1753234427
            }),
            "extra": json.dumps({
                "hotlist_param": json.dumps({
                    "board_type": 0,
                    "rank": rank,
                    "time": 1753234427
                }),
                "previous_page": "trending_board_page",
                "gid": group_id,
                "enter_method": "hot_list_page"
            })
        }

        encoded_params = urllib.parse.urlencode(params, safe=':/', quote_via=urllib.parse.quote)
        return f"{base_url}?{encoded_params}"

    def parse_detail(self, response):
        try:
            author = response.xpath('(//x-view[@class=\'video-author\']//x-text[@text-maxline=\'1\'])[1]').get()
            author = author.strip() if author else '未知作者'

            yield self.create_hot_item(
                response,
                title=response.meta['title'],
                author=author,
                rank=response.meta['rank']
            )

        except Exception as e:
            self.logger.error(f"解析详情页失败: {e}")
