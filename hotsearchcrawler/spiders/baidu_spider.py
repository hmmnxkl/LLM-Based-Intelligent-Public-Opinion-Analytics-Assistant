from datetime import time
from .base5_spder import BaseHotSpider
from urllib.parse import urljoin


class BaiduHotSpider(BaseHotSpider):
    name = 'baidu_hot'
    platform_id = 1
    custom_settings = {
        'DOWNLOADER_MIDDLEWARES': {
            'hotsearchcrawler.fakemiddlewares.SeleniumMiddleware': 500,
        }
    }
    start_url = 'https://top.baidu.com/board?tab=realtime'
    topics_xpath = '//div[@style="margin-bottom:20px"]//a[@class="title_dIF3B "]/@href'
    topic_title_xpath = '//div[@class="c-single-text-ellipsis"]'
    article_author_xpath = '(//div[@class="cosc-source"]//span)[1]'
    article_url_xpath = '//*[@id="1"]/div/div/div/div/div/div[2]/h3/a/@href'

    def selenium_actions(self, driver):
        try:
            more_btn = driver.find_element_by_xpath('//div[contains(@class, "more")]')
            if more_btn:
                more_btn.click()
                time.sleep(1)
        except:
            pass
