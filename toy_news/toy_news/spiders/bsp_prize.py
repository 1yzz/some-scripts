import scrapy
from datetime import datetime

class BspPrizeSpider(scrapy.Spider):
    domain = "https://bsp-prize.jp"
    ip = "BSP"
    collection_name = "bsp_prize"
    start_urls = []
    spider_type = 'product'

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
        links = response.css('.products_list .products_item a')
        # reverse the links
        for link in reversed(links):
            yield response.follow(link, callback=self.parse_detail)
        
    def parse_detail(self, response):
        def extract_with_css(query):
            return response.css(query).get(default="").strip()

        description = ""
        for part in response.css('.productDetail_body  p *::text').getall():  # Iterate through all text and <br>
            description += part +'\n'

        # Extract the data you want from the response
        data = {
            'url': response.url,
            'title': extract_with_css("h1.headLine1::text"),
            'releaseDate': extract_with_css(".contents .releaseDate::text"),     
            'gallery': [self.domain + i for i in response.css(".productDetail_imgs a::attr(href)").getall() if "javascript" not in i ],
            'thumbs': [self.domain + i for i in response.css(".productDetail_imgs img::attr(src)").getall()],
            'desc': description,            
            'characters': [i.css("::text").get() for i in response.css('.pankuzu_item a') if ("charac" in i.css("::attr(href)").get())],
            'ip': self.ip,
        }

        data["file_urls"] = [i for i in data["gallery"]]


        yield data


class BspPrizeOPSpider(BspPrizeSpider):
    name = 'bsp_prize_op'
    ip = "ONEPIECE"
    start_urls = ['https://bsp-prize.jp/search/?ref=title&title=IP00002025']

class BspPrizeOPAllSpider(BspPrizeSpider):
    name = 'bsp_prize_op_all'
    ip = "ONEPIECE"
    start_urls = [
        f"https://bsp-prize.jp/search/?ref=title&title=IP00002025&page={index}"  for index in reversed(range(2, 23))
    ]

class BspPrizeNarutoSpider(BspPrizeSpider):
    name = 'bsp_prize_naruto'
    ip = "NARUTO"
    start_urls = [
        'https://bsp-prize.jp/search/?ref=title&title=IP00006142'
    ]


class BspPrizeHunterSpider(BspPrizeSpider):
    name = 'bsp_prize_hunter'
    ip = "HUNTER"
    start_urls = [
        'https://bsp-prize.jp/search/?ref=title&title=IP00006048'
    ]

class BspPrizeDragonBallSpider(BspPrizeSpider):
    name = 'bsp_prize_dragon_ball'
    ip = "DRAGONBALL"
    start_urls = [
        'https://bsp-prize.jp/search/?ref=title&title=IP00003375'
    ]

class BspPrizeKimetsuSpider(BspPrizeSpider):
    name = 'bsp_prize_kimetsu'
    ip = "鬼滅の刃"
    start_urls = [
        'https://bsp-prize.jp/search/?ref=title&title=IP00002034'
    ]


class BspPrizeJujutsuSpider(BspPrizeSpider):
    name = 'bsp_prize_jujutsu'
    ip = "呪術廻戦"
    start_urls = [
        'https://bsp-prize.jp/search/?ref=title&title=IP00002080'
    ]


class BspPrizeBleachSpider(BspPrizeSpider):
    name = 'bsp_prize_bleach'
    ip = "BLEACH"
    start_urls = [
        'https://bsp-prize.jp/search/?ref=title&title=IP00004767'
    ]

class BspPrizeChainSawSpider(BspPrizeSpider):
    name = 'bsp_prize_chain_saw'
    ip = "チェインソー"
    start_urls = [
         f'https://bsp-prize.jp/search/?ref=title&title=IP00004957'
    ]

class BspPrizeJoJoSpider(BspPrizeSpider):
    name = 'bsp_prize_jojo'
    ip = "ジョジョ"
    start_urls = [
        f'https://bsp-prize.jp/search/?ref=title&title=IP00003150'
    ]

class BspPrizeUmaSpider(BspPrizeSpider):
    name = 'bsp_prize_uma'
    ip = "ウマ娘"

    start_urls = [
        f'https://bsp-prize.jp/search/?ref=title&title=IP00002839'
    ]