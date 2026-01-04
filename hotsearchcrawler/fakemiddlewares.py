from scrapy.http import HtmlResponse
from selenium import webdriver
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
import time
from selenium.webdriver.common.by import By
import logging

logger = logging.getLogger(__name__)


def create_driver_with_fallback(executable_path, driver_arguments, use_edge=True):
    driver = None
    browser_name = "Edge" if use_edge else "Chrome/Chromium"

    try:
        if use_edge:
            try:
                options = EdgeOptions()
                for arg in driver_arguments:
                    options.add_argument(arg)
                options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59')

                service = EdgeService(executable_path=executable_path)
                driver = webdriver.Edge(service=service, options=options)
                logger.info("✅ Edge浏览器驱动初始化成功")
                return driver
            except Exception as edge_error:
                logger.warning(f"❌ Edge浏览器驱动初始化失败: {edge_error}")
                logger.info("尝试使用Chrome/Chromium浏览器...")
                return create_driver_with_fallback(executable_path, driver_arguments, use_edge=False)
        else:
            try:
                options = ChromeOptions()
                for arg in driver_arguments:
                    options.add_argument(arg)
                options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')

                service = ChromeService(executable_path=executable_path)
                driver = webdriver.Chrome(service=service, options=options)
                logger.info("✅ Chrome/Chromium浏览器驱动初始化成功")
                return driver
            except Exception as chrome_error:
                logger.error(f"❌ Chrome/Chromium浏览器驱动初始化失败: {chrome_error}")
                raise Exception("所有浏览器驱动初始化都失败，请检查浏览器驱动配置")

    except Exception as e:
        logger.error(f"❌ 浏览器驱动创建失败: {e}")
        raise


class SeleniumMiddleware:
    def __init__(self, driver_name, executable_path, driver_arguments):
        from selenium import webdriver

        self.driver = create_driver_with_fallback(
            executable_path, driver_arguments, use_edge=True)

    @classmethod
    def from_crawler(cls, crawler):
        settings = crawler.settings
        return cls(
            driver_name=settings.get('SELENIUM_DRIVER_NAME'),
            executable_path=settings.get('SELENIUM_DRIVER_EXECUTABLE_PATH'),
            driver_arguments=settings.get('SELENIUM_DRIVER_ARGUMENTS')
        )

    def process_request(self, request, spider):
        if 'selenium' in request.meta:
            self.driver.get(request.url)
            time.sleep(3)

            if hasattr(spider, 'selenium_actions'):
                spider.selenium_actions(self.driver)

            body = self.driver.page_source.encode('utf-8')
            return HtmlResponse(
                self.driver.current_url,
                body=body,
                encoding='utf-8',
                request=request
            )
        return None

    def spider_closed(self):
        self.driver.quit()


class SeleniumMiddleware1:
    def __init__(self, driver_name, executable_path, driver_arguments):
        self.driver = create_driver_with_fallback(
            executable_path, driver_arguments, use_edge=True)

    @classmethod
    def from_crawler(cls, crawler):
        settings = crawler.settings
        return cls(
            driver_name=settings.get('SELENIUM_DRIVER_NAME'),
            executable_path=settings.get('SELENIUM_DRIVER_EXECUTABLE_PATH'),
            driver_arguments=settings.get('SELENIUM_DRIVER_ARGUMENTS')
        )

    def process_request(self, request, spider):
        if 'selenium' in request.meta:
            if 'click_xpath' in request.meta:
                try:
                    click_xpath = request.meta['click_xpath']
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(1)

                    next_button = self.driver.find_element(By.XPATH, click_xpath)
                    next_button.click()
                    spider.logger.info(f"已点击元素: {click_xpath}")

                    time.sleep(3)
                except Exception as e:
                    spider.logger.error(f"点击元素失败: {click_xpath}, 错误: {str(e)}")
                    self.driver.get(request.url)
                    time.sleep(3)
            else:
                self.driver.get(request.url)
                time.sleep(3)

            if hasattr(spider, 'selenium_actions') and callable(spider.selenium_actions):
                spider.selenium_actions(self.driver)

            body = self.driver.page_source.encode('utf-8')
            return HtmlResponse(
                self.driver.current_url,
                body=body,
                encoding='utf-8',
                request=request
            )
        return None

    def spider_closed(self):
        self.driver.quit()
