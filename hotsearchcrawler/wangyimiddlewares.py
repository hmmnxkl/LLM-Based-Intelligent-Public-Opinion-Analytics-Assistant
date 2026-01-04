from scrapy import signals
from fake_useragent import UserAgent


class RotateUserAgentMiddleware:
    def __init__(self):
        self.ua = UserAgent()

    def process_request(self, request, spider):
        request.headers.setdefault('User-Agent', self.ua.random)
        request.headers.setdefault('Referer', 'https://news.163.com/')
        request.headers.setdefault('Accept', 'application/json, text/javascript, */*; q=0.01')
        request.headers.setdefault('X-Requested-With', 'XMLHttpRequest')


class NetEaseCookieMiddleware:
    def process_request(self, request, spider):
        if 'netease' in spider.name:
            request.cookies.setdefault('ntes_ka', 'ad00ecb5f5a1a1e1')
            request.cookies.setdefault('ntes_utuid', '1234567890ABCDEF')


class ErrorHandleMiddleware:
    def process_response(self, request, response, spider):
        if response.status != 200:
            spider.logger.error(f"请求失败: {response.url} 状态码: {response.status}")
        return response
