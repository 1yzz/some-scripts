#!/usr/bin/env python3
"""
翻译服务 - 统一翻译架构版本

直接在 toys_normalized 集合中更新翻译结果
无需额外的翻译集合，简化数据流
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

from toy_news.translators.deepseek_translator import DeepSeekTranslator


class TranslationService:
    def __init__(self, mongo_uri, mongo_db, mongo_collection, check_interval=10):
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db
        self.mongo_collection = mongo_collection
        self.check_interval = check_interval
        self.translator = DeepSeekTranslator()
        self.batch_size = 10
        self.running = True
        
        # 统一的翻译字段
        self.fields_to_translate = ['name', 'description']
        
    def connect_mongodb(self):
        self.client = pymongo.MongoClient(self.mongo_uri)
        self.db = self.client[self.mongo_db]
        
        # 统一的集合
        self.normalized_collection = self.db[self.mongo_collection]
        self.pending_collection = self.db['toys_translation_pending']
        self.cache_collection = self.db['toys_translation_cache']
        
        # 创建缓存索引 (只需要哈希索引，不需要文本索引)
        self.cache_collection.create_index('text_hash', unique=True)
        
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
        
    def get_cached_translation(self, text):
        """从缓存中获取翻译"""
        text_hash = self.get_text_hash(text)
        cached = self.cache_collection.find_one({'text_hash': text_hash})
        return cached['translated_text'] if cached else None
        
    def cache_translation(self, original_text, translated_text):
        """缓存翻译结果"""
        text_hash = self.get_text_hash(original_text)
        try:
            self.cache_collection.update_one(
                {'text_hash': text_hash},
                {   
                    '$setOnInsert': {'created_at': datetime.now()},
                    '$set': {
                        'text_hash': text_hash,
                        'original_text': original_text,
                        'translated_text': translated_text,
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
    
    def translate_with_cache(self, items_to_translate):
        """使用缓存进行翻译"""
        # 准备翻译数据
        translation_map = {}  # {field: {original_text: product_hash_list}}
        cache_hits = 0
        cache_misses = 0
        
        # 检查缓存
        for doc in items_to_translate:
            product_hash = doc['product_hash']
            
            for field in self.fields_to_translate:
                if field in doc and doc[field]:
                    original_text = doc[field]
                    cached_translation = self.get_cached_translation(original_text)
                    
                    if cached_translation:
                        # 缓存命中，直接设置翻译
                        doc[f'{field}CN'] = cached_translation
                        cache_hits += 1
                    else:
                        # 缓存未命中，需要翻译
                        if field not in translation_map:
                            translation_map[field] = {}
                        if original_text not in translation_map[field]:
                            translation_map[field][original_text] = []
                        translation_map[field][original_text].append(product_hash)
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
                    self.cache_translation(original_text, translated_text)
                    
                    # 更新所有使用这个文本的文档
                    for product_hash in text_map[original_text]:
                        # 找到对应的文档并设置翻译
                        for doc in items_to_translate:
                            if doc['product_hash'] == product_hash:
                                doc[translated_field] = translated_text
                                break
        
        return items_to_translate
        
    def process_pending_translations(self):
        """处理待翻译队列"""
        try:
            # 检查待翻译队列
            pending_count = self.pending_collection.count_documents({})
            if pending_count == 0:
                return 0
                
            print(f"Found {pending_count} pending items")
            
            # 获取一批待翻译的 items
            pending_items = list(self.pending_collection.find().sort('createdAt', 1).limit(self.batch_size))
            if not pending_items:
                return 0
                
            print(f"Processing {len(pending_items)} items with cache...")
            
            # 使用缓存进行翻译
            translated_docs = self.translate_with_cache(pending_items)
            
            # 准备批量操作
            update_operations = []
            pending_deletions = []
            
            for doc in translated_docs:
                product_hash = doc['product_hash']
                
                # 准备翻译字段更新
                translation_updates = {}
                has_translation = False
                
                for field in self.fields_to_translate:
                    translated_field = f'{field}CN'
                    if translated_field in doc:
                        translation_updates[translated_field] = doc[translated_field]
                        has_translation = True
                
                if has_translation:
                    # 更新 toys_normalized 集合
                    update_operations.append(
                        UpdateOne(
                            {'product_hash': product_hash},
                            {
                                '$set': translation_updates,
                                '$currentDate': {'updatedAt': True}
                            }
                        )
                    )
                    
                    # 标记为需要从 pending 中删除
                    pending_deletions.append(product_hash)
            
            # 执行批量操作
            if update_operations:
                result = self.normalized_collection.bulk_write(update_operations)
                print(f"Updated {result.modified_count} products in toys_normalized")
                
            # 从 pending 表中删除已处理的项目
            if pending_deletions:
                delete_result = self.pending_collection.delete_many({'product_hash': {'$in': pending_deletions}})
                print(f"Removed {delete_result.deleted_count} items from translation_pending")
                
            return len(pending_deletions)
            
        except Exception as e:
            print(f"Error processing pending translations: {str(e)}")
            return 0
    
    def show_stats(self):
        """显示统计信息"""
        try:
            # 待翻译队列统计
            pending_count = self.pending_collection.count_documents({})
            print(f"Translation pending: {pending_count} items")
            
            # 已翻译产品统计
            translated_count = self.normalized_collection.count_documents({
                '$or': [
                    {'nameCN': {'$exists': True}},
                    {'descriptionCN': {'$exists': True}}
                ]
            })
            total_products = self.normalized_collection.count_documents({})
            print(f"Translated products: {translated_count}/{total_products}")
            
            # 缓存统计
            total_cached = self.cache_collection.count_documents({})
            if total_cached > 0:
                total_usage = self.cache_collection.aggregate([
                    {'$group': {'_id': None, 'total_usage': {'$sum': '$usage_count'}}}
                ])
                total_usage = list(total_usage)
                usage_count = total_usage[0]['total_usage'] if total_usage else total_cached
                
                print(f"Translation cache: {total_cached} entries, {usage_count} total uses")
                    
        except Exception as e:
            print(f"Error getting stats: {str(e)}")
    
    def run(self):
        """运行翻译服务"""
        print("Starting Unified Translation Service...")
        print("Processing translations for toys_normalized collection")
        print(f"Check interval: {self.check_interval} seconds")
        print(f"Batch size: {self.batch_size}")
        print(f"Fields to translate: {self.fields_to_translate}")
        print()
        
        # 注册信号处理器
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        try:
            self.connect_mongodb()
            
            # 显示初始统计
            self.show_stats()
            print()
            
            while self.running:
                processed = self.process_pending_translations()
                
                if processed > 0:
                    print(f"Processed {processed} items in this cycle")
                    # 显示更新后的统计
                    self.show_stats()
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
    parser = argparse.ArgumentParser(description='Unified Translation Service')
    parser.add_argument('--interval', '-i', type=int, default=10,
                       help='Check interval in seconds (default: 10)')
    parser.add_argument('--mongo-uri', default='mongodb://localhost:27017/',
                       help='MongoDB URI (default: mongodb://localhost:27017/)')
    parser.add_argument('--mongo-db', default='scrapy_items',
                       help='MongoDB database (default: scrapy_items)')
    parser.add_argument('--mongo-collection', default='toys_normalized',
                       help='MongoDB collection (default: toys_normalized)')
    parser.add_argument('--show-stats', action='store_true',
                       help='Show statistics and exit')
    
    args = parser.parse_args()
    
    # 创建服务实例
    service = TranslationService(
        mongo_uri=args.mongo_uri,
        mongo_db=args.mongo_db,
        mongo_collection=args.mongo_collection,
        check_interval=args.interval
    )
    
    if args.show_stats:
        # 只显示统计信息
        service.connect_mongodb()
        service.show_stats()
        service.close_mongodb()
        return
    
    print("Unified Translation Service Configuration:")
    print(f"  Source: toys_translation_pending -> {args.mongo_collection}")
    print(f"  Fields: {service.fields_to_translate}")
    print()
    
    # 运行服务
    service.run()


if __name__ == "__main__":
    main() 