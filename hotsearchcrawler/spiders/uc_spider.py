from datetime import time
import urllib.parse
from urllib.parse import unquote, urlparse, parse_qs

from .base_spider import BaseHotSpider


class UcHotSpider_R(
    BaseHotSpider):
    name = 'uc_hot'
    platform_id = 2  # 平台唯一ID
    custom_settings = {
        'DOWNLOADER_MIDDLEWARES': {
            'hotsearchcrawler.fakemiddlewares.SeleniumMiddleware': 500,
        }
    }


    start_url = 'https://tophub.today/n/5PdMD3Xvmg'

    # XPath 配置
    first_topic_xpath = '/html/body/div[1]/div[3]/div/div[2]/div[2]/div[2]/div/div[1]/table/tbody/tr[1]/td[2]/a/@href'
    article_title_xpath = '//div[@class=\'sc sc_news_uchq\']//div[@class=\'qk-title-text qk-font-bold\']'
    article_author_xpath = '//div[@class=\'sc sc_news_uchq\']//div[@class="qk-view qk-padding-top-l padding-bottom-spread-style"]//span[@class=\'qk-source-item qk-clamp-1\'][1]'
    article_url_xpath = '//div[@class=\'shenfu-news_uchq-hot-container\']//div[@class="qk-paragraph-content qk-clamp-3"]//@data-openpageurl'



