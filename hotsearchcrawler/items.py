import scrapy
from w3lib.html import remove_tags


def clean_text(text, max_length=None):
    if text is None:
        return ''

    cleaned = remove_tags(text).strip()

    if max_length and len(cleaned) > max_length:
        cleaned = cleaned[:max_length]
    return cleaned


class HotItem(scrapy.Item):
    platform_id = scrapy.Field()
    rank = scrapy.Field()
    title = scrapy.Field()
    author = scrapy.Field()
    url = scrapy.Field()
    crawl_time = scrapy.Field()

    def process_item(self):
        self['title'] = clean_text(self['title'], max_length=500)
        self['author'] = clean_text(self['author'], max_length=100)
        return self
