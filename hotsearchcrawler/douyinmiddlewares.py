import random
import logging
from scrapy import signals
from scrapy.downloadermiddlewares.useragent import UserAgentMiddleware


class RotateUserAgentMiddleware(UserAgentMiddleware):
    def __init__(self, user_agents):
        self.user_agents = user_agents
        self.logger = logging.getLogger(__name__)

    @classmethod
    def from_crawler(cls, crawler):
        settings = crawler.settings
        user_agents = settings.get('USER_AGENTS', [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1'
        ])
        return cls(user_agents)

    def process_request(self, request, spider):
        user_agent = random.choice(self.user_agents)
        request.headers['User-Agent'] = user_agent
        self.logger.debug(f"使用User-Agent: {user_agent}")


class DouyinAntiScrapMiddleware:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    @classmethod
    def from_crawler(cls, crawler):
        return cls()

    def process_request(self, request, spider):
        if 'douyin.com' in request.url:
            request.headers['Referer'] = 'https://www.douyin.com/'
            request.headers['Accept'] = 'application/json, text/javascript, */*; q=0.01'
            request.headers['X-Requested-With'] = 'XMLHttpRequest'

    def process_response(self, request, response, spider):
        if response.status == 403 or b'captcha' in response.body:
            self.logger.warning(f"抖音反爬检测触发: {request.url}")
            return request.copy()
        return response

    def process_exception(self, request, exception, spider):
        self.logger.error(f"请求异常: {request.url}, Error: {exception}")
        return None
