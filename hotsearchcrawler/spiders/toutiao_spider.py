from urllib.parse import urljoin
from datetime import time
from .base5_spder import BaseHotSpider


class ToutiaoHotSpider(BaseHotSpider):
    name = 'Toutiao_hot'
    platform_id = 3
    custom_settings = {
        'DOWNLOADER_MIDDLEWARES': {
            'hotsearchcrawler.fakemiddlewares.SeleniumMiddleware': 400,
        }
    }

    start_url = 'https://www.toutiao.com'

    topics_xpath = '//div[@class="ttp-hot-board"]//li//a/@href'
    topic_title_xpath = '//*[@id="root"]/div/div[5]/div[2]/div[3]/div/div/div[1]/ol/li/a/p'

    article_author_xpath = '//div[@class=\'block-container\'][1]//div[@class=\'feed-card-footer-cmp-author\']'
    article_url_xpath = '//div[@class=\'block-container\'][1]//div[@class=\'card-render-wrapper\']//a[@class=\'title\']//@href'

    def selenium_actions(self, driver):
        try:
            more_btn = driver.find_element_by_xpath('//div[contains(@class, "more")]')
            if more_btn:
                more_btn.click()
                time.sleep(1)
        except:
            pass