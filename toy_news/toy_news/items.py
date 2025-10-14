# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy
import hashlib


# 映射函数注册表（在类外部定义）
_MAPPERS = {}

def register_mapper(source_name):
    """装饰器：注册映射函数"""
    def decorator(func):
        _MAPPERS[source_name] = func
        return func
    return decorator


class BaseItem(scrapy.Item):
    """基础Item - 所有爬虫数据的通用字段"""
    # 元数据
    _id = scrapy.Field()             # 商品唯一ID
    source = scrapy.Field()          # 数据源标识 (jump_cal, bsp_prize)
    spider_name = scrapy.Field()     # 爬虫名称
    url = scrapy.Field()             # 原始URL
    ip = scrapy.Field()              # IP/品牌 (ONEPIECE, JUMP等)


class ProductItem(BaseItem):
    """商品数据归一化Item - 简化版本"""
    # 核心商品信息
    product_hash = scrapy.Field()    # 商品哈希ID (基于名称+URL生成)
    name = scrapy.Field()            # 商品名称
    description = scrapy.Field()     # 商品描述
    price = scrapy.Field()           # 价格信息
    category = scrapy.Field()        # 商品分类
    release_date = scrapy.Field()    # 发售日期
    manufacturer = scrapy.Field()    # 制造商/厂商
    
    # 媒体文件
    images = scrapy.Field()          # 图片URL列表
    cdn_keys = scrapy.Field()        # 文件CDN key
    
    # 原始数据引用
    raw_data_id = scrapy.Field()     # 原始数据的引用ID

    # 额外字段
    extra_fields = scrapy.Field()    # 额外字段

class DataMapper:
    """数据映射器 - 将原始数据映射到归一化结构"""
    
    @staticmethod
    def map_to_product(raw_item, source):
        """统一入口：根据 source 自动选择映射函数"""
        mapper = _MAPPERS.get(source)
        if mapper:
            return mapper(raw_item)
        return None
    
    @staticmethod
    def _generate_hash(text):
        """生成确定性哈希"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()[:8]
    
    @staticmethod
    @register_mapper('jump_cal')
    def map_jump_cal_to_product(raw_item):
        """将JumpCal数据映射到ProductItem"""
        product = ProductItem()
        
        # 基础信息
        product['source'] = 'jump_cal'
        product['spider_name'] = raw_item.get('spider_name')
        product['url'] = raw_item.get('url')
        product['ip'] = raw_item.get('ip')
        
        # 商品信息映射
        product['name'] = raw_item.get('goodsName')
        product['description'] = raw_item.get('genre', '')
        product['price'] = raw_item.get('price')
        product['category'] = raw_item.get('genre')
        product['release_date'] = raw_item.get('releaseDate')
        product['manufacturer'] = raw_item.get('maker')
        product['product_hash'] = product['spider_name'] + '_' + DataMapper._generate_hash(f"{product['name']}|{product['url']}")

        return product
    
    @staticmethod
    @register_mapper('bsp_prize')
    def map_bsp_prize_to_product(raw_item):
        """将BSP Prize数据映射到ProductItem"""
        product = ProductItem()
        
        # 基础信息
        product['source'] = 'bsp_prize'
        product['spider_name'] = raw_item.get('spider_name')
        product['url'] = raw_item.get('url')
        product['ip'] = raw_item.get('ip')
        
        # 商品信息映射
        product['name'] = raw_item.get('title')
        product['description'] = raw_item.get('desc', '')
        product['price'] = ''  # BSP Prize通常没有价格
        product['category'] = 'Prize Figure'
        product['release_date'] = raw_item.get('releaseDate')
        product['manufacturer'] = 'Banpresto'
        product['images'] = raw_item.get('gallery', [])
        # 同步CDN_Keys
        product['cdn_keys'] = raw_item.get('cdn_keys', [])
        product['product_hash'] = product['spider_name'] + '_' + DataMapper._generate_hash(f"{product['name']}|{product['url']}")

        return product

    @staticmethod
    @register_mapper('bandai_hobby')
    def map_bandai_hobby_to_product(raw_item):
        """将Bandai Hobby数据映射到ProductItem"""
        product = ProductItem()
        
        # 基础信息
        product['source'] = 'bandai_hobby'
        product['spider_name'] = raw_item.get('spider_name')
        product['url'] = raw_item.get('url')
        product['ip'] = raw_item.get('ip')
        
        # 商品信息映射
        product['name'] = raw_item.get('title')
        product['description'] = raw_item.get('desc', '')
        product['price'] = raw_item.get('price')
        product['category'] = 'Bandai Hobby'
        product['release_date'] = raw_item.get('releaseDate')
        product['manufacturer'] = 'Bandai'
        product['images'] = raw_item.get('gallery', [])
        # 同步CDN_Keys
        product['cdn_keys'] = raw_item.get('cdn_keys', [])
        product['product_hash'] = product['spider_name'] + '_' + DataMapper._generate_hash(f"{product['name']}|{product['url']}")

        return product

    @staticmethod
    @register_mapper('op_base_shop')
    def map_op_base_shop_to_product(raw_item):
        """将OP Base Shop数据映射到ProductItem"""
        product = ProductItem()
        
        # 基础信息
        product['source'] = 'op_base_shop'
        product['spider_name'] = raw_item.get('spider_name')
        product['url'] = raw_item.get('url')
        product['ip'] = raw_item.get('ip')

          # 商品信息映射
        product['name'] = raw_item.get('title')
        product['description'] = raw_item.get('desc', '')
        product['price'] = raw_item.get('price')
        product['category'] = raw_item.get('category')
        product['release_date'] = raw_item.get('releaseDate')
        product['images'] = raw_item.get('images', [])

        # 同步CDN_Keys
        product['cdn_keys'] = raw_item.get('cdn_keys', [])
        product['product_hash'] = product['spider_name'] + '_' + DataMapper._generate_hash(f"{product['name']}|{product['url']}")

        return product

    @staticmethod
    @register_mapper('tamashii_web')
    def map_tamashii_web_to_product(raw_item):
        """将Tamashii Web数据映射到ProductItem"""
        product = ProductItem()
        
        # 基础信息
        product['source'] = 'tamashii_web'
        product['spider_name'] = raw_item.get('spider_name')
        product['url'] = raw_item.get('url')
        product['ip'] = raw_item.get('ip')

        product['name'] = raw_item.get('title')
        product['price'] = raw_item.get('price')
        product['category'] = raw_item.get('category')
        product['release_date'] = raw_item.get('releaseDate')
        product['images'] = raw_item.get('images', [])
        product['description'] = raw_item.get('desc', '')
        product['cdn_keys'] = raw_item.get('cdn_keys', [])
        product['product_hash'] = product['spider_name'] + '_' + DataMapper._generate_hash(f"{product['name']}|{product['url']}")

        product['extra_fields'] = [{
            'key': 'salesForm',
            'label': '販売方法',
            'value': raw_item.get('salesForm')
        }, {
            'key': 'openDate',
            'label': '预订开始日期',
            'value': raw_item.get('openDate')
        }]

        return product
