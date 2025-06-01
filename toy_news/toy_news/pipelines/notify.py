from datetime import datetime
from ..notify import notify_all

class NotifyPipeline:
    def _format_message(self, item):
        """格式化通知内容"""
        return f"""
        商品名称: {item['goodsName']}
        发售时间: {item.get('releaseDate')}
        价格: {item.get('genre')}
        系列: {item.get('price')}
        厂商: {item.get('maker')}
        更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """

    def process_item(self, item, spider):
        if not item.get("notify"):  
            return item
        
        try:
            title = "新增数据" if item.get("Add") else "更新数据"

            # 发送通知
            notify_all(
                title=title,
                content=self._format_message(item),
            )
                    
            spider.logger.info(f"Notification sent: {title}")
        except Exception as e:
            spider.logger.error(f"Error sending notification: {e}")

        return item
