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
            "jump_cal.pipelines.jump_cal.PurifyPipeline": 600,
            "jump_cal.pipelines.jump_cal.JumpCalMongoPipeline": 700,
            "jump_cal.pipelines.translation.TranslationPipeline": 800,
            "jump_cal.pipelines.notify.NotifyPipeline": 900,
        },
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'ROBOTSTXT_OBEY': True,
    }

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url=url, callback=self.parse)

    def parse(self, response):
        # Collect all the linkes
        # links = response.css(".newsMenu .acord .cat-item")
        # logging.info(f"Found {len(links)} link(s) on page {response.url}")
        #
        # yield from response.follow_all(links, callback=self.parse_detail)
        self.log("Start Crawling...")

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
    fields_to_translate = ['goodsName', 'description']
    start_urls = [
        'https://www.shonenjump.com/j/jumpcalendar/sakuhin/onepiece/'
    ]

class JumpCalHunterSpider(JumpcalSpider):
    name = 'jump_cal_hunter'
    ip = "HUNTER"
    fields_to_translate = ['goodsName', 'description']
    start_urls = [
        'https://www.shonenjump.com/j/jumpcalendar/sakuhin/hunter/'
    ]

class JumpCalNarutoSpider(JumpcalSpider):
    name = 'jump_cal_naruto'
    ip = "NARUTO"
    fields_to_translate = ['goodsName', 'description']
    start_urls = [
        'https://www.shonenjump.com/j/jumpcalendar/sakuhin/naruto/'
    ]

class JumpCalBleachSpider(JumpcalSpider):
    name = 'jump_cal_bleach'
    ip = "BLEACH"
    fields_to_translate = ['goodsName', 'description']
    start_urls = [
        'https://www.shonenjump.com/j/jumpcalendar/sakuhin/bleach/'
    ]

class JumpCalDragonBallSpider(JumpcalSpider):
    name = 'jump_cal_dragonball'
    ip = "DRAGONBALL"
    fields_to_translate = ['goodsName', 'description']
    start_urls = [
        'https://www.shonenjump.com/j/jumpcalendar/sakuhin/dragonball/'
    ]

