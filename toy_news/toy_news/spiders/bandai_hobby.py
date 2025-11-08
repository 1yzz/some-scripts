# https://bandai-hobby.net/news/?cat=new_product
import scrapy
from datetime import datetime
import re
from urllib.parse import quote

class BandaiHobbySpider(scrapy.Spider):
    name = "bandai_hobby"
    allowed_domains = ["bandai-hobby.net"]
    start_urls = ["https://bandai-hobby.net/news/?cat=new_product"]
    ip = "BANDAI_HOBBY"
    collection_name = "bandai_hobby"

    # comment below for testing
    custom_settings = {
        'ITEM_PIPELINES': {
            "toy_news.pipelines.files.UploadToCOSPipeline": 600,
            "toy_news.pipelines.mongo.MongoDBPipeline": 700,
            "toy_news.pipelines.normalization.DataNormalizationPipeline": 900,
            "toy_news.pipelines.translation.TranslationPipeline": 950,
            "toy_news.pipelines.notify.NotifyPipeline": 1000,
        },
    }

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url=url, callback=self.parse)

    def parse(self, response):
        # Each news item is in .newsList__item
        for item in response.css('.p-newslist__lists li a::attr(href)'):
            detail_url = item.get()
            if detail_url and "news" in detail_url:
                detail_url = response.urljoin(detail_url)
                yield scrapy.Request(url=detail_url, callback=self.parse_news_detail)

        # Pagination: look for next page
        next_page = response.css('.p-pagination__nextList a::attr(href)').get()
        self.logger.info(f"Next page: {next_page}")
        if next_page:
            yield response.follow(next_page, callback=self.parse)

    def parse_news_detail(self, response):

        for item in response.css('.pg-article__inner a::attr(href)'):
            product_url = item.get()
            if product_url and "item" in product_url:
                product_url = response.urljoin(product_url)
                yield scrapy.Request(url=product_url, callback=self.parse_product_detail)


    def parse_product_detail(self, response):
        def extract_with_css(query):
            return response.css(query).get(default="").strip()
        title = extract_with_css('h1.p-heading__h1-product::text')

        # replace multi white spaces with only one space using regex
        price = re.sub(r'\s+', ' ', extract_with_css('dl.pg-products__detail dd:nth-of-type(1)::text'))
        date_str = extract_with_css('dl.pg-products__detail dd:nth-of-type(2)::text')

        # Try to parse date, fallback to raw string
        try:
            release_date = datetime.strptime(date_str, "%Y.%m.%d").strftime("%Y-%m-%d")
        except Exception:
            release_date = date_str
        # Description: join all text in .newsDetail__body
        desc = "\n".join([t.strip() for t in response.css('.pg-products__instructionTxt *::text').getall() if t.strip()])

        # Images: get all images in the body
        gallery = [response.urljoin(src) for src in response.css('.pg-products__sliderThumbnailInner img::attr(src)').getall()]

        data = {
            'url': response.url,
            'title': title,
            'releaseDate': release_date,
            'desc': desc,
            # remove query string from gallery url
            'gallery': [i.split('?')[0] for i in gallery],
            'ip': self.ip,
            'price': price,
        }

        data["file_urls"] = [i for i in gallery]

        yield data
