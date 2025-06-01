# Toy News - 统一数据归一化与翻译系统

一个基于 Scrapy 的玩具资讯爬取与翻译系统，支持数据归一化、智能去重和缓存翻译。

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              TOY NEWS 数据处理架构                                │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   爬虫层     │    │   数据处理   │    │   存储层     │    │   翻译层     │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘

┌─────────────┐    ┌─────────────┐
│JumpCal Spider│    │DataValidation│    
│BSP Prize    │───▶│DataQuality  │    
│Spider       │    │Pipeline     │    
└─────────────┘    └─────────────┘    
                           │                           
                           ▼                           
                   ┌─────────────┐    ┌─────────────┐
                   │原始数据存储  │    │归一化处理    │
                   │Pipeline     │───▶│Pipeline     │
                   └─────────────┘    └─────────────┘
                           │                   │
                           ▼                   ▼
                   ┌─────────────┐    ┌─────────────┐
                   │原始数据集合  │    │归一化数据    │
                   │jump_cal_*   │    │toys_        │
                   │bsp_prize_*  │    │normalized   │
                   └─────────────┘    └─────────────┘
                                             │
                                             ▼
                                     ┌─────────────┐
                                     │翻译Pipeline │
                                     └─────────────┘
                                             │
                                             ▼
                                     ┌─────────────┐
                                     │translation_ │
                                     │pending      │
                                     └─────────────┘
                                             │
                   ┌─────────────┐           ▼
                   │translation_ │    ┌─────────────┐
                   │cache        │◀───│Translation  │
                   └─────────────┘    │Service      │
                                     └─────────────┘
                                             │
                                             ▼
                                     ┌─────────────┐
                                     │翻译结果更新  │
                                     │至toys_      │
                                     └─────────────┘

数据流向：
原始爬取 → 数据验证 → 原始存储 → 数据归一化 → 翻译处理 → 缓存优化
```

## 📊 数据存储结构

```
MongoDB Collections:
├── 原始数据层
│   ├── jump_cal_op          # ONEPIECE 商品数据
│   ├── jump_cal_hunter      # Hunter×Hunter 商品数据  
│   ├── bsp_prize_op         # BSP Prize 数据
│   └── ...                  # 其他原始数据集合
│
├── 归一化数据层  
│   └── toys_normalized  # 统一商品数据结构
│       ├── product_hash     # 商品哈希ID (去重标识)
│       ├── name            # 商品名称
│       ├── description     # 商品描述  
│       ├── nameCN          # 中文商品名称 (翻译结果)
│       ├── descriptionCN   # 中文描述 (翻译结果)
│       └── ...             # 其他归一化字段
│
└── 翻译管理层
    ├── translation_pending  # 待翻译队列
    └── translation_cache    # 翻译结果缓存
```

## 🚀 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone <repository>
cd toy_news

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
export DEEPSEEK_API_KEY="your_api_key"
export MONGO_URI="mongodb://localhost:27017/"
export MONGO_DATABASE="scrapy_items"
```

### 2. 运行爬虫

```bash
# 爬取 ONEPIECE 商品数据
scrapy crawl jump_cal_op

# 爬取 Hunter×Hunter 商品数据  
scrapy crawl jump_cal_hunter

# 爬取 BSP Prize 数据
scrapy crawl bsp_prize_op
```

### 3. 启动翻译服务

```bash
# 启动统一翻译服务
python scripts/translation_service.py

# 查看翻译统计
python scripts/translation_service.py --show-stats

# 自定义检查间隔
python scripts/translation_service.py --interval 30
```

## 📋 Pipeline 配置

系统使用分层 Pipeline 架构：

```python
ITEM_PIPELINES = {
    # 1. 数据验证和清洗 (100-200)
    'toy_news.pipelines.normalization.DataValidationPipeline': 100,
    'toy_news.pipelines.normalization.DataQualityPipeline': 200,
    
    # 2. 文件下载 (300)
    'toy_news.pipelines.files.ToyNewsFilesPipeline': 300,
    
    # 3. 原始数据存储 (400-700)
    'toy_news.pipelines.jump_cal.PurifyPipeline': 600,
    'toy_news.pipelines.jump_cal.JumpCalMongoPipeline': 700,
    
    # 4. 数据归一化 (800)
    'toy_news.pipelines.normalization.DataNormalizationPipeline': 800,
    
    # 5. 翻译服务 (950)
    'toy_news.pipelines.translation.TranslationPipeline': 950,
}
```

## 🔧 核心功能

### 数据归一化

将不同数据源的商品信息统一为标准格式：

```python
# Jump Cal 数据映射
jump_cal_item = {
    'goodsName': '路飞手办',
    'genre': 'フィギュア', 
    'price': '¥3,500'
}

# 归一化后
normalized_item = {
    'product_hash': 'jump_cal_a1b2c3d4',
    'name': '路飞手办',
    'description': 'フィギュア',
    'price': '¥3,500',
    'source': 'jump_cal'
}
```

### 智能翻译

基于内容哈希的去重翻译：

```python
# 相同内容只翻译一次
text = "路飞手办"
product_hash = "jump_cal_a1b2c3d4"

# 首次翻译
translation_service.translate(text) → "Luffy Figure"

# 后续相同内容直接使用缓存
cache_hit = translation_cache.get(text) → "Luffy Figure"
```

### 翻译缓存

```python
# 缓存结构
{
    'text_hash': 'md5_hash_of_text',
    'original_text': '路飞手办',
    'translated_text': 'Luffy Figure', 
    'usage_count': 15,
    'created_at': datetime,
    'updated_at': datetime
}
```

## 📊 监控与统计

### 查看翻译状态

```bash
# 显示详细统计
python scripts/translation_service.py --show-stats
```

输出示例：
```
Translation pending: 25 items
Translated products: 150/200  
Translation cache: 85 entries, 340 total uses
```

### MongoDB 查询示例

```javascript
// 查看待翻译队列
db.translation_pending.find().limit(5)

// 查看已翻译产品
db.toys_normalized.find({
    "nameCN": {$exists: true}
}).limit(5)

// 缓存命中率分析
db.translation_cache.aggregate([
    {$group: {
        _id: null,
        totalEntries: {$sum: 1},
        totalUsage: {$sum: "$usage_count"},
        avgUsage: {$avg: "$usage_count"}
    }}
])
```

## ⚙️ 配置选项

### 爬虫配置

```python
# settings.py
BOT_NAME = 'toy_news'
ROBOTSTXT_OBEY = True
DOWNLOAD_DELAY = 1
RANDOMIZE_DOWNLOAD_DELAY = True

# MongoDB 配置
MONGO_URI = "mongodb://localhost:27017/"
MONGO_DATABASE = "scrapy_items"
```

### 翻译服务配置

```bash
# 命令行选项
--interval 10           # 检查间隔(秒)
--mongo-uri URL        # MongoDB 连接串
--mongo-db NAME        # 数据库名称  
--show-stats           # 显示统计信息
```

## 🔍 数据字段说明

### 归一化字段

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `product_hash` | String | 商品哈希ID | `jump_cal_a1b2c3d4` |
| `name` | String | 商品名称 | `路飞手办` |
| `description` | String | 商品描述 | `フィギュア` |
| `price` | String | 价格信息 | `¥3,500` |
| `category` | String | 商品分类 | `Figure` |
| `manufacturer` | String | 制造商 | `バンダイ` |
| `source` | String | 数据源 | `jump_cal` |
| `spider_name` | String | 爬虫名称 | `jump_cal_op` |

### 翻译字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `nameCN` | String | 中文商品名称 |
| `descriptionCN` | String | 中文商品描述 |

## 🛠️ 故障排除

### 常见问题

1. **翻译服务无法启动**
   ```bash
   # 检查 API Key
   echo $DEEPSEEK_API_KEY
   
   # 检查 MongoDB 连接
   mongosh $MONGO_URI
   ```

2. **无待翻译数据**
   ```bash
   # 检查 pipeline 配置
   # 确保包含 DataNormalizationPipeline
   ```

3. **翻译结果为空**
   ```bash
   # 检查 DeepSeek API 配额
   # 查看翻译服务日志
   ```

## 📈 性能优化

### 批处理优化

```python
# translation_service.py
self.batch_size = 10  # 调整批处理大小
self.check_interval = 10  # 调整检查间隔
```

### 缓存优化

```python
# 缓存命中率优化
# 1. 文本预处理统一
# 2. 去除无意义字符
# 3. 大小写标准化
```

### 数据库优化

```javascript
// 创建必要索引
db.toys_normalized.createIndex({product_hash: 1})
db.translation_pending.createIndex({product_hash: 1})
db.translation_cache.createIndex({text_hash: 1})
```

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🔗 相关链接

- [Scrapy 文档](https://scrapy.org/)
- [MongoDB 文档](https://docs.mongodb.com/)
- [DeepSeek API](https://platform.deepseek.com/)
