from itemadapter import ItemAdapter
from datetime import datetime
import pymongo

class TranslationPipeline:
    """
    将商品信息添加到翻译队列中
    实际翻译由独立的翻译服务处理
    """
    def __init__(self, mongo_uri, mongo_db, source_collection, translated_collection, fields_to_translate=None):
        self.fields_to_translate = fields_to_translate or ['goodsName', 'description']
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db
        self.source_collection_name = source_collection
        self.translated_collection_name = translated_collection
        self.client = None
        self.db = None
        self.translated_collection = None
        self.pending_collection = None

    @classmethod
    def from_crawler(cls, crawler):
        # 从 spider 获取集合名称
        spider_name = crawler.spider.name
        source_collection = getattr(crawler.spider, 'collection_name', f'{spider_name}')
        translated_collection = f'{source_collection}_translated'
        
        # 从 spider 获取需要翻译的字段
        fields_to_translate = getattr(crawler.spider, 'fields_to_translate', None)
        
        return cls(
            mongo_uri=crawler.settings.get('MONGO_URI', '127.0.0.1'),
            mongo_db=crawler.settings.get('MONGO_DATABASE', 'scrapy_items'),
            source_collection=source_collection,
            translated_collection=translated_collection,
            fields_to_translate=fields_to_translate
        )

    def open_spider(self, spider):
        # 连接 MongoDB
        self.client = pymongo.MongoClient(self.mongo_uri)
        self.db = self.client[self.mongo_db]
        self.translated_collection = self.db[self.translated_collection_name]
        self.pending_collection = self.db[f'{self.source_collection_name}_translation_pending']
        
        # 创建索引
        self.pending_collection.create_index('item_id', unique=True)
        self.translated_collection.create_index('item_id', unique=True)
        
        spider.logger.info(f"Translation pipeline: {self.source_collection_name} -> {self.translated_collection_name}")
        spider.logger.info(f"Fields to translate: {self.fields_to_translate}")

    def close_spider(self, spider):
        # 显示待翻译队列状态
        pending_count = self.pending_collection.count_documents({})
        if pending_count > 0:
            spider.logger.info(f"Spider closed with {pending_count} items in translation queue")
        
        if self.client:
            self.client.close()

    def process_item(self, item, spider):
        
        # 获取文档的 _id（由 MongoDB pipeline 生成）
        item_id = item.get('_id')

        if not item_id:
            return item
            
        # 检查是否已经翻译过
        translated_doc = self.translated_collection.find_one({'item_id': item_id})
        if translated_doc:
            # 将翻译结果添加到 item 中
            for field in self.fields_to_translate:
                translated_field = f'{field}CN'
                if translated_field in translated_doc:
                    item[translated_field] = translated_doc[translated_field]
            return item
            
        # 将未翻译的 item 添加到 pending 表
        try:
            self.pending_collection.update_one(
                {'item_id': item_id},
                {'$setOnInsert': {'createdAt': datetime.now()}, 
                 '$set': {
                     'updatedAt': datetime.now(),
                     **{field: item.get(field) for field in self.fields_to_translate},
                     'item_id': item_id,
                 }},
                upsert=True
            )
        except pymongo.errors.DuplicateKeyError:
            pass
            
        return item 