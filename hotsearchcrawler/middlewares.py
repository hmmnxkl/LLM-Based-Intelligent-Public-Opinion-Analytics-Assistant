import random
from scrapy import signals
from scrapy.downloadermiddlewares.useragent import UserAgentMiddleware


class RandomUserAgentMiddleware(UserAgentMiddleware):
    def __init__(self, user_agents):
        super().__init__()
        self.user_agents = user_agents

    @classmethod
    def from_crawler(cls, crawler):
        settings = crawler.settings
        user_agents = settings.get('USER_AGENTS', [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36'
        ])
        return cls(user_agents)

    def process_request(self, request, spider):
        request.headers.setdefault(b'User-Agent', random.choice(self.user_agents))


class ProxyMiddleware:
    def __init__(self, proxies):
        self.proxies = proxies

    @classmethod
    def from_crawler(cls, crawler):
        settings = crawler.settings
        proxies = settings.get('PROXIES', [])
        return cls(proxies)

    def process_request(self, request, spider):
        if self.proxies:
            proxy = random.choice(self.proxies)
            request.meta['proxy'] = proxy


class RetryMiddleware:
    def __init__(self, max_retry_times):
        self.max_retry_times = max_retry_times

    @classmethod
    def from_crawler(cls, crawler):
        settings = crawler.settings
        max_retry_times = settings.getint('RETRY_TIMES', 3)
        return cls(max_retry_times)

    def process_response(self, request, response, spider):
        if response.status in [500, 502, 503, 504] and request.meta.get('retry_times', 0) < self.max_retry_times:
            retryreq = request.copy()
            retryreq.meta['retry_times'] = retryreq.meta.get('retry_times', 0) + 1
            retryreq.dont_filter = True
            return retryreq
        return response
