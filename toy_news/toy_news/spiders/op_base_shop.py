import scrapy
from datetime import datetime

class OnePieceBaseShopSpider(scrapy.Spider):
    name = "op_base_shop"
    domain = "https://baseshop.onepiece-base.com"
    ip = "ONEPIECE"
    collection_name = "op_base_shop"
    category_id = "37tgnvfomq6p"
    start_urls = [
        'https://products.baseshop.onepiece-base.com/frontend-api/products/list?&sortOrder=desc&orderBy=releaseDate&filters=%5B%7B%22field%22%3A%22categoryID%22%2C%22value%22%3A%2237tgnvfomq6p%22%7D%5D'
    ]

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
        data = response.json()
        totalCount = data["totalCount"]
        for i in range(0, totalCount, 20):
            url = f'https://products.baseshop.onepiece-base.com/frontend-api/products/list?limit=20&offset={i}&sortOrder=desc&orderBy=releaseDate&filters=%5B%7B%22field%22%3A%22categoryID%22%2C%22value%22%3A%2237tgnvfomq6p%22%7D%5D'
            yield scrapy.Request(url=url, callback=self.parse_detail)
        
        
    def parse_detail(self, response):
        res = response.json()
        self.logger.info("================")
        self.logger.info(f"limit: {res['limit']}, offset: {res['offset']}, totalCount: {res['totalCount']}")
        self.logger.info("================")
        for item in res["items"]:
            data = {
                'url': f"{self.domain}/item/{item['productID']}",
                'title': item.get("productName", {}).get('ja', item["productID"]),
                'productID': item['productID'],
                'price': f"{item["price"]}", # convert to string
                'releaseDate': item["releaseDate"],
                'category': item.get("mainCategories", [{}])[0].get('categoryCode', ''),
                'images': [i['url'] for i in item["productImageMulti"]],
                'desc': item.get("description", {}).get('ja', ''),
                'publishStartDate': item["publishStartDate"],
                'linkUrl': item["linkUrl"],
                'linkLabel': item.get("linkLabel", {}).get('ja', ''),
                'productForm': item['productForm'],
                'salesForm': item['salesForm'],
                'ip': self.ip,
            }

            data["file_urls"] = [i for i in data["images"]]

            yield data