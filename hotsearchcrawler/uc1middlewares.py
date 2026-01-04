import random
from scrapy import signals


class RotateUserAgentMiddleware:
    def __init__(self, user_agents):
        self.user_agents = user_agents

    @classmethod
    def from_crawler(cls, crawler):
        settings = crawler.settings
        user_agents = settings.get('USER_AGENTS', [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1'
        ])
        middleware = cls(user_agents)
        crawler.signals.connect(middleware.spider_opened, signals.spider_opened)
        return middleware

    def spider_opened(self, spider):
        spider.logger.info(f"Using RotateUserAgentMiddleware with {len(self.user_agents)} user agents")

    def process_request(self, request, spider):
        if self.user_agents:
            request.headers['User-Agent'] = random.choice(self.user_agents)


class UCRefererMiddleware:
    def process_request(self, request, spider):
        if 'ff.dayu.com/contents' in request.url:
            if 'wm_cid' in request.meta:
                wm_cid = request.meta['wm_cid']
                request.headers['Referer'] = f'https://ff.dayu.com/detail/{wm_cid}'
        elif 'your-uc-hotlist-api-url' in request.url:
            request.headers['Referer'] = 'https://www.uc.cn/'
