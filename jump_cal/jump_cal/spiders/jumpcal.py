import scrapy
from datetime import datetime
from scrapy.utils.project import get_project_settings
import urllib.parse

class JumpcalSpider(scrapy.Spider):
    name = "jump_cal"
    allowed_domains = ["www.shonenjump.com"]
    start_urls = []
    ip = "JUMP"

    custom_settings = {
        'ITEM_PIPELINES': {
            "jump_cal.pipelines.jump_cal.PurifyPipeline": 600,
            "jump_cal.pipelines.jump_cal.JumpCalMongoPipeline": 800,
        },
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
    start_urls = [
        'https://www.shonenjump.com/j/jumpcalendar/sakuhin/onepiece/'
    ]