import scrapy
import re
from datetime import datetime

class DengekiHobbySpider(scrapy.Spider):
    """电撃ホビーウェブ爬虫 - 爬取模型和手办相关新闻"""
    allowed_domains = ["hobby.dengeki.com"]
    start_urls = []
    pageCount = 0
    maxPage = 2

    custom_settings = {
        'ITEM_PIPELINES': {
            "toy_news.pipelines.files.UploadToCOSPipeline": 600,
            "toy_news.pipelines.mongo.MongoDBPipeline": 700,
            "toy_news.pipelines.normalization.DataNormalizationPipeline": 900,
           # "toy_news.pipelines.translation.TranslationPipeline": 950,
            #"toy_news.pipelines.notify.NotifyPipeline": 1000,
        },
        # 设置blognew专用的集合名称
        'BLOGNEW_COLLECTION': 'blognew_normalized',
    }

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url=url, callback=self.parse)

    def parse(self, response):
        """解析列表页面"""
        links = response.css(".archive-post .post-item .thumb a")
        self.logger.info(f"Found {len(links)} links on page {response.url}")
        for link in links[:1]:
            yield response.follow(link, callback=self.parse_article)

        next_page = response.css(".wp-pagenavi a.nextpostslink::attr(href)").get()
        if next_page:
            self.pageCount += 1
            if self.pageCount >= self.maxPage:
                return
            yield response.follow(next_page, callback=self.parse)

    def parse_article(self, response):
        """解析文章详情页面"""
        def extract_with_css(query):
            return response.css(query).get(default="").strip()

        def extract_with_xpath(text):
            return response.xpath(f'//span[text()="{text}"]/following-sibling::text()').get(default="").strip()

        title = extract_with_css("#contents .titleBox h1::text")
        author = extract_with_css("#contents .titleBox .meta2 .author::text") or '電撃ホビー編集部'
        tags = response.css("#contents .titleBox .meta1 .keyword li a::text").getall()
        publish_date = extract_with_css("#contents .titleBox .date *::text")

        # publish_date to datetime e.g. purify publish_date: 公開日：2025年10月21日 08:37 to 2025-10-21 08:37
        if publish_date:
            publish_date = re.sub(r'公開日：', '', publish_date)

        content = response.css("#contents .entry_body *::text").getall() or []
        content = '\n'.join([p.strip() for p in content]) or ''

        summary = extract_with_css("#contents .entry_body p:first-child::text") or ''

        images = response.css("#contents .entry_body img::attr(src)").getall() or []    

        # 构建博客新闻数据结构
        data = {
            'url': response.url,
            'title': title,
            'content': content,
            'summary': summary,
            'author': author,
            'publish_date': publish_date,
            'tags': tags,
            'category': 'GUNPLA',
            'ip': getattr(self, 'ip', 'DENGEKI_HOBBY'),  # 使用爬虫的ip属性
            'images': images,
        }

        # 设置文件下载URLs
        data["file_urls"] = images
        yield data

class DengekiHobbyGunplaSpider(DengekiHobbySpider):
    """电撃ホビーウェブ - 高达模型爬虫"""
    name = "blog_dengeki_hobby_gunpla"
    ip = "DENGEKI_HOBBY_GUNPLA"
    start_urls = [
       'https://hobby.dengeki.com/tag/gunpla-2/'
    ]


# class DengekiHobbyFigureSpider(DengekiHobbySpider):
#     """电撃ホビーウェブ - 美少女手办爬虫"""
#     name = "dengeki_hobby_figure"
#     ip = "DENGEKI_HOBBY_FIGURE"
#     start_urls = [
#         "https://hobby.dengeki.com/figure/",
#     ]
