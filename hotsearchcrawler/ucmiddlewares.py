# hotsearchcrawler/fakemiddlewares.py
from scrapy import signals
from scrapy.downloadermiddlewares.useragent import UserAgentMiddleware
import random

class RotateUserAgentMiddleware(UserAgentMiddleware):
    """随机轮换User-Agent中间件"""
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1',
        'Mozilla/5.0 (Linux; Android 10; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36'
    ]

    def process_request(self, request, spider):
        request.headers['User-Agent'] = random.choice(self.user_agents)
        request.headers['Referer'] = 'https://www.uc.cn/'
        request.headers['Accept'] = 'application/json, text/javascript, */*; q=0.01'
        request.headers['X-Requested-With'] = 'XMLHttpRequest'

class ProxyMiddleware:
    """代理中间件（如需使用代理请取消注释）"""
    # def process_request(self, request, spider):
    #     # 在此处设置代理服务器
    #     # request.meta['proxy'] = "http://your-proxy-address:port"
    #     pass

class RetryMiddleware:
    """自定义重试中间件"""
    def process_response(self, request, response, spider):
        if response.status in [403, 429]:
            spider.logger.warning(f"遇到限制状态码 {response.status}, 将重试")
            return self._retry(request, spider) or response
        return response

    def _retry(self, request, spider):
        retryreq = request.copy()
        retryreq.dont_filter = True
        return retryreq

