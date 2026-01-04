from hotsearchcrawler.spiders.base3_spider import BaseHotSpider
import time
import random
import scrapy


class UCHotSpider(BaseHotSpider):
    name = "uc_hotnew_hot"
    platform_id = 2
    NEED_AUTHOR = True
    NEED_FINAL_URL = True

    custom_settings = {
        'DOWNLOADER_MIDDLEWARES': {
            'hotsearchcrawler.ucmiddlewares.RotateUserAgentMiddleware': 500,
        },
        'DOWNLOAD_DELAY': 3,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
        'CONCURRENT_REQUESTS': 3,
        'AUTOTHROTTLE_ENABLED': True,
        'AUTOTHROTTLE_START_DELAY': 1,
        'AUTOTHROTTLE_MAX_DELAY': 10,
        'AUTOTHROTTLE_TARGET_CONCURRENCY': 1.0,
        'RETRY_TIMES': 3,
        'RETRY_HTTP_CODES': [500, 502, 503, 504, 408, 403, 429],
        'COOKIES_ENABLED': True,
        'COOKIES_DEBUG': False,
    }

    start_urls = [
        "https://iflow-api.uc.cn/hot_rank/list?auto=0&page=0&size=50&uc_param_str=odmelanwdsdijbfrdnsnvemiut&need_ad=1&slot_id=100000660&personalized_ad=1&de=AAS5GPX7YYvBw6xLfvKbvQS8dasjbJFuvvavqLudt%2BvWng%3D%3D&od=AAQgVyfKKwBJE68CqbpW5Cjem2HodecGmtihzIs4OHj5PrFq2%2FYErMl70HofrV0jAys%3D&la=zh-cn&jb=0&nw=WIFI&dn=61177343034-ea334173&sn=2210-61177343034-419d6b30&fr=android&mi=OXF-AN10&ds=bTkwBEkwqZ1Xr3dJctxJ6etWgpZ%2Bc4ABBSP0732Z9rxUWw%3D%3D&ve=15.1.2.1202&ut=AARbJ4cpeOCLmBv%2B00WYXkvunjVZJ%2BeReru7ipC96EFxAQ%3D%3D"
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_initialized = False
        self.last_request_time = 0

    def start_requests(self):
        init_url = "https://www.uc.cn"
        yield scrapy.Request(
            url=init_url,
            callback=self.init_session,
            meta={'dont_redirect': True},
            dont_filter=True
        )

    def init_session(self, response):
        self.logger.info("会话初始化完成，开始请求热榜数据")
        self.session_initialized = True

        for url in self.start_urls:
            yield scrapy.Request(
                url=url,
                callback=self.parse,
                dont_filter=True
            )

    def parse(self, response):
        current_time = time.time()
        if self.last_request_time > 0:
            elapsed = current_time - self.last_request_time
            if elapsed < 2:
                time.sleep(2 - elapsed)

        self.last_request_time = time.time()

        return super().parse(response)

    def parse_detail_page(self, response):
        current_time = time.time()
        if self.last_request_time > 0:
            elapsed = current_time - self.last_request_time
            if elapsed < 1.5:
                time.sleep(1.5 - elapsed)

        self.last_request_time = time.time()

        if self.is_verification_page(response):
            self.logger.warning(f"触发验证页面: {response.url}")
            time.sleep(5)
            return scrapy.Request(
                response.url,
                callback=self.parse_detail_page,
                meta=response.meta,
                dont_filter=True
            )

        return super().parse_detail_page(response)

    def is_verification_page(self, response):
        verification_indicators = [
            '验证码' in response.text,
            'captcha' in response.url.lower(),
            response.xpath('//input[@name="captcha"]'),
            response.status in [403, 429],
            'access denied' in response.text.lower(),
            'anti-spam' in response.text.lower()
        ]
        return any(verification_indicators)

    def extract_final_url(self, response):
        final_url_selector = response.xpath('(//div[@class="sc sc_news_uchq"]//a/@data-openpageurl)[2]')

        if final_url_selector:
            final_url = final_url_selector.get()
            if final_url and not final_url.startswith(('http://', 'https://')):
                final_url = response.urljoin(final_url)
            return final_url

        return None

    def extract_author(self, item, response):
        author_selector = response.xpath(
            '//div[@class="sc sc_news_uchq"]//div[@class="qk-view qk-padding-top-l padding-bottom-spread-style"]//span[@class="qk-source-item qk-clamp-1"][1]/text()'
        )
        item['author'] = author_selector.get() or "未知作者"

        return item