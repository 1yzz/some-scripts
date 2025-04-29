import os
import scrapy
from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem
from pathlib import PurePosixPath
from scrapy.utils.httpobj import urlparse_cached
from scrapy.pipelines.files import FilesPipeline
from qcloud_cos import CosConfig, CosS3Client
from scrapy.utils.project import get_project_settings
from urllib.parse import urljoin
from twisted.internet import defer

class JumpCalFilesPipeline(FilesPipeline):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        settings = get_project_settings()
        self.cos_client = self._init_cos_client(settings)
        self.bucket = settings.get('COS_BUCKET')
        self.region = settings.get('COS_REGION')
        self.cdn_domain = settings.get('COS_CDN_DOMAIN')

    def _init_cos_client(self, settings):
        secret_id = settings.get('COS_SECRET_ID')
        secret_key = settings.get('COS_SECRET_KEY')
        region = settings.get('COS_REGION')
        
        if not all([secret_id, secret_key, region]):
            raise ValueError("Missing required COS configuration")
            
        config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key)
        return CosS3Client(config)

    def file_path(self, request, response=None, info=None, *, item=None):
        path = f"jump_cal/{item.get('ip')}/{item.get('title')}/{PurePosixPath(urlparse_cached(request).path).name}"
        return path
    
    def media_failed(self, failure, request, info):
        # Handle the failed download
        print(f"Failed to download image: {request.url}")
        print("Re-downloading...")
        return request
    
    def process_item(self, item, spider):
        spider.logger.info("="*50)
        spider.logger.info(f"Processing item: {item.get('title')}")
        spider.logger.info("="*50)

        file_urls = item.get("file_urls", [])
        spider.logger.info(f"Found {len(file_urls)} file URLs to process")
        urls_to_download = []  # List to store URLs that *should* be downloaded
        settings = get_project_settings()

        if not file_urls:
            spider.logger.info("No file URLs found, skipping processing")
            return item

        # Check which files need to be downloaded
        spider.logger.info("Checking which files need to be downloaded...")
        for file_url in file_urls:
            filepath = self.file_path(scrapy.Request(file_url), item=item)
            full_path = os.path.join(settings.get('FILES_STORE'), filepath)
            if not os.path.exists(full_path):
                urls_to_download.append(file_url)
                spider.logger.info(f"File will be downloaded: {file_url}")
                spider.logger.info(f"Target path: {full_path}")
            else:
                spider.logger.info(f"File already exists: {full_path}")

        # Update the item's file_urls with the filtered list
        item["file_urls"] = urls_to_download
        spider.logger.info(f"Files to download: {len(urls_to_download)}")

        # Process the item through the parent class to download files
        spider.logger.info("Starting file downloads...")
        d = super().process_item(item, spider)
        
        def _process_files(result):
            spider.logger.info("File downloads completed")
            spider.logger.info("Starting COS uploads...")
            cdn_keys = []
            files_info = []
            
            # Process all files, whether they were just downloaded or already existed
            for file_url in file_urls:
                filepath = self.file_path(scrapy.Request(file_url), item=result)
                local_path = os.path.join(settings.get('FILES_STORE'), filepath)
                cos_key = f"jump_cal/{result.get('ip')}/{result.get('title')}/{os.path.basename(filepath)}"
                
                spider.logger.info(f"Processing file: {file_url}")
                spider.logger.info(f"Local path: {local_path}")
                spider.logger.info(f"COS key: {cos_key}")
                
                # Add file info to the files field
                file_info = {
                    'url': file_url,
                    'path': filepath,
                    'checksum': None,  # You can add checksum if needed
                    'status': 'downloaded'
                }
                files_info.append(file_info)
                
                try:
                    # Upload to COS
                    spider.logger.info(f"Uploading to COS: {cos_key}")
                    response = self.cos_client.upload_file(
                        Bucket=self.bucket,
                        LocalFilePath=local_path,
                        Key=cos_key
                    )
                    spider.logger.info(f"COS upload response: {response['ETag']}")
                    # Add COS key to the list
                    cdn_keys.append(cos_key)
                    
                    spider.logger.info(f"Successfully uploaded {local_path} to COS as {cos_key}")
                except Exception as e:
                    spider.logger.error(f"Failed to upload {local_path} to COS: {str(e)}")
            
            # Add CDN keys to the item
            result['cdn_keys'] = cdn_keys
            
            # Remove file_urls and files fields before returning to MongoDB
            if 'file_urls' in result:
                del result['file_urls']
            if 'files' in result:
                del result['files']
            
            spider.logger.info("="*50)
            spider.logger.info(f"Completed processing item: {result.get('title')}")
            spider.logger.info(f"Total files processed: {len(files_info)}")
            spider.logger.info(f"Total CDN keys generated: {len(cdn_keys)}")
            spider.logger.info("="*50)
            
            return result

        d.addCallback(_process_files)
        return d

    def _get_file_path_from_url(self, url, item, spider):
        """Helper function to construct the file path (mirrors file_path)."""
        filename = url.split('/')[-1]
        files_store = spider.crawler.spider.settings.get('FILES_STORE')
        if not files_store:
            raise ValueError("FILES_STORE setting must be defined")
        return os.path.join(files_store, 'jump_cal', item.get('ip'), item.get("title"), filename)

    def get_media_requests(self, item, info):
        for image_url in item['file_urls']:
            headers = {
                'Referer': item["url"]
            }
            yield scrapy.Request(image_url, headers=headers) 