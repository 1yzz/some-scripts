#!/usr/bin/env python3
"""
独立的翻译服务 - 数据分离版本
持续监控待翻译队列并处理翻译任务
支持翻译缓存以避免重复翻译
只将翻译结果保存到独立的翻译集合，保持源数据干净
"""

import os
import sys
import time
import signal
import argparse
import hashlib
from datetime import datetime
import pymongo
from pymongo import UpdateOne

# 添加项目路径到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from jump_cal.translators.deepseek_translator import DeepSeekTranslator


class TranslationService:
    def __init__(self, mongo_uri, mongo_db, collections_config, check_interval=10):
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db
        self.collections_config = collections_config  # {collection_name: ['field1', 'field2']}
        self.check_interval = check_interval
        self.translator = DeepSeekTranslator()
        self.batch_size = 10
        self.running = True
        self.cache_collection = None
        
    def connect_mongodb(self):
        self.client = pymongo.MongoClient(self.mongo_uri)
        self.db = self.client[self.mongo_db]
        self.cache_collection = self.db['translation_cache']
        
        # 创建缓存索引
        self.cache_collection.create_index('text_hash', unique=True)
        self.cache_collection.create_index([('original_text', 'text'), ('field_name', 1)])
        
    def close_mongodb(self):
        if hasattr(self, 'client'):
            self.client.close()
            
    def signal_handler(self, signum, frame):
        """处理停止信号"""
        print(f"\nReceived signal {signum}, shutting down gracefully...")
        self.running = False
        
    def get_text_hash(self, text):
        """生成文本的哈希值"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()
        
    def get_cached_translation(self, text, field_name):
        """从缓存中获取翻译"""
        text_hash = self.get_text_hash(text)
        cached = self.cache_collection.find_one({
            'text_hash': text_hash,
            'field_name': field_name
        })
        return cached['translated_text'] if cached else None
        
    def cache_translation(self, original_text, translated_text, field_name):
        """缓存翻译结果"""
        text_hash = self.get_text_hash(original_text)
        try:
            self.cache_collection.update_one(
                {'text_hash': text_hash},
                {   '$setOnInsert':{'created_at': datetime.now()},
                    '$set': {
                        'text_hash': text_hash,
                        'original_text': original_text,
                        'translated_text': translated_text,
                        'field_name': field_name,
                        'updated_at': datetime.now(),
                        'usage_count': 1
                    }
                },
                upsert=True
            )
        except pymongo.errors.DuplicateKeyError:
            # 如果已存在，增加使用次数
            self.cache_collection.update_one(
                {'text_hash': text_hash},
                {
                    '$inc': {'usage_count': 1},
                    '$set': {'updated_at': datetime.now()}
                }
            )
    
    def translate_with_cache(self, items_to_translate, fields_to_translate):
        """使用缓存进行翻译"""
        # 准备翻译数据
        translation_map = {}  # {field: {original_text: item_index}}
        cache_hits = 0
        cache_misses = 0
        
        # 检查缓存
        for i, doc in enumerate(items_to_translate):
            for field in fields_to_translate:
                if field in doc and doc[field]:
                    original_text = doc[field]
                    cached_translation = self.get_cached_translation(original_text, field)
                    
                    if cached_translation:
                        # 缓存命中
                        doc[f'{field}CN'] = cached_translation
                        cache_hits += 1
                    else:
                        # 缓存未命中，需要翻译
                        if field not in translation_map:
                            translation_map[field] = {}
                        if original_text not in translation_map[field]:
                            translation_map[field][original_text] = []
                        translation_map[field][original_text].append(i)
                        cache_misses += 1
        
        print(f"Cache hits: {cache_hits}, Cache misses: {cache_misses}")
        
        # 对缓存未命中的内容进行翻译
        for field, text_map in translation_map.items():
            if not text_map:
                continue
                
            # 准备批量翻译的文本
            texts_to_translate = list(text_map.keys())
            print(f"Translating {len(texts_to_translate)} unique {field} texts...")
            
            # 创建临时文档进行翻译
            temp_docs = [{field: text} for text in texts_to_translate]
            translated_docs = self.translator.batch_translate_documents(temp_docs, [field])
            
            # 处理翻译结果
            for j, translated_doc in enumerate(translated_docs):
                original_text = texts_to_translate[j]
                translated_field = f'{field}CN'
                
                if translated_field in translated_doc:
                    translated_text = translated_doc[translated_field]
                    
                    # 缓存翻译结果
                    self.cache_translation(original_text, translated_text, field)
                    
                    # 更新所有使用这个文本的文档
                    for item_index in text_map[original_text]:
                        items_to_translate[item_index][translated_field] = translated_text
        
        return items_to_translate
        
    def process_collection_pending(self, collection_name, collection_config):
        """处理单个集合的待翻译项目 - 只保存到翻译集合，不更新源集合"""
        try:
            fields_to_translate = collection_config
            
            source_collection = self.db[collection_name]
            translated_collection = self.db[f'{collection_name}_translated']
            pending_collection = self.db[f'{collection_name}_translation_pending']
            
            # 检查待翻译队列
            pending_count = pending_collection.count_documents({})
            if pending_count == 0:
                return 0
                
            print(f"[{collection_name}] Found {pending_count} pending items")
            
            # 获取一批待翻译的 items
            pending_items = list(pending_collection.find().sort('created_at', 1).limit(self.batch_size))
            if not pending_items:
                return 0
                
            # 获取完整的 item 数据（使用 _id 查询）
            item_ids = [item['item_id'] for item in pending_items]
            items_to_translate = list(source_collection.find({'_id': {'$in': item_ids}}))
            
            if not items_to_translate:
                print(f"[{collection_name}] No source documents found, cleaning up pending items")
                # 清理无效的 pending 项目
                for item in pending_items:
                    pending_collection.delete_one({'item_id': item['item_id']})
                return 0
                
            print(f"[{collection_name}] Processing {len(items_to_translate)} items with cache...")
            
            # 使用缓存进行翻译
            translated_docs = self.translate_with_cache(items_to_translate, fields_to_translate)
            
            # 准备批量操作 - 只保存到翻译集合
            translated_operations = []
            pending_deletions = []
            
            for doc in translated_docs:
                translated_data = {
                    'item_id': doc['_id'],
                    'collection_name': collection_name,
                    'created_at': datetime.now(),
                    'updated_at': datetime.now()
                }
                
                # 添加翻译字段
                for field in fields_to_translate:
                    translated_field = f'{field}CN'
                    if translated_field in doc:
                        translated_data[translated_field] = doc[translated_field]
                
                # 保存原始字段用于对比和查询
                for field in fields_to_translate:
                    if field in doc:
                        translated_data[f'original_{field}'] = doc[field]
                
                # 检查是否有翻译内容
                has_translation = any(key.endswith('CN') for key in translated_data.keys())
                
                if has_translation:
                    # 只添加到翻译集合
                    translated_operations.append(
                        UpdateOne(
                            {'item_id': doc['_id']},
                            {'$set': translated_data},
                            upsert=True
                        )
                    )
                    
                    # 标记为需要从 pending 中删除
                    pending_deletions.append(doc['_id'])
            
            # 执行批量操作 - 只更新翻译集合
            if translated_operations:
                translated_collection.bulk_write(translated_operations)
                print(f"[{collection_name}] Saved {len(translated_operations)} translations to {collection_name}_translated")
                
            # 从 pending 表中删除已处理的项目
            if pending_deletions:
                pending_collection.delete_many({'item_id': {'$in': pending_deletions}})
                
            print(f"[{collection_name}] Successfully processed {len(pending_deletions)} items (source data unchanged)")
            return len(pending_deletions)
            
        except Exception as e:
            print(f"[{collection_name}] Error processing pending items: {str(e)}")
            return 0
    
    def show_cache_stats(self):
        """显示缓存统计信息"""
        try:
            total_cached = self.cache_collection.count_documents({})
            if total_cached > 0:
                # 按字段统计
                pipeline = [
                    {'$group': {
                        '_id': '$field_name',
                        'count': {'$sum': 1},
                        'total_usage': {'$sum': '$usage_count'}
                    }}
                ]
                field_stats = list(self.cache_collection.aggregate(pipeline))
                
                print(f"Translation Cache Stats:")
                print(f"  Total cached translations: {total_cached}")
                for stat in field_stats:
                    print(f"  {stat['_id']}: {stat['count']} cached, {stat['total_usage']} total uses")
        except Exception as e:
            print(f"Error getting cache stats: {str(e)}")
    
    def run(self):
        """运行翻译服务"""
        print("Starting Translation Service (Data Separation Mode)...")
        print("NOTE: Translations will only be saved to separate translation collections")
        print("Source data collections will remain unchanged and clean.")
        print(f"Check interval: {self.check_interval} seconds")
        print(f"Batch size: {self.batch_size}")
        print(f"Collections: {list(self.collections_config.keys())}")
        print()
        
        # 注册信号处理器
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        try:
            self.connect_mongodb()
            
            # 显示缓存统计
            self.show_cache_stats()
            print()
            
            while self.running:
                total_processed = 0
                
                # 处理每个集合的待翻译项目
                for collection_name, collection_config in self.collections_config.items():
                    if not self.running:
                        break
                        
                    processed = self.process_collection_pending(collection_name, collection_config)
                    total_processed += processed
                
                if total_processed > 0:
                    print(f"Total processed in this cycle: {total_processed} items")
                    # 显示更新后的缓存统计
                    self.show_cache_stats()
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] No pending translations found")
                
                # 等待下一次检查
                for _ in range(self.check_interval):
                    if not self.running:
                        break
                    time.sleep(1)
                    
        except Exception as e:
            print(f"Service error: {str(e)}")
        finally:
            print("Shutting down Translation Service...")
            self.close_mongodb()


def main():
    parser = argparse.ArgumentParser(description='Translation Service with Cache')
    parser.add_argument('--config', '-c', 
                       help='Collections config in format: collection1:field1,field2;collection2:field3')
    parser.add_argument('--interval', '-i', type=int, default=10,
                       help='Check interval in seconds (default: 10)')
    parser.add_argument('--mongo-uri', default='127.0.0.1',
                       help='MongoDB URI (default: 127.0.0.1)')
    parser.add_argument('--mongo-db', default='scrapy_items',
                       help='MongoDB database (default: scrapy_items)')
    parser.add_argument('--show-cache', action='store_true',
                       help='Show cache statistics and exit')
    
    args = parser.parse_args()
    
    # 解析集合配置
    collections_config = {}
    if args.config:
        # 格式: collection1:field1,field2;collection2:field3
        for collection_config in args.config.split(';'):
            if ':' in collection_config:
                parts = collection_config.split(':')
                collection_name = parts[0].strip()
                
                if len(parts) >= 2:
                    fields_str = parts[1]
                    fields = [f.strip() for f in fields_str.split(',')]
                    collections_config[collection_name] = fields
    else:
        # 默认配置
        collections_config = {
            'jump_cal': ['goodsName', 'description'],
            'bsp_prize': ['title', 'content']
        }
    
    # 创建服务实例
    service = TranslationService(
        mongo_uri=args.mongo_uri,
        mongo_db=args.mongo_db,
        collections_config=collections_config,
        check_interval=args.interval
    )
    
    if args.show_cache:
        # 只显示缓存统计
        service.connect_mongodb()
        service.show_cache_stats()
        service.close_mongodb()
        return
    
    print("Translation Service Configuration (Data Separation Mode):")
    for collection, fields in collections_config.items():
        print(f"  {collection}: fields={fields} -> {collection}_translated")
    print()
    
    # 运行服务
    service.run()


if __name__ == "__main__":
    main() 