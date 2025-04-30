import scrapy
from datetime import datetime

class BspPrizeSpider(scrapy.Spider):
    name = "bsp_prize"
    domain = "https://bsp-prize.jp"
    ip = "BSP"
    start_urls = []

    custom_settings = {
        'ITEM_PIPELINES': {
            "jump_cal.pipelines.files.JumpCalFilesPipeline": 600,
            "jump_cal.pipelines.bsp_prize.BspMongoPipeline": 700,
        },
    }        

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url=url, callback=self.parse)

    def parse(self, response):
        links = response.css('.products_list .products_item a')
        for link in links:
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
        f"https://bsp-prize.jp/search/?ref=title&title=IP00002025&page={index}"  for index in range(2, 21)
    ]   
