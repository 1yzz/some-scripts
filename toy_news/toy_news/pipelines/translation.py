from itemadapter import ItemAdapter
import pymongo
from datetime import datetime

class TranslationPipeline:
    """
    针对归一化数据进行翻译
    只处理包含product_hash的归一化数据
    只添加到翻译队列，不修改原始item
    """
    def __init__(self, mongo_uri, mongo_db, mongo_collection):
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db
        self.mongo_collection = mongo_collection
        self.client = None
        self.db = None
        
        # 归一化数据的标准翻译字段
        self.fields_to_translate = ['name', 'description']

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            mongo_uri=crawler.settings.get('MONGO_URI', 'mongodb://localhost:27017/'),
            mongo_db=crawler.settings.get('MONGO_DATABASE', 'scrapy_items'),
            mongo_collection=crawler.settings.get('MONGO_COLLECTION', 'toys_normalized'),
        )

    def open_spider(self, spider):
        # 连接 MongoDB
        self.client = pymongo.MongoClient(self.mongo_uri)
        self.db = self.client[self.mongo_db]
        
        # 归一化数据集合
        self.normalized_collection = self.db[self.mongo_collection]
        self.pending_collection = self.db['toys_translation_pending']
        
        # 创建索引
        self.normalized_collection.create_index('product_hash', unique=True)
        self.pending_collection.create_index('product_hash', unique=True)
        
        spider.logger.info(f"Translation pipeline initialized for normalized data")
        spider.logger.info(f"Fields to translate: {self.fields_to_translate}")
        spider.logger.info(f"Translation queue: toys_translation_pending")

    def close_spider(self, spider):
        # 显示待翻译队列状态
        pending_count = self.pending_collection.count_documents({})
        if pending_count > 0:
            spider.logger.info(f"Spider closed with {pending_count} items in translation queue")
        
        if self.client:
            self.client.close()

    def process_item(self, item, spider):
        if not item:
            return None
        
        adapter = ItemAdapter(item)
        
        # 只处理归一化数据（通过product_hash判断）
        product_hash = adapter.get('product_hash')
        if not product_hash:
            # 不是归一化数据，直接返回
            return item
            
        spider.logger.debug(f"Processing translation queue for product: {product_hash}")
        
        # 检查归一化数据是否已经有翻译
        normalized_doc = self.normalized_collection.find_one({'product_hash': product_hash})
        if normalized_doc:
            # 检查每个字段的翻译状态
            translated_fields = []
            untranslated_fields = []
            
            for field in self.fields_to_translate:
                translated_field = f'{field}CN'
                if translated_field in normalized_doc and normalized_doc[translated_field]:
                    # 已翻译的字段
                    translated_fields.append(field)
                else:
                    # 未翻译的字段
                    if field in adapter and adapter[field]:
                        untranslated_fields.append(field)
            
            if translated_fields:
                spider.logger.debug(f"Found existing translations for {product_hash}: {translated_fields}")
            
            if not untranslated_fields:
                # 所有字段都已翻译，直接返回原始item（不修改）
                spider.logger.debug(f"All fields already translated for: {product_hash}")
                return item
            else:
                # 还有未翻译的字段，添加到翻译队列
                spider.logger.debug(f"Need translation for {product_hash}: {untranslated_fields}")
                self._add_to_translation_queue(adapter, spider, untranslated_fields)
        else:
            # 文档不存在，将所有需要翻译的字段添加到队列
            untranslated_fields = [field for field in self.fields_to_translate if field in adapter and adapter[field]]
            if untranslated_fields:
                self._add_to_translation_queue(adapter, spider, untranslated_fields)
        
        # 返回原始item，不添加翻译字段
        return item
        
    def _add_to_translation_queue(self, adapter, spider, fields_to_translate=None):
        """将归一化数据添加到翻译队列"""
        if fields_to_translate is None:
            fields_to_translate = self.fields_to_translate
            
        try:
            # 准备元数据
            metadata = {
                'product_hash': adapter.get('product_hash'),
            }
            
            # 准备需要翻译的字段
            translation_fields = {}
            for field in fields_to_translate:
                if field in adapter and adapter[field]:
                    translation_fields[field] = adapter[field]
            
            # 如果没有需要翻译的内容，直接返回
            if not translation_fields:
                return
            
            # 插入到待翻译队列（如果不存在）
            self.pending_collection.update_one(
                {'product_hash': adapter.get('product_hash')},
                {
                    '$setOnInsert': {
                        'createdAt': datetime.now()
                    },
                    '$set': {
                        **metadata,
                        **translation_fields
                    },
                },
                upsert=True
            )
            
            spider.logger.debug(f"Added to translation queue: {adapter.get('product_hash')} (fields: {fields_to_translate})")
            
        except pymongo.errors.DuplicateKeyError:
            # 已存在，忽略
            pass
        except Exception as e:
            spider.logger.error(f"Error adding to translation queue: {e}")
