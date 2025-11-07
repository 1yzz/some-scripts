# https://1kuji.com/products
import scrapy
from datetime import datetime
import re
from urllib.parse import quote

class OneKujiSpider(scrapy.Spider):
    name = "1kuji"
    allowed_domains = ["1kuji.com"]
    start_urls = [
        "https://1kuji.com/products",
        #"https://1kuji.com/products?sale_month=11&sale_year=2025"
        ]
    ip = "ONE_KUJI"
    collection_name = "one_kuji"

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
        for item in response.css('div.categoryCol ul.itemList li a::attr(href)'):
            product_url = item.get()
            if product_url:
                product_url = response.urljoin(product_url)
                yield scrapy.Request(url=product_url, callback=self.parse_detail)

        # Pagination: look for next page
        next_page = response.css('.releaseCol p.monthArrow.next a::attr(href)').get()
        self.logger.info(f"Next page: {next_page}")
        if next_page:
            yield response.follow(next_page, callback=self.parse)

    def parse_detail(self, response):
        def extract_with_css(query):
            return response.css(query).get(default="").strip()
        title = extract_with_css('#aboutCol .aboutColInner h2::text')

        release_form = ','.join(response.css('#aboutCol .aboutColInner .status *::text').getall()).strip()

        ip = extract_with_css('.mainCol .relativeLink ul li a::text').split('ページはこちら')[0].strip()

        detail_list = response.css('#aboutCol .detail.glBox > ul li')

        desc = "\n".join([t.strip() for t in detail_list.css('::text').getall() if t.strip()])

        price = detail_list[1].css('::text').get().strip().split('：')[1]
        date_str = detail_list[0].css('::text').getall()[-1].strip()

        release_date = None
        if date_str:
            pattern = r"\d{4}年\d{1,2}月\d{1,2}日"
            match = re.search(pattern, date_str)
            if match:
                release_date = datetime.strptime(match.group(0), "%Y年%m月%d日").strftime("%Y-%m-%d")
            else:
                release_date = date_str

        # 各等賞一覧
        price_list = response.css('#listCol .listColInner > .itemColList')

        for price_item in price_list:
            name = price_item.css('.itemColDetailHead > h4::text').get().strip()
            data = '\n'.join([t.strip() for t in price_item.css('.itemColDetailHead > ul > li::text').getall() if t.strip()])
            descriptiion = ' '.join([t.strip() for t in price_item.css('.itemColDetailHead > .scrollArea *::text').getall() if t.strip()])

            desc += f"\n{name}:\n{data}\n{descriptiion}"

        # Images: get all images in the body
        gallery = set()

        banner = response.css('.mainCol > .mvCol img::attr(src)').get()
       
        if banner:
            gallery.add(response.urljoin(banner))
       
        for src in response.css('#galleryCol > .galleryColInner.glBox > ul:first-child li a::attr(href)').getall():
            gallery.add(response.urljoin(src))

        for src in price_list.css('.itemColGallery li:first-child img::attr(src)').getall():
            gallery.add(response.urljoin(src))

        data = {
            'url': response.url,
            'title': title,
            'releaseDate': release_date,
            'desc': desc,
            'gallery': [i for i in gallery],
            'ip': ip,
            'price': price,
            'releaseForm': release_form,
        }

        data["file_urls"] = [i for i in gallery]

        yield data
