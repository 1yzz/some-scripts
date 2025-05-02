import os
from datetime import datetime
import pymongo
from pymongo import UpdateOne
import sys
from jump_cal.translators.deepseek_translator import DeepSeekTranslator

class MongoTranslator:
    def __init__(self, mongo_uri, mongo_db, source_collection, target_collection, translate_all=False):
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db
        self.source_collection = source_collection
        self.target_collection = target_collection
        self.translator = DeepSeekTranslator()
        self.FIELDS_TO_TRANSLATE = ['title', 'goodsName']
        self.translate_all = translate_all

    def connect_mongodb(self):
        self.client = pymongo.MongoClient(self.mongo_uri)
        self.db = self.client[self.mongo_db]
        self.source_coll = self.db[self.source_collection]
        self.target_coll = self.db[self.target_collection]

    def close_mongodb(self):
        self.client.close()

    def process_collection(self):
        try:
            print("\n=== Starting Batch Translation Process ===")
            self.connect_mongodb()
            
            # Get all documents if translate_all is True, otherwise get only untranslated
            query = {} if self.translate_all else {'translatedAt': {'$exists': False}}
            
            # Get total count of documents to process
            total_docs = self.source_coll.count_documents(query)
            print(f"Total documents to process: {total_docs}")
            
            # Process documents in batches of 10
            batch_size = 10
            processed_count = 0
            
            while processed_count < total_docs:
                # Get next batch of documents
                cursor = self.source_coll.find(query).limit(batch_size)
                
                docs_to_translate = list(cursor)
                if not docs_to_translate:
                    break
                
                print(f"\nProcessing batch {processed_count//batch_size + 1} ({len(docs_to_translate)} documents)...")
                
                try:
                    # Translate the batch using the DeepSeek translator module
                    translated_docs = self.translator.batch_translate_documents(
                        docs_to_translate,
                        self.FIELDS_TO_TRANSLATE
                    )
                    
                    # Update target collection with only translated fields
                    bulk_operations = []
                    for doc in translated_docs:
                        # Create update with only translated fields that exist
                        translated_fields = {}
                        for field in self.FIELDS_TO_TRANSLATE:
                            translated_field = f'{field}CN'
                            if translated_field in doc:
                                translated_fields[translated_field] = doc[translated_field]
                        
                        if translated_fields:  # Only add if we have translations
                            bulk_operations.append(
                                UpdateOne(
                                    {'_id': doc['_id']},
                                    {'$set': {**translated_fields, 'updatedAt': datetime.now()}},
                                    upsert=True
                                )
                            )
                    
                    if bulk_operations:
                        self.target_coll.bulk_write(bulk_operations)
                        
                        # Update source collection to mark as translated
                        source_bulk_operations = []
                        for doc in translated_docs:
                            source_bulk_operations.append(
                                UpdateOne(
                                    {'_id': doc['_id']},
                                    {'$set': {'translatedAt': datetime.now()}}
                                )
                            )
                        self.source_coll.bulk_write(source_bulk_operations)
                    
                    processed_count += len(translated_docs)
                    print(f"Successfully processed batch. Total processed: {processed_count}/{total_docs}")
                    
                except Exception as e:
                    print(f"Error processing batch: {str(e)}")
                    continue

            print("\n=== Processing Complete ===")
            print(f"Total documents processed: {processed_count}")
            print(f"Remaining documents: {total_docs - processed_count}")
                    
        except Exception as e:
            print(f"Error in process_collection: {str(e)}")
        finally:
            self.close_mongodb()


def main():
    # Simple flag check for --all
    translate_all = len(sys.argv) > 1 and sys.argv[1] == '--all'

    # Configuration
    mongo_uri = os.getenv('MONGO_URI', '127.0.0.1')
    mongo_db = os.getenv('MONGO_DATABASE', 'scrapy_items')
    source_collection = 'jump_cal_op'  # Source collection with Japanese content
    target_collection = 'jump_cal_op_translated'  # Target collection for translated content
    
    # Initialize and run translator
    translator = MongoTranslator(
        mongo_uri=mongo_uri,
        mongo_db=mongo_db,
        source_collection=source_collection,
        target_collection=target_collection,
        translate_all=translate_all
    )
    
    translator.process_collection()


if __name__ == "__main__":
    main()
