# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter


class TutorialPipeline:
    def __init__(self, mongo_uri, mongo_db):
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db

    @classmethod
    def from_crawler(cls, crawler):
        settings = crawler.settings
        return cls(
            mongo_uri=settings.get("MONGO_URI"),
            mongo_db=settings.get("MONGO_DATABASE", "items"),
        )
    def process_item(self, item, spider):
        spider.logger.info(f"settings mongo_uri: {self.mongo_uri}")
        spider.logger.info(f"settings mongo_db: {self.mongo_db}")
        return item
