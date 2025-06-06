import os
import scrapy
from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem
from pathlib import PurePosixPath
from scrapy.utils.httpobj import urlparse_cached
from qcloud_cos import CosConfig, CosS3Client
from scrapy.utils.project import get_project_settings
from urllib.parse import urljoin, urlparse, quote
import requests
from twisted.internet import defer

class UploadToCOSPipeline:
    def __init__(self, *args, **kwargs):
        settings = get_project_settings()
        self.cos_client = self._init_cos_client(settings)
        self.bucket = settings.get('COS_BUCKET')
        self.region = settings.get('COS_REGION')
        self.files_store = settings.get('FILES_STORE')
        self.spider_name = ''

        # Log COS configuration
        print("="*50)
        print("COS Configuration:")
        print(f"Bucket: {self.bucket}")
        print(f"Region: {self.region}")
        print(f"Files Store: {self.files_store}")
        print("="*50)

    def _init_cos_client(self, settings):
        secret_id = settings.get('COS_SECRET_ID')
        secret_key = settings.get('COS_SECRET_KEY')
        region = settings.get('COS_REGION')
        
        if not all([secret_id, secret_key, region]):
            raise ValueError("Missing required COS configuration")
            
        config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key)
        return CosS3Client(config)

    def open_spider(self, spider):
        self.spider_name = spider.name

    def file_path(self, url, item):
        filename = os.path.basename(urlparse(url).path)
        path = f"toy_news/{self.spider_name}/{item.get('ip')}/{item.get('title')}/{filename}"
        return path.lstrip('/')  # Remove leading slash
    
    def process_item(self, item, spider):
        spider.logger.info("="*50)
        spider.logger.info(f"Processing item: {item.get('title')}")
        spider.logger.info("="*50)

        file_urls = item.get("file_urls", [])
        spider.logger.info(f"Found {len(file_urls)} file URLs to process")
        spider.logger.info(f"File URLs: {file_urls}")
        local_files = []  # Store local file paths

        if not file_urls:
            spider.logger.info("No file URLs found, skipping processing")
            return item

        # Step 1: Download all files
        for file_url in file_urls:
            filepath = self.file_path(file_url, item)
            spider.logger.info(f"Filepath: {filepath}")
            local_path = os.path.join(self.files_store, filepath)
            
            spider.logger.info(f"Processing file: {file_url}")
            spider.logger.info(f"Local path: {local_path}")
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # Download file if it doesn't exist locally
            if not os.path.exists(local_path):
                try:
                    spider.logger.info(f"Downloading file: {file_url}")
                    response = requests.get(file_url, headers={'Referer': item['url']})
                    response.raise_for_status()
                    
                    with open(local_path, 'wb') as f:
                        f.write(response.content)
                    spider.logger.info(f"Successfully downloaded to: {local_path}")
                except Exception as e:
                    spider.logger.error(f"Failed to download {file_url}: {str(e)}")
                    continue
            
            # Verify file exists and has content
            if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
                local_files.append(local_path)
                spider.logger.info(f"File ready for processing: {local_path}")
                spider.logger.info(f"File size: {os.path.getsize(local_path)} bytes")
            else:
                spider.logger.error(f"File not available: {local_path}")

        spider.logger.info(f"Total local files ready for processing: {len(local_files)}")
        spider.logger.info(f"Local files: {local_files}")

        # Step 2: Process all local files for CDN upload
        cdn_keys = []
        for local_path in local_files:
            # Generate COS key from local path
            cos_key = os.path.relpath(local_path, self.files_store).replace('\\', '/').lstrip('/')
            # URL encode the key, but preserve forward slashes
            cos_key = '/'.join(quote(part, safe='') for part in cos_key.split('/'))
            spider.logger.info(f"Processing for CDN: {cos_key}")
            
            try:
                # Check if file exists in COS
                try:
                    spider.logger.info(f"Checking if file exists in COS: {cos_key}")
                    spider.logger.info(f"Using bucket: {self.bucket}")
                    spider.logger.info(f"Using region: {self.region}")
                    self.cos_client.head_object(
                        Bucket=self.bucket,
                        Key=cos_key
                    )
                    spider.logger.info(f"File already exists in COS: {cos_key}")
                    cdn_keys.append(cos_key)
                    spider.logger.info(f"Added existing key to cdn_keys. Current count: {len(cdn_keys)}")
                    continue
                except Exception as e:
                    error_dict = getattr(e, '__dict__', {})
                    spider.logger.info(f"Error dict: {error_dict}")
                    if error_dict.get('_status_code') == 404:
                        spider.logger.info(f"File does not exist in COS, will upload: {cos_key}")
                    else:
                        spider.logger.error(f"Error checking COS: {str(e)}")
                        raise e

                # Upload to COS
                spider.logger.info(f"Uploading to COS: {cos_key}")
                response = self.cos_client.upload_file(
                    Bucket=self.bucket,
                    LocalFilePath=local_path,
                    Key=cos_key
                )
                spider.logger.info(f"COS upload response: {response['ETag']}")
                cdn_keys.append(cos_key)
                spider.logger.info(f"Added new key to cdn_keys. Current count: {len(cdn_keys)}")
                spider.logger.info(f"Successfully uploaded to COS: {cos_key}")
            except Exception as e:
                spider.logger.error(f"Failed to upload to COS: {str(e)}")
                spider.logger.error(f"Error type: {type(e)}")
                spider.logger.error(f"Error details: {str(e)}")
                continue

        # Step 3: Update item with CDN keys
        if cdn_keys:
            spider.logger.info(f"Adding {len(cdn_keys)} CDN keys to item")
            spider.logger.info(f"CDN keys: {cdn_keys}")
            item['cdn_keys'] = cdn_keys
        else:
            spider.logger.warning("No CDN keys were generated")
            spider.logger.warning(f"Local files processed: {local_files}")
        
        # Remove file_urls field before returning to MongoDB
        if 'file_urls' in item:
            del item['file_urls']
        
        spider.logger.info("="*50)
        spider.logger.info(f"Completed processing item: {item.get('title')}")
        spider.logger.info(f"Total files processed: {len(local_files)}")
        spider.logger.info(f"Total CDN keys generated: {len(cdn_keys)}")
        spider.logger.info("="*50)
        
        return item

    def _get_file_path_from_url(self, url, item, spider):
        """Helper function to construct the file path (mirrors file_path)."""
        filename = url.split('/')[-1]
        files_store = spider.crawler.spider.settings.get('FILES_STORE')
        if not files_store:
            raise ValueError("FILES_STORE setting must be defined")
        return os.path.join(files_store, 'toy_news', self.spider_name, item.get('ip'), item.get("title"), filename)

    def get_media_requests(self, item, info):
        for image_url in item['file_urls']:
            headers = {
                'Referer': item["url"]
            }
            yield scrapy.Request(image_url, headers=headers) 