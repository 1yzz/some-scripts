import scrapy

class RamenToySpider(scrapy.Spider):
    allowed_domains = ["ramentoy.com"]
    start_urls = []
    spider_type = 'product'

    custom_settings = {
        'ITEM_PIPELINES': {
            "toy_news.pipelines.files.UploadToCOSPipeline": 600,
            "toy_news.pipelines.mongo.MongoDBPipeline": 700,
            "toy_news.pipelines.normalization.DataNormalizationPipeline": 900,
            "toy_news.pipelines.translation.TranslationPipeline": 950,
            #"toy_news.pipelines.notify.NotifyPipeline": 1000,
        },
    }


    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url=url, callback=self.parse)

    def parse(self, response):
        links = response.css("#product-grid li .card--media > .card__content .card__information a")
        self.logger.info(f"Found {len(links)} links on page {response.url}")
        for link in links:
            yield response.follow(link, callback=self.parse_detail)

    def parse_detail(self, response):
        def extract_with_css(query):
            return response.css(query).get(default="").strip()


        gallery = [
            'https:' + src.split('?')[0] for src in response.css("slider-component ul.thumbnail-list img::attr(src)").getall()
        ]

        text_list = response.css(".product__description *::text").getall()
        cleaned_text = '\n'.join(
            line.strip() for line in text_list if line.strip()
        )

        data = {
            'url': response.url,
            'ip': self.ip,
            'title': extract_with_css(".product__title h1::text"),
            'price': extract_with_css(".price__container .price-item::text"),
            'desc': cleaned_text,
            'images': [i for i in gallery],
        }

        data["file_urls"] = [i for i in data["images"]]

        yield data



class RamenToyMAKINA(RamenToySpider):
    name = "ramen_toy_makina"
    ip = "RAMEN_TOY_MAKINA"
    start_urls = [
        "https://ramentoy.com/collections/makina?sort_by=created-descending"
    ]