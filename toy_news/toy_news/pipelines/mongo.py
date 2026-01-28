import re
import textwrap
from itemadapter import ItemAdapter
import pymongo
from datetime import datetime, timezone
from bson import ObjectId

class MongoDBPipeline:
    """
    存储到db with history tracking support
    
    Features:
    - Maintains latest snapshot in main collection
    - Stores full history in separate _history collection
    - Tracks changes between versions
    - Version numbering for each item
    """
    def __init__(self, mongo_uri, mongo_db, mongo_collection, spider_type):
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db
        self.mongo_collection = mongo_collection
        self.history_collection_name = f"{mongo_collection}_history"
        self.spider_type = spider_type

    @classmethod
    def from_crawler(cls, crawler):
        spider_name = crawler.spider.name
        mongo_collection = getattr(crawler.spider, 'collection_name', f'{spider_name}')
        spider_type = getattr(crawler.spider, 'spider_type', 'product')
        return cls(
            mongo_uri=crawler.settings.get("MONGO_URI"),
            mongo_db=crawler.settings.get("MONGO_DATABASE", "scrapy_items"),
            mongo_collection=mongo_collection,
            spider_type=spider_type
        )

    def open_spider(self, spider):
        self.client = pymongo.MongoClient(self.mongo_uri)
        self.db = self.client[self.mongo_db]
        self.collection = self.db[self.mongo_collection]
        
        # Initialize history collection
        self.history_collection = self.db[self.history_collection_name]
        self._setup_history_collection(spider)
        
        # 创建唯一索引（如果尚未存在）
        self.collection.create_index("url", unique=True)
        self.collection.create_index("updatedAt")
        self.collection.create_index("version")

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
                    },
                    "version": {
                        "bsonType": "int",
                        "description": "version number for tracking changes"
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
    
    def _setup_history_collection(self, spider):
        """Setup history collection with indexes"""
        # Create indexes for efficient history queries
        self.history_collection.create_index("data_id")
        self.history_collection.create_index("url")
        self.history_collection.create_index("timestamp")
        self.history_collection.create_index("version")
        # Compound indexes for common queries
        self.history_collection.create_index([("data_id", 1), ("version", -1)])
        self.history_collection.create_index([("url", 1), ("timestamp", -1)])
        
        spider.logger.info(f"History collection '{self.history_collection_name}' initialized")
    
    def _detect_changes(self, old_data, new_data):
        """Detect changes between old and new data"""
        if not old_data:
            return {}
        
        changes = {}
        exclude_fields = {'_id', 'updatedAt', 'createdAt', 'version', 'spider_type'}
        
        for key in new_data.keys():
            if key in exclude_fields:
                continue
            
            old_value = old_data.get(key)
            new_value = new_data.get(key)
            
            if old_value != new_value:
                changes[key] = {
                    'old': old_value,
                    'new': new_value
                }
        
        return changes
    
    def _save_to_history(self, data_id, url, item_dict, changes, version, spider):
        """Save a snapshot to history collection"""
        history_doc = {
            'data_id': data_id,
            'url': url,
            'snapshot': item_dict,  # Full snapshot
            'changes': changes,  # Changed fields only
            'version': version,
            'timestamp': datetime.now(timezone.utc),
            'source': item_dict.get('source'),
            'spider_name': item_dict.get('spider_name')
        }
        
        try:
            result = self.history_collection.insert_one(history_doc)
            spider.logger.debug(
                f"History saved: {url} (v{version}, {len(changes)} changes)"
            )
        except Exception as e:
            spider.logger.error(f"Error saving history for {url}: {e}")

    def close_spider(self, spider):
        self.client.close()

    def process_item(self, item, spider):
        # Add timestamps to the item
        now = datetime.now(timezone.utc)

        adapter = ItemAdapter(item)

        # 使用标题作为查询条件
        query = {"url": adapter["url"]}

        # Get existing data for change detection
        old_data = self.collection.find_one(query)
        
        # Determine if new or update
        is_new = old_data is None
        current_version = old_data.get('version', 0) if old_data else 0
        new_version = 1 if is_new else (current_version + 1)
        
        # Prepare item dict
        item_dict = adapter.asdict()
        item_dict['spider_type'] = self.spider_type

        # Detect changes if updating
        changes = {}
        if not is_new:
            changes = self._detect_changes(old_data, item_dict)

        # Remove system fields from item_dict to avoid conflicts
        system_fields = {'_id', 'createdAt', 'updatedAt', 'version'}
        clean_item_dict = {k: v for k, v in item_dict.items() if k not in system_fields}

        # Build update operation
        update = {
            "$setOnInsert": {
                "createdAt": now,
            },
            "$set": {**clean_item_dict},
            "$currentDate": {
                "updatedAt": True
            }
        }
        
        # Handle version field based on whether it's new or update
        if is_new:
            # For new documents, set version on insert
            update["$setOnInsert"]["version"] = 1
        elif changes:
            # For updates with changes, increment version in $set
            update["$set"]["version"] = new_version

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

            # Save to history
            if is_new:
                spider.logger.info(f"New item created: {adapter['url']}")
                self._save_to_history(
                    data_id=new_data['_id'],
                    url=adapter['url'],
                    item_dict=item_dict,
                    changes={'_initial': True},
                    version=1,
                    spider=spider
                )
            elif changes:
                spider.logger.info(
                    f"Item updated: {adapter['url']} "
                    f"(v{new_version}, {len(changes)} fields changed)"
                )
                self._save_to_history(
                    data_id=new_data['_id'],
                    url=adapter['url'],
                    item_dict=item_dict,
                    changes=changes,
                    version=new_version,
                    spider=spider
                )
            else:
                spider.logger.debug(f"No changes detected: {adapter['url']}")

            # 如果存在变化, 发送消息到notify API
            try:
                if changes:
                    message = {
                        "id": str(uuid.uuid4()),
                        "source": adapter.get('source'),
                        "type":  "translation",
                        "payload": {
                            "_id": adapter.get('_id'),
                            "created_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                            **item_dict,
                            "description": '[Update] ' + item_dict.get('description')
                        },
                        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "attempts": 0,
                        "max_retries": 5
                    }
                    resp = requests.post(
                        url=f"{spider.settings.get('NOTIFY_API_URL')}/api/v1/translation/messages",
                        json={
                            "message": [message]
                        },
                        headers={
                            "Content-Type": "application/json"
                        }
                    )
                    resp.raise_for_status()
                    spider.logger.info(f"Changes sent to notify API: {resp.json()}")
            except Exception as e:
                spider.logger.error(f"Warning: Failed to send changes to notify API: {e}")
                
        except pymongo.errors.DuplicateKeyError:
            spider.logger.warning(f"Duplicate name found: {adapter['url']}")
        except Exception as e:
            spider.logger.error(f"Error processing item: {e}")
            raise

        return item