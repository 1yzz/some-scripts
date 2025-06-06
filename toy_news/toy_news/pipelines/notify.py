from datetime import datetime
from ..notify import wecom_notify_text, wecom_nofity_image_text
from itemadapter import ItemAdapter

class NotifyPipeline:
    def _format_message(self, item):
        """格式化通知内容"""
        return f"""
        商品名称: {item['name']}
        发售时间: {item.get('releaseDate')}
        价格: {item.get('price')}
        系列: {item.get('category')}
        厂商: {item.get('manufacturer')}
        更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        item_id = adapter.get('product_hash')
        
        # 从 spider.notify_meta 获取通知数据
        notify_data = getattr(spider, 'notify_meta', {}).get(item_id)

        if not notify_data or not notify_data.get('enable'):
            return item
        
        if notify_data.get('isNew'):
            title = "新增数据"
        else:
            title = "更新数据"

        try:
            if notify_data.get('type') == 'image_text':
                # 发送图片和文字通知
                wecom_nofity_image_text(
                    title=title,
                    description=self._format_message(item),
                    image_url=item.get('images')[0],
                    url=item.get('url'),
                )
            else:
                # 默认发送文字通知
                wecom_notify_text(
                    title=title,
                    content=self._format_message(item),
                )
                    
            spider.logger.info(f"Notification sent: {title}")
        except Exception as e:
            spider.logger.error(f"Error sending notification: {e}")

        try:
            # TODO: 发送消息到grpc
            pass
        except Exception as e:
            spider.logger.error(f"Error sending grpc notification: {e}")

        return item
