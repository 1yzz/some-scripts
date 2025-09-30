import scrapy
from datetime import datetime
from scrapy.utils.project import get_project_settings
import urllib.parse

class JumpcalSpider(scrapy.Spider):
    name = "jump_cal"
    allowed_domains = ["www.shonenjump.com"]
    start_urls = []
    ip = "JUMP"
    collection_name = "jump_cal"

    custom_settings = {
        'ITEM_PIPELINES': {
            "toy_news.pipelines.jump_cal.PurifyPipeline": 600,
            "toy_news.pipelines.jump_cal.JumpCalMongoPipeline": 700,
            "toy_news.pipelines.normalization.DataNormalizationPipeline": 900,
            "toy_news.pipelines.translation.TranslationPipeline": 950,
            # "toy_news.pipelines.notify.NotifyPipeline": 1000,
        },
    }

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url=url, callback=self.parse)

    def parse(self, response):
        self.log(f"[{self.name}] Start Crawling...")
        yield from self.parse_detail(response)

    def parse_detail(self, response):
        cal_list = response.css(".callist li:nth-child(n+2)")

        for group in cal_list:
            release_date = group.css("h5::text").get()
            for item in group.css("ul > li"):
                # Get image URLs
                image_urls = item.css("img::attr(src)").getall()
                file_urls = [urllib.parse.urljoin(response.url, url) for url in image_urls]

                data = {
                    'releaseDate': release_date,
                    'genre': item.css(".genre2::text").get().strip(),
                    'goodsName': item.css('.title2::text').get(default="").strip() or item.css('.title2 a::text').get().strip(),
                    'price': item.css(".price2::text").get().strip(),
                    'maker': item.css(".maker2::text").get().strip(),
                    'ip': self.ip,
                    'url': response.url,
                    'file_urls': file_urls,  # Add file URLs for download
                }
                self.log(f"data crawled: {data['goodsName']}")
                yield data


class JumpCalOPSpider(JumpcalSpider):
    name = 'jump_cal_op'
    ip = "ONEPIECE"
    start_urls = [
        'https://www.shonenjump.com/j/jumpcalendar/sakuhin/onepiece/'
    ]

class JumpCalHunterSpider(JumpcalSpider):
    name = 'jump_cal_hunter'
    ip = "HUNTER"
    start_urls = [
        'https://www.shonenjump.com/j/jumpcalendar/sakuhin/hunter/'
    ]

class JumpCalNarutoSpider(JumpcalSpider):
    name = 'jump_cal_naruto'
    ip = "NARUTO"
    start_urls = [
        'https://www.shonenjump.com/j/jumpcalendar/sakuhin/naruto/'
    ]

class JumpCalBleachSpider(JumpcalSpider):
    name = 'jump_cal_bleach'
    ip = "BLEACH"
    start_urls = [
        'https://www.shonenjump.com/j/jumpcalendar/sakuhin/bleach/'
    ]

class JumpCalDragonBallSpider(JumpcalSpider):
    name = 'jump_cal_dragonball'
    ip = "DRAGONBALL"
    start_urls = [
        'https://www.shonenjump.com/j/jumpcalendar/sakuhin/dragonball/'
    ]

