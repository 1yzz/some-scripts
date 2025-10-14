import scrapy

class TamashiiWebSpider(scrapy.Spider):
    allowed_domains = ["tamashiiweb.com"]
    start_urls = []
    pageCount = 0
    maxPage = 2

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
        links = response.css(".product_search_list .item_img a")
        self.logger.info(f"Found {len(links)} links on page {response.url}")
        for link in reversed(links):
            yield response.follow(link, callback=self.parse_detail)

        next_page = response.css(".pagenavi li:last-child a::attr(href)").get()
        if next_page:
            self.pageCount += 1
            if self.pageCount >= self.maxPage:
                return
            yield response.follow(next_page, callback=self.parse)


    def parse_detail(self, response):
        def extract_with_css(query):
            return response.css(query).get(default="").strip()

        def extract_with_xpath(text):
            return response.xpath(f'//dt[text()="{text}"]/following-sibling::dd/text()').get(default="").strip()
        
        gallery = [response.urljoin(href) for href in response.css("#mainimage_2021 li a::attr(href)").getall()]
        data = {
            'url': response.url,
            "category": extract_with_css("#itemdtl_main .item_brand::text"),
            'title': extract_with_css("#itemdtl_main .item_name::text"),
            "ip": extract_with_css("#item_outline dl dd:nth-of-type(1)::text"),
            'price':  extract_with_css("#item_outline dl dd:nth-of-type(2)::text").replace('\t', ''),
            "salesForm":extract_with_xpath("販売方法"),
            'openDate':  extract_with_xpath("予約開始日"),
            'releaseDate':  extract_with_xpath("発売日"),
            'images': [i for i in gallery],
            'desc': "",
        }

        data["file_urls"] = [i for i in data["images"]]

        yield data


class TamashiiWebSHFSpider(TamashiiWebSpider):
    name = "tamashii_web_shf"
    start_urls = [
        "https://tamashiiweb.com/special/shf/?page=1&sa=JAPAN&chara=&sub_brand=&ck1=1&ck2=1&ck3=1&ck4=1&ck5=1&order=release#!",
    ]

class TamashiiWebFZeroSpider(TamashiiWebSpider):
    name = "tamashii_web_fzero"
    start_urls = [
        'https://tamashiiweb.com/item_brand/figuarts_zero/1/?number=20&sa=JAPAN&character=&sub_chara=&brand=&sub_brand=&order=release&ck1=1&ck2=1&ck3=1&ck4=1&ck5=1#category_search',
    ]

class TamashiiWebMetaBuildSpider(TamashiiWebSpider):
    name = "tamashii_web_meta_build"
    start_urls = [
        'https://tamashiiweb.com/item_brand/metal_build/'
    ]