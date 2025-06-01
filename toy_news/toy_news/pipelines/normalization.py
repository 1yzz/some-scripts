"""
数据归一化Pipeline - 简化版
专注于数据归一化，不重复存储原始数据
"""

import pymongo
from datetime import datetime
from ..items import DataMapper
from itemadapter import ItemAdapter

class DataNormalizationPipeline:
    """数据归一化Pipeline - 只负责归一化，不存储原始数据"""
    
    def __init__(self, mongo_uri, mongo_db):
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db
        
    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            mongo_uri=crawler.settings.get("MONGO_URI", "mongodb://localhost:27017/"),
            mongo_db=crawler.settings.get("MONGO_DATABASE", "scrapy_items"),
        )
        
    def open_spider(self, spider):
        self.client = pymongo.MongoClient(self.mongo_uri)
        self.db = self.client[self.mongo_db]
        self.normalized_collection = self.db['products_normalized']
        
        # 创建基础索引
        self.normalized_collection.create_index('product_hash', unique=True)
        self.normalized_collection.create_index([('source', 1), ('ip', 1)])
        
    def close_spider(self, spider):
        self.client.close()
        
    def process_item(self, item, spider):
        """处理爬取的数据 - 只进行归一化"""
        adapter = ItemAdapter(item)
        
        # 添加基础元数据
        adapter['spider_name'] = spider.name
        adapter['source'] = self._get_source_from_spider(spider.name)
        
        # 数据归一化并保存
        return self._normalize_and_save(item, spider)
        
        
    def _get_source_from_spider(self, spider_name):
        """根据爬虫名称确定数据源"""
        if 'jump_cal' in spider_name:
            return 'jump_cal'
        elif 'bsp_prize' in spider_name:
            return 'bsp_prize'
        return 'unknown'
        
    def _normalize_and_save(self, item, spider):
        """归一化数据并保存"""
        adapter = ItemAdapter(item)
        source = adapter.get('source')

        try:
            # 数据归一化
            if source == 'jump_cal':
                normalized_item = DataMapper.map_jump_cal_to_product(adapter)
            elif source == 'bsp_prize':
                normalized_item = DataMapper.map_bsp_prize_to_product(adapter)
            else:
                return None
                
            if normalized_item:
                # 如果原始数据有_id，保存引用关系
                if '_id' in adapter:
                    normalized_item['raw_data_id'] = adapter['_id']
                
                # 保存归一化数据
                normalized_data = dict(**normalized_item)
                
                # 使用MongoDB操作符优雅地处理时间戳
                update_doc = {
                    '$set': normalized_data,
                    '$setOnInsert': {
                        'createdAt': datetime.now()
                    },
                    '$currentDate': {
                        'updatedAt': True
                    }
                }
                
                # 使用 upsert 避免重复
                self.normalized_collection.update_one(
                    {'raw_data_id': normalized_data['raw_data_id']},
                    update_doc,
                    upsert=True
                )

                spider.logger.info(f"Normalized product: {normalized_data['raw_data_id']} {normalized_data['name']}")
                return normalized_item
                
        except Exception as e:
            spider.logger.error(f"Error normalizing item: {e}")
            
        return None