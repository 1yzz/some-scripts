# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy

class BspPrizeItem(scrapy.Item):
    file_urls = scrapy.Field()
    files = scrapy.Field()
