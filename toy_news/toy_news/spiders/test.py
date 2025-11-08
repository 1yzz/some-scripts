import scrapy
from datetime import datetime

class TestSpider(scrapy.Spider):
    name = "test"
    start_urls = ["https://quotes.toscrape.com/"]
    collection_name = "test"
    custom_settings = { 
        'ITEM_PIPELINES': {
            "toy_news.pipelines.mongo.MongoDBPipeline": 700,
        },
    }

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url=url, callback=self.parse)

    def parse(self, response):
        for quote in response.css(".quote"):
            yield {
                'url': response.url + quote.css(".text::text").get(),
                'text': quote.css(".text::text").get() + datetime.now().isoformat(),
                'author': quote.css(".author::text").get(),
                'tags': quote.css(".tag::text").getall(),
            }