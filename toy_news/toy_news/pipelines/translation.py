from itemadapter import ItemAdapter
import pymongo
from datetime import datetime
import json
import redis
import uuid
class TranslationPipeline:
    """
    针对归一化数据进行翻译
    只处理包含product_hash的归一化数据
    只添加到翻译队列，不修改原始item
    """
    def __init__(self, mongo_uri, mongo_db, mongo_collection, blognew_collection, redis_host, redis_password, redis_port, redis_db, redis_translation_queue):
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db
        self.mongo_collection = mongo_collection
        self.blognew_collection = blognew_collection
        self.client = None
        self.db = None
        self.translation_queue = redis_translation_queue
        self.redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db, password=redis_password)
        # 归一化数据的标准翻译字段
        self.fields_to_translate = ['name', 'description']
        # 博客新闻数据的标准翻译字段
        self.blognew_fields_to_translate = ['title', 'content', 'summary']

    @classmethod
    def from_crawler(cls, crawler):
        # 获取 Redis 配置
        redis_host = crawler.settings.get('REDIS_HOST', 'localhost')
        redis_password = crawler.settings.get('REDIS_PWD', '')
        redis_port = crawler.settings.get('REDIS_PORT', 6379)
        redis_db = crawler.settings.get('REDIS_DB', 0)
        
        # 调试信息
        print(f"TranslationPipeline Redis config:")
        print(f"  Host: {redis_host}")
        print(f"  Port: {redis_port}")
        print(f"  DB: {redis_db}")
        print(f"  Password configured: {'Yes' if redis_password else 'No'}")
        
        return cls(
            mongo_uri=crawler.settings.get('MONGO_URI', 'mongodb://localhost:27017/'),
            mongo_db=crawler.settings.get('MONGO_DATABASE', 'scrapy_items'),
            mongo_collection=crawler.settings.get('MONGO_COLLECTION', 'toys_normalized'),
            blognew_collection=crawler.settings.get('BLOGNEW_COLLECTION', 'blognew_normalized'),
            redis_host=redis_host,
            redis_password=redis_password,
            redis_port=redis_port,
            redis_db=redis_db,
            redis_translation_queue=crawler.settings.get('TRANSLATION_QUEUE', 'toys:translation:pending'),
        )

    def open_spider(self, spider):
        # 连接 MongoDB
        self.client = pymongo.MongoClient(self.mongo_uri)
        self.db = self.client[self.mongo_db]
        
        # 归一化数据集合
        self.normalized_collection = self.db[self.mongo_collection]
        self.blognew_normalized_collection = self.db[self.blognew_collection]
        # self.pending_collection = self.db['toys_translation_pending']
        
        # 创建索引
        self.normalized_collection.create_index('product_hash', unique=True)
        self.blognew_normalized_collection.create_index('article_hash', unique=True)
        # self.pending_collection.create_index('product_hash', unique=True)
        
        # 测试 Redis 连接
        try:
            self.redis_client.ping()
            spider.logger.info(f"Redis connection successful")
        except Exception as e:
            spider.logger.error(f"Redis connection failed: {e}")
            spider.logger.error(f"Redis config - Host: {self.redis_client.connection_pool.connection_kwargs.get('host')}, "
                              f"Port: {self.redis_client.connection_pool.connection_kwargs.get('port')}, "
                              f"DB: {self.redis_client.connection_pool.connection_kwargs.get('db')}, "
                              f"Password configured: {'Yes' if self.redis_client.connection_pool.connection_kwargs.get('password') else 'No'}")
        
        spider.logger.info(f"Translation pipeline initialized for normalized data")
        spider.logger.info(f"Fields to translate: {self.fields_to_translate}")
        spider.logger.info(f"Translation queue: {self.translation_queue}")

    def close_spider(self, spider):
        # 显示待翻译队列状态
        pending_count = self.redis_client.llen(self.translation_queue)
        if pending_count > 0:
            spider.logger.info(f"Spider closed with {pending_count} items in translation queue")
        
        if self.client:
            self.client.close()

    def process_item(self, item, spider):
        if not item:
            return None
        
        adapter = ItemAdapter(item)
        
        # 判断数据类型并处理
        product_hash = adapter.get('product_hash')
        article_hash = adapter.get('article_hash')
        
        if product_hash:
            # 处理商品数据
            return self._process_product_translation(adapter, spider, product_hash)
        elif article_hash:
            # 处理博客新闻数据
            return self._process_blognew_translation(adapter, spider, article_hash)
        else:
            # 不是归一化数据，直接返回
            return item
    
    def _process_product_translation(self, adapter, spider, product_hash):
        """处理商品数据翻译"""
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
        return adapter
    
    def _process_blognew_translation(self, adapter, spider, article_hash):
        """处理博客新闻数据翻译"""
        spider.logger.debug(f"Processing translation queue for blognew: {article_hash}")
        
        # 检查归一化数据是否已经有翻译
        normalized_doc = self.blognew_normalized_collection.find_one({'article_hash': article_hash})
        if normalized_doc:
            # 检查每个字段的翻译状态
            translated_fields = []
            untranslated_fields = []
            
            for field in self.blognew_fields_to_translate:
                translated_field = f'{field}CN'
                if translated_field in normalized_doc and normalized_doc[translated_field]:
                    # 已翻译的字段
                    translated_fields.append(field)
                else:
                    # 未翻译的字段
                    if field in adapter and adapter[field]:
                        untranslated_fields.append(field)
            
            if translated_fields:
                spider.logger.debug(f"Found existing translations for {article_hash}: {translated_fields}")
            
            if not untranslated_fields:
                # 所有字段都已翻译，直接返回原始item（不修改）
                spider.logger.debug(f"All fields already translated for: {article_hash}")
                return adapter
            else:
                # 还有未翻译的字段，添加到翻译队列
                spider.logger.debug(f"Need translation for {article_hash}: {untranslated_fields}")
                self._add_to_translation_queue(adapter, spider, untranslated_fields)
        else:
            # 文档不存在，将所有需要翻译的字段添加到队列
            untranslated_fields = [field for field in self.blognew_fields_to_translate if field in adapter and adapter[field]]
            if untranslated_fields:
                self._add_to_translation_queue(adapter, spider, untranslated_fields)
        
        # 返回原始item，不添加翻译字段
        return item
        
    def _add_to_translation_queue(self, adapter, spider, fields_to_translate=None):
        """将归一化数据添加到翻译队列"""
        if fields_to_translate is None:
            # 根据数据类型选择默认字段
            if adapter.get('product_hash'):
                fields_to_translate = self.fields_to_translate
            elif adapter.get('article_hash'):
                fields_to_translate = self.blognew_fields_to_translate
            else:
                fields_to_translate = self.fields_to_translate
            
        try:
            # 准备元数据
            metadata = {}
            if adapter.get('product_hash'):
                metadata['product_hash'] = adapter.get('product_hash')
            elif adapter.get('article_hash'):
                metadata['article_hash'] = adapter.get('article_hash')
            
            # 准备需要翻译的字段
            translation_fields = {}
            for field in fields_to_translate:
                if field in adapter and adapter[field]:
                    translation_fields[field] = adapter[field]
            
            # 如果没有需要翻译的内容，直接返回
            if not translation_fields:
                return
            
            # 构建符合Go Message结构的消息格式
            queue_message = {
                "id": str(uuid.uuid4()),
                "type": "translation",
                "payload": {
                    "_id": adapter.get('_id'),
                    "created_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                    **metadata,
                    **translation_fields,
                },
                "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "attempts": 0,
                "max_retries": 5
            }
            
            # 插入到待redis中的翻译队列
            self.redis_client.lpush(self.translation_queue, json.dumps(queue_message))
            
            hash_key = adapter.get('product_hash') or adapter.get('article_hash')
            spider.logger.debug(f"Added to translation queue: {hash_key} (fields: {fields_to_translate})")
            
        except pymongo.errors.DuplicateKeyError:
            # 已存在，忽略
            pass
        except Exception as e:
            spider.logger.error(f"Error adding to translation queue: {e}")
