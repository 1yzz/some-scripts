from base64 import b64decode
from pathlib import Path
import urllib.parse
import scrapy
import urllib



class BspItemSpider(scrapy.Spider):
    name = 'bsp_item'
    # allowed_domains = ['bsp-prize.jp']
    start_urls = []
        
    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url=url, callback=self.parse)

    def parse(self, response):
        # 提取页面中的标题
        # title = response.xpath('//h1/text()').get()
        
        # 提取页面中的描述
        # description = response.xpath('//div[@class="description"]/text()').get()
        
        # 提取页面中的价格
        # price = response.xpath('//span[@class="price"]/text()').get()
        links = response.css(".products_item a")
        yield from response.follow_all(links, callback=self.parse_detail)

    
    def parse_detail(self, response):
        def extract_with_css(query):
            return response.css(query).get(default="").strip()
        

        # 输出提取的数据
        data = {
            'url': response.url,
            'title': extract_with_css("h1.headLine1::text"),
            'date': extract_with_css(".contents .releaseDate::text"),
            'gallery': [i for i in response.css(".productDetail_imgs a::attr(href)").getall() if "javascript" not in i ],
            'thumbs': response.css(".productDetail_imgs img::attr(src)").getall(),
        }

        data["file_urls"] = [urllib.parse.urljoin(response.url, i) for i in data["gallery"]]


        # screenshot: bytes = b64decode(response.raw_api_response["screenshot"])
        # filename = f"quotes-{data["title"]}.jpg"
        # Path(filename).write_bytes(screenshot)

        yield data


class BspItemSpider1(BspItemSpider):
    name = 'bsp_item_1'
    start_urls = [
          'https://bsp-prize.jp/brand/5/item-by-title/IP00002025/',
    ]

class BspItemSpider2(BspItemSpider):
    name = 'bsp_item_2'
    start_urls = [
          'https://bsp-prize.jp/brand/5/item-by-title/IP00002025/?page=2',
    ]


class BspItemSpider3(BspItemSpider):
    name = 'bsp_item_3'
    start_urls = [
          'https://bsp-prize.jp/brand/5/item-by-title/IP00002025/?page=3',
    ]


class BspItemSpider4(BspItemSpider):
    name = 'bsp_item_4'
    start_urls = [
          'https://bsp-prize.jp/brand/5/item-by-title/IP00002025/?page=4',
    ]

class BspItemSpider5(BspItemSpider):
    name = 'bsp_item_5'
    start_urls = [
          'https://bsp-prize.jp/brand/5/item-by-title/IP00002025/?page=5',
    ]

class BspItemSpider6(BspItemSpider):
    name = 'bsp_item_6'
    start_urls = [
          'https://bsp-prize.jp/brand/5/item-by-title/IP00002025/?page=6',
    ]

class QuotesSpider(scrapy.Spider):
    name = "quotes"

    def start_requests(self):
        urls = [
            "https://quotes.toscrape.com/page/1/",
            "https://quotes.toscrape.com/page/2/",
        ]
        for url in urls:
            yield scrapy.Request(url=url, callback=self.parse)

    def parse(self, response):
        page = response.url.split("/")[-2]
        pass
        # filename = f"quotes-{page}.html"
        # Path(filename).write_bytes(response.body)
        # self.log(f"Saved file {filename}")
