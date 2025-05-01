import os
from datetime import datetime
import pymongo
from pymongo import UpdateOne
from openai import OpenAI
from typing import List, Dict
import sys  # Add this import


class DeepSeekTranslator:
    def __init__(self, mongo_uri, mongo_db, source_collection, target_collection, translate_all=False):
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db
        self.source_collection = source_collection
        self.target_collection = target_collection
        self.deepseek = OpenAI(api_key=os.getenv('DEEPSEEK_API_KEY'), base_url="https://api.deepseek.com")
        self.FIELDS_TO_TRANSLATE = ['title', 'goodsName']
        self.translate_all = translate_all

    def connect_mongodb(self):
        self.client = pymongo.MongoClient(self.mongo_uri)
        self.db = self.client[self.mongo_db]
        self.source_coll = self.db[self.source_collection]
        self.target_coll = self.db[self.target_collection]

    def close_mongodb(self):
        self.client.close()

    def batch_translate_texts(self, texts: List[str]) -> List[str]:
        try:
            # Combine all texts into one prompt with numbering
            combined_text = "\n---\n".join([f"{i+1}. {text}" for i, text in enumerate(texts)])
            
            print(f"\nSending batch of {len(texts)} texts for translation...")
            print(f"Original texts:\n{combined_text}")
            
            response = self.deepseek.chat.completions.create(
                model="deepseek-coder",
                temperature=1.3,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that translates Japanese text to Chinese. Please translate each text separately and maintain the numbering. Return only the translations, one per line, with the same numbering."},
                    {"role": "user", "content": f"Translate the following texts from Japanese to Chinese, keeping the same numbering:\n{combined_text}"}
                ]
            )
            
            # Get the response content
            response_text = response.choices[0].message.content.strip()
            print(f"Translation response:\n{response_text}")
            
            # Split the response into individual translations
            translations = []
            for line in response_text.split('\n'):
                # Skip empty lines and separator lines
                if not line.strip() or line.strip() == '---':
                    continue
                    
                # Try to extract the translation
                try:
                    # Handle both formats: "1. translation" or just "translation"
                    if '. ' in line:
                        translation = line.split('. ', 1)[1]
                    else:
                        translation = line
                    translations.append(translation.strip())
                except Exception as e:
                    print(f"Error parsing translation line: {line}")
                    translations.append(line.strip())
            
            # Verify we got the right number of translations
            if len(translations) != len(texts):
                print(f"Warning: Got {len(translations)} translations for {len(texts)} texts")
                # Pad with original texts if we got fewer translations
                while len(translations) < len(texts):
                    translations.append(texts[len(translations)])
            
            print(f"Processed translations:\n{translations}")
            return translations
            
        except Exception as e:
            print(f"Batch translation error: {str(e)}")
            return texts

    def translate_documents_batch(self, docs: List[Dict]) -> List[Dict]:
        translated_docs = []
        
        # Prepare batches for each field
        for field in self.FIELDS_TO_TRANSLATE:
            texts_to_translate = []
            doc_indices = []
            
            # Collect all texts for this field
            for i, doc in enumerate(docs):
                if field in doc and doc[field]:
                    texts_to_translate.append(doc[field])
                    doc_indices.append(i)
            
            if texts_to_translate:
                print(f"\nTranslating {len(texts_to_translate)} {field} fields...")
                translations = self.batch_translate_texts(texts_to_translate)
                
                # Apply translations back to documents
                for idx, translation in zip(doc_indices, translations):
                    if idx >= len(translated_docs):
                        translated_docs.append(docs[idx].copy())
                    translated_docs[idx][f'{field}CN'] = translation
        
        # Add timestamp and verify translations
        for doc in translated_docs:
            
            # Verify at least one field was translated
            translation_performed = False
            for field in self.FIELDS_TO_TRANSLATE:
                if f'{field}CN' in doc and doc[f'{field}CN'] != doc[field]:
                    translation_performed = True
                    break
            
            if not translation_performed:
                raise ValueError(f"No translation was performed for document {doc['_id']}")
        
        return translated_docs

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
                    # Translate the batch
                    translated_docs = self.translate_documents_batch(docs_to_translate)
                    
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
    translator = DeepSeekTranslator(
        mongo_uri=mongo_uri,
        mongo_db=mongo_db,
        source_collection=source_collection,
        target_collection=target_collection,
        translate_all=translate_all
    )
    
    translator.process_collection()

if __name__ == "__main__":
    main()
