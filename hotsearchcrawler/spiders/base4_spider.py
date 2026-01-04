import scrapy
import json
import logging
import time
import re
from ..items import HotItem


class BaseHotSpider(scrapy.Spider):
    platform_id = None
    hot_list_url = None
    author_xpath = None

    title_field = 'article_title'
    url_field = 'article_link'
    rank_field = 'rank'
    id_field = 'article_id'
    need_author = False

    def start_requests(self):
        yield scrapy.Request(
            url=self.hot_list_url,
            callback=self.parse_hot_list,
            headers={'Content-Type': 'application/json'}
        )

    def parse_hot_list(self, response):
        try:
            crawl_time = int(time.time())
            data = json.loads(response.text)
            hot_items = data['data']['data']

            if not hot_items:
                self.logger.warning("No hot items found in the response")
                return

            for index, item in enumerate(hot_items):
                title = item.get(self.title_field, '')
                original_url = item.get(self.url_field, '')
                article_id = item.get(self.id_field, None)
                rank = item.get(self.rank_field, index + 1)

                if not original_url:
                    self.logger.warning(f"URL is missing for item at position {index + 1}")
                    continue

                final_url = original_url

                if not original_url.startswith('https://'):
                    cmt_add_match = re.search(r'cmt_add=([^&]+)', original_url)
                    cmt_add = cmt_add_match.group(1) if cmt_add_match else None

                    if article_id and cmt_add:
                        final_url = f"https://mparticle.uc.cn/article_org.html?uc_param_str=frdnsnpfvecpntnwprdssskt&aid={article_id}&cmt_add={cmt_add}"
                        self.logger.info(f"Converted non-HTTPS URL to: {final_url}")
                    else:
                        self.logger.warning(f"Failed to extract required parameters. article_id: {article_id}, cmt_add: {cmt_add}. Using original URL with added protocol.")
                        if not re.match(r'^[a-zA-Z]+://', original_url):
                            final_url = 'https://' + original_url

                self.logger.info(f"Processing hot item #{index + 1}: {title}")

                hot_item = HotItem()
                hot_item['platform_id'] = self.platform_id
                hot_item['title'] = title
                hot_item['url'] = final_url
                hot_item['rank'] = rank
                hot_item['crawl_time'] = crawl_time

                if self.need_author:
                    yield scrapy.Request(
                        url=final_url,
                        callback=self.parse_article_content,
                        meta={'item': hot_item},
                        dont_filter=True
                    )
                else:
                    hot_item['author'] = "平台作者"
                    yield hot_item.process_item()

        except Exception as e:
            self.logger.error(f"Error parsing hot list: {str(e)}", exc_info=True)

    def parse_article_content(self, response):
        try:
            hot_item = response.meta['item']

            if not self.author_xpath:
                self.logger.error("Author XPath is not configured")
                hot_item['author'] = "未知作者"
                yield hot_item.process_item()
                return

            author_element = response.xpath(self.author_xpath)
            if not author_element:
                self.logger.warning(f"Author element not found using XPath: {self.author_xpath}")
                hot_item['author'] = '未知作者'
            else:
                author_text = author_element.get()
                hot_item['author'] = author_text.strip() if author_text else "未知作者"

            yield hot_item.process_item()

        except Exception as e:
            self.logger.error(f"Error parsing article content: {str(e)}", exc_info=True)
            if 'hot_item' in locals():
                hot_item['author'] = "解析失败"
                yield hot_item.process_item()
