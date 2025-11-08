import re
import textwrap
from datetime import datetime
from toy_news.pipelines.mongo import MongoDBPipeline

class BspMongoPipeline(MongoDBPipeline):
    """
    存储到db with history tracking (inherits from MongoDBPipeline)
    Uses 'url' as unique identifier (default behavior from parent class)
    
    No customization needed - inherits all functionality from MongoDBPipeline
    """
    pass