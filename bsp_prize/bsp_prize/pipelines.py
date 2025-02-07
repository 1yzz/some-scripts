# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
import os
import scrapy
from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem
from pathlib import PurePosixPath
from scrapy.utils.httpobj import urlparse_cached
from itemadapter import ItemAdapter
from scrapy.pipelines.files import FilesPipeline



class BspPrizePipeline:
    def process_item(self, item, spider):
        return item


class DuplicatesPipeline:
    def __init__(self):
        self.ids_seen = set()

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        if adapter["url"] in self.ids_seen:
            raise DropItem(f"Item URL already seen: {adapter['url']}")
        else:
            self.ids_seen.add(adapter["url"])
            return item
        
class MyFilesPipeline(FilesPipeline):
    def file_path(self, request, response=None, info=None, *, item=None):
        return "bsp_item/" + item.get("title")  + "/" + PurePosixPath(urlparse_cached(request).path).name
    
    def media_failed(self, failure, request, info):
        # Handle the failed download
        print(f"Failed to download image: {request.url}")
        print("Re-downloading...")
        return request
    
    def process_item(self, item, spider):
        file_urls = item.get(self.files_urls_field, [])
        urls_to_download = []  # List to store URLs that *should* be downloaded

        if not file_urls:
            return item

        for file_url in file_urls:
            filepath = self._get_file_path_from_url(file_url, item, spider)  # Use helper function
            if os.path.exists(filepath):
                spider.logger.info(f"File already exists: {filepath}. Removing from download list: {file_url}")
                # Do *not* add this URL to urls_to_download
            else:
                urls_to_download.append(file_url)  # Add URL if file doesn't exist

        # Update the item's file_urls with the filtered list
        item[self.files_urls_field] = urls_to_download


        #return item  # Return the item to continue the download process
        return super().process_item(item, spider)
    


    def _get_file_path_from_url(self, url, item, spider):
        """Helper function to construct the file path (mirrors file_path)."""
        # category = spider.crawler.spider.settings.get('FILES_STORE_CATEGORY', 'default') # get category from settings
        filename = url.split('/')[-1]
        files_store = spider.crawler.spider.settings.get('FILES_STORE')
        if not files_store:
            raise ValueError("FILES_STORE setting must be defined")
        return os.path.join(files_store, 'bsp_item', item.get("title"), filename)

    
    def get_media_requests(self, item, info):
        for image_url in item['file_urls']:
            headers = {
                'Referer': item["url"]
            }
            yield scrapy.Request(image_url, headers=headers)

