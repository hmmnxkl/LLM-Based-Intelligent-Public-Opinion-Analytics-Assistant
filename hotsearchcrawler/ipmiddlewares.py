from scrapy.http import HtmlResponse
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.by import By
import time
import random
import logging

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 Edg/116.0.1938.76",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36 Edg/115.0.1901.203",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36 Edg/114.0.1823.67",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 Edg/116.0.1938.76",
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36 EdgA/116.0.1938.76",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/116.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; SM-S901B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36"
]


class SeleniumMiddleware:
    def __init__(self, driver_name, executable_path, driver_arguments):
        self.options = Options()
        for arg in driver_arguments:
            self.options.add_argument(arg)

        self.options.add_argument(f"window-size={random.randint(1200, 1920)},{random.randint(800, 1080)}")

        self.options.add_experimental_option("excludeSwitches", ["enable-automation"])
        self.options.add_experimental_option('useAutomationExtension', False)

        service = Service(executable_path=executable_path)
        self.driver = webdriver.Edge(service=service, options=self.options)

        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        self.proxy_config = None
        self.bad_ips = set()
        self.request_count = 0
        self.last_ip_check = 0
        self.current_ip = None

        logger.info("SeleniumMiddleware for Edge initialized")

    @classmethod
    def from_crawler(cls, crawler):
        settings = crawler.settings
        return cls(
            driver_name=settings.get('SELENIUM_DRIVER_NAME'),
            executable_path=settings.get('SELENIUM_DRIVER_EXECUTABLE_PATH'),
            driver_arguments=settings.get('SELENIUM_DRIVER_ARGUMENTS')
        )

    def _get_proxy_config(self, spider):
        if not self.proxy_config:
            self.proxy_config = {
                'host': spider.settings.get('PROXY_HOST'),
                'port': spider.settings.get('PROXY_PORT'),
                'user': spider.settings.get('PROXY_USER'),
                'pass': spider.settings.get('PROXY_PASS'),
                'protocol': spider.settings.get('PROXY_PROTOCOL', 'socks5')
            }
        return self.proxy_config

    def _get_proxy_url(self, spider):
        config = self._get_proxy_config(spider)
        if config['host'] and config['port']:
            import urllib.parse
            user = urllib.parse.quote(config['user'])
            password = urllib.parse.quote(config['pass'])

            auth = f"{user}:{password}@" if config['user'] and config['pass'] else ""
            return f"{config['protocol']}://{auth}{config['host']}:{config['port']}"
        return None

    def _set_dynamic_proxy(self, proxy_url):
        if not proxy_url:
            return

        self.driver.execute_cdp_cmd('Network.setProxy', {
            'proxyConfiguration': {
                'proxyType': 'manual',
                'socksProxy': proxy_url,
                'socksVersion': 5,
                'bypassList': ["localhost", "127.0.0.1"]
            }
        })
        self.driver.execute_cdp_cmd('Network.enable', {})

    def _get_current_ip(self):
        try:
            self.driver.get("https://api.ipify.org?format=json")
            time.sleep(1)
            page_source = self.driver.page_source
            import re
            ip_match = re.search(r'{"ip":"(\d+\.\d+\.\d+\.\d+)"}', page_source)

            if ip_match:
                return ip_match.group(1)
            return None
        except Exception as e:
            logger.error(f"获取IP失败: {str(e)}")
            return None

    def _is_blocked(self):
        try:
            blocked_keywords = ["access denied", "forbidden", "blocked", "captcha", "验证码", "禁止访问", "403"]
            page_source = self.driver.page_source.lower()

            blocked_elements = self.driver.find_elements(
                By.XPATH,
                '//*[contains(text(), "Access Denied") or contains(text(), "Forbidden")]'
            )

            return (
                    any(keyword in page_source for keyword in blocked_keywords)
                    or len(blocked_elements) > 0)
        except:
            return False

    def _rotate_proxy(self):
        try:
            self.driver.execute_cdp_cmd('Network.disable', {})
            self.driver.execute_cdp_cmd('Network.enable', {})

            self.driver.delete_all_cookies()
            return True
        except Exception as e:
            logger.error(f"代理轮换失败: {str(e)}")
            return False

    def _random_delay(self):
        delay = random.uniform(1.0, 3.5)
        time.sleep(delay)

    def _random_user_agent(self):
        user_agent = random.choice(USER_AGENTS)
        self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": user_agent})
        return user_agent

    def _edge_fingerprint_spoofing(self):
        try:
            self.driver.execute_script("""
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
                configurable: true
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
                configurable: true
            });
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => 4,
                configurable: true
            });
            """)

            self.driver.execute_script("""
            Object.defineProperty(screen, 'width', {
                get: () => %d,
                configurable: true
            });
            Object.defineProperty(screen, 'height', {
                get: () => %d,
                configurable: true
            });
            Object.defineProperty(screen, 'availWidth', {
                get: () => %d,
                configurable: true
            });
            Object.defineProperty(screen, 'availHeight', {
                get: () => %d,
                configurable: true
            });
            """ % (
                random.randint(1920, 2560),
                random.randint(1080, 1440),
                random.randint(1800, 2400),
                random.randint(1000, 1400)
            ))

            self.driver.execute_script("""
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) {
                    return 'Microsoft';
                }
                if (parameter === 37446) {
                    return 'Edge WebGL';
                }
                return getParameter.call(this, parameter);
            };
            """)

            return True
        except Exception as e:
            logger.warning(f"Edge指纹伪装失败: {str(e)}")
            return False

    def process_request(self, request, spider):
        if 'selenium' not in request.meta:
            return None

        try:
            logger.debug(f"处理请求: {request.url}")

            proxy_url = self._get_proxy_url(spider)
            self._set_dynamic_proxy(proxy_url)

            user_agent = self._random_user_agent()
            logger.debug(f"使用用户代理: {user_agent}")

            self._edge_fingerprint_spoofing()

            width = random.randint(1200, 1920)
            height = random.randint(800, 1080)
            self.driver.set_window_size(width, height)
            logger.debug(f"设置窗口大小: {width}x{height}")

            self._random_delay()

            self.driver.get(request.url)
            logger.debug(f"已加载页面: {request.url}")

            load_time = random.uniform(1.0, 4.0)
            time.sleep(load_time)

            current_time = time.time()
            if current_time - self.last_ip_check > 120:
                current_ip = self._get_current_ip()
                if current_ip:
                    logger.info(f"当前IP: {current_ip}")
                    self.current_ip = current_ip
                    if current_ip in self.bad_ips:
                        logger.warning(f"使用已知坏IP: {current_ip}, 轮换代理中...")
                        self._rotate_proxy()
                self.last_ip_check = current_time

            if self._is_blocked():
                logger.warning(f"检测到封锁: {request.url}")
                if self.current_ip:
                    self.bad_ips.add(self.current_ip)
                    logger.warning(f"添加到坏IP列表: {self.current_ip}")

                if self._rotate_proxy():
                    logger.info("代理轮换成功")
                    return self.process_request(request, spider)
                else:
                    logger.error("代理轮换失败")
                    return None

            if hasattr(spider, 'selenium_actions'):
                try:
                    spider.selenium_actions(self.driver)
                    time.sleep(random.uniform(0.5, 1.5))
                except Exception as e:
                    logger.error(f"执行selenium_actions失败: {str(e)}")

            body = self.driver.page_source.encode('utf-8')
            response = HtmlResponse(
                url=self.driver.current_url,
                body=body,
                encoding='utf-8',
                request=request
            )

            logger.debug(f"成功创建响应: {request.url}")
            return response

        except Exception as e:
            logger.error(f"处理请求错误: {str(e)}")
            if self._rotate_proxy():
                logger.info("代理轮换后重试")
                return self.process_request(request, spider)
            return None

    def spider_closed(self):
        try:
            self.driver.quit()
            logger.info("Edge浏览器已关闭")
        except Exception as e:
            logger.error(f"关闭浏览器错误: {str(e)}")
