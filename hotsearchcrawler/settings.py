# 简单的日志文件配置
import os
from datetime import datetime

# 创建日志目录
LOG_DIR = 'logs'
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# 日志文件配置
LOG_FILE = os.path.join(LOG_DIR, f'scrapy_{datetime.now().strftime("%Y%m%d_%H%M")}.log')
LOG_LEVEL = 'INFO'
LOG_FORMAT = '%(asctime)s [%(name)s] %(levelname)s: %(message)s'

# 禁用控制台输出，只输出到文件
LOG_ENABLED = True
LOG_STDOUT = False


CONCURRENT_REQUESTS = 16
CONCURRENT_REQUESTS_PER_DOMAIN = 2
DOWNLOAD_DELAY = 1
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1
AUTOTHROTTLE_MAX_DELAY = 10

BOT_NAME = 'hotsearchcrawler'
SPIDER_MODULES = ['hotsearchcrawler.spiders']
NEWSPIDER_MODULE = 'hotsearchcrawler.spiders'

# Selenium 设置
SELENIUM_DRIVER_NAME = 'edge'
SELENIUM_DRIVER_EXECUTABLE_PATH = 'msedgedriver'
SELENIUM_DRIVER_ARGUMENTS = ['--headless', '--disable-gpu']

# MySQL 配置
MYSQL_CONFIG = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': '123456',
    'database': 'hotsearch_db',
    'port': 3306
}

CUSTOM_MIDDLEWARES = {

    'baidu_spider': {
        'selenium_enabled': True
    },
    'uc_spider': {
        'selenium_enabled': True
    },
    'toutiao_spider': {
        'selenium_enabled': True
    }
}
# 让 Selenium 自动在 PATH 中查找
SELENIUM_DRIVER_EXECUTABLE_PATH = None



ZHIHU_COOKIES={
    '_zap': 'b14066b9-0bf3-4b72-896a-b85f985d8410',
    'd_c0': 'frFThen9MRqPTp4OkIAEG4Hd_KnDN7xOwlA=|1742811494',
    'q_c1': '67e5ef34b3524398a2d3a93c9919faf4|1753665845000|1753665845000',
    '_xsrf': 'klQQ7FbPAorEdTbN5cB2kXLTpQsCtkJX',
    '__zse_ck': '004_7npKa1=9fSZJCW0bwCNtorQrdDZoUfdfIH9aYRAnC45A9P3flSOvZXUl979FUpk6tjFtP6cN76tz2rR65pFvFGMK6FIpx5EajFCeDDmIH7TdZQY6/eB9pGgL/Z=hNFBR-gnLhmMaUWtQCW42X45oeaRJ+jc8zp4vbHDO3BUmtmZ6ngY2XQaPJfAX9c1kNhnVu4Hh4x+3gP81TcO9EXMOFDBRq7ORFaHhdGZSuO9vOAlYW2n9dMckMRHs0SZ+3bLb7',
    'Hm_lvt_98beee57fd2ef70ccdd5ca52b9740c49': '1761647151,1761898949,1763552059,1763961383',
    'HMACCOUNT': '0E65CF6406C78B16',
    'SESSIONID': '7XA2qEJDhwdjr76LHhSp2JEnL3D93DB58M3I9eDMOgg',
    'JOID': 'Wl4RB0nzINSAWsmiDf9kz0KG-6cXynqVtCGC6kmRWbLqLvSaQ9fI8eVexaALYNrtuaHPd2eDahckJD-o0u6OV7o=',
    'osd': 'WlwdBkrzItiBWcmgAf5nz0CK-qQXyHaUtyGA5kiSWbDmL_eaQdvJ8uVcyaEIYNjhuKLPdWuCaRcmKD6r0uyCVrk=',
    'z_c0': '2|1:0|10:1763961405|4:z_c0|92:Mi4xREhKakx3QUFBQUItc1ZPRjZmMHhHaVlBQUFCZ0FsVk5QVGdSYWdBLU55UFltTE1HUkZaUkd0OEltN3hVRm93NkVn|83709c2a4f3ad7ad12029d1a6028074a5944b0ce7ebb3dfe5833e2f067c9be49',
    'BEC': '4da336ae0b6517487a94031e0c3cbd90',
    'Hm_lpvt_98beee57fd2ef70ccdd5ca52b9740c49': '1763961704'
}

# 启用中间件和管道
DOWNLOADER_MIDDLEWARES = {
   'hotsearchcrawler.middlewares.RandomUserAgentMiddleware': 400,
    'hotsearchcrawler.middlewares.ProxyMiddleware': 500,
    'hotsearchcrawler.middlewares.RetryMiddleware': 550,
}
ITEM_PIPELINES = {
    'hotsearchcrawler.pipelines.MySQLPipeline': 300,
}

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0'
]

# 其他设置
ROBOTSTXT_OBEY = False
CONCURRENT_REQUESTS = 4
DOWNLOAD_DELAY = 2