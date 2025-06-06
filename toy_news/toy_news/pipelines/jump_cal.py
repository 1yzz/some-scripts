# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html
import re
from itemadapter import ItemAdapter
import pymongo
from datetime import datetime

class PurifyPipeline:
    """
    处理一些数据, 比如发售日期
    """
    def add_year_if_missing(self, text):
        # 如果字符串不以4位数字开头（简单检查）
        if not text[:4].isdigit():
            current_year = datetime.now().year
            return f"{current_year}年{text}"
        return text

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        adapter["releaseDate"] = self.add_year_if_missing(adapter["releaseDate"])
        return item

class JumpCalMongoPipeline:
    """
    存储到db
    """
    def __init__(self, mongo_uri, mongo_db, mongo_collection):
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db
        self.mongo_collection = mongo_collection

    @classmethod
    def from_crawler(cls, crawler):
        spider_name = crawler.spider.name
        mongo_collection = getattr(crawler.spider, 'collection_name', f'{spider_name}')
        return cls(
            mongo_uri=crawler.settings.get("MONGO_URI"),
            mongo_db=crawler.settings.get("MONGO_DATABASE", "scrapy_items"),
            mongo_collection=mongo_collection
        )

    def open_spider(self, spider):
        self.client = pymongo.MongoClient(self.mongo_uri)
        self.db = self.client[self.mongo_db]
        self.collection = self.db[self.mongo_collection]
        # 创建唯一索引（如果尚未存在）
        self.collection.create_index("goodsName", unique=True)

        # Define the validator schema
        validator = {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["createdAt", "updatedAt"],  # Enforce these fields
                "properties": {
                    "createdAt": {
                        "bsonType": "date",
                        "description": "must be a date and is required"
                    },
                    "updatedAt": {
                        "bsonType": "date",
                        "description": "must be a date and is required"
                    }
                }
            }
        }
        if self.mongo_collection not in self.db.list_collection_names():
            self.db.create_collection(self.mongo_collection, validator=validator)
        else:
            # Update existing collection's validator
            self.db.command({
                "collMod": self.mongo_collection,
                "validator": validator
            })

    def close_spider(self, spider):
        self.client.close()


    def process_item(self, item, spider):
        # Add timestamps to the item
        now = datetime.now()

        adapter = ItemAdapter(item)

        # 使用标题作为查询条件
        query = {"goodsName": adapter["goodsName"]}

        old_data = self.collection.find_one(query)

        # 设置更新操作（$set 更新所有字段）
        update = {
            "$setOnInsert": {"createdAt": now},
            "$set": {"updatedAt":now, **adapter.asdict()},
        }

        try:
            # 存在则更新，不存在则插入
            result = self.collection.update_one(
                query,
                update,
                upsert=True
            )
            new_data = self.collection.find_one(query)
            
            adapter['_id'] = new_data['_id']
            item['_id'] = new_data['_id']
        
            spider.logger.info(f"Upserted item with name: {adapter['goodsName']}")
        except pymongo.errors.DuplicateKeyError:
            spider.logger.warning(f"Duplicate name found: {adapter['goodsName']}")
        except Exception as e:
            spider.logger.error(f"Error processing item: {e}")

        return item