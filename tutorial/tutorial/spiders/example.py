import scrapy


class QuotesSpider(scrapy.Spider):
    name = "quotes"
    allowed_domains = ["quotes.toscrape.com"]
    start_urls = ["https://quotes.toscrape.com/"]

    custom_settings = {
        'ITEM_PIPELINES': {
            "tutorial.pipelines.TutorialPipeline": 300,
        },
    }

    def parse(self, response):
        for quote in response.css(".quote"):
            yield {
                'text': quote.css(".text::text").get(),
                'author': quote.css(".author::text").get(),
                'tags': quote.css(".tag::text").getall(),
            }

        #next_page = response.css("li.next a::attr(href)").get()
        #if next_page is not None:
        #    yield response.follow(next_page, callback=self.parse)
