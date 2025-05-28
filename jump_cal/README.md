# Jump Cal Translation Service

A comprehensive translation service for Japanese to Chinese translation using DeepSeek API with MongoDB integration and caching support.

## Features

- **Batch Translation**: Efficiently translates multiple documents in batches
- **Translation Caching**: Avoids duplicate translations with intelligent caching
- **MongoDB Integration**: Works with MongoDB collections for data persistence
- **Queue-based Processing**: Monitors pending translation queues continuously
- **Multiple Collection Support**: Can handle multiple collections with different field configurations
- **Signal Handling**: Graceful shutdown with SIGINT/SIGTERM support

## Prerequisites

1. **Python 3.7+**
2. **MongoDB** (local or remote)
3. **DeepSeek API Key** - Get from [DeepSeek](https://platform.deepseek.com/)

## Installation

### 1. Install Dependencies

```bash
pip install pymongo python-openai python-dotenv
```

### 2. Set Environment Variables

Create a `.env` file or set environment variables:

```bash
export DEEPSEEK_API_KEY="your_deepseek_api_key_here"
export MONGO_URI="mongodb://localhost:27017"  # Optional, defaults to 127.0.0.1
export MONGO_DATABASE="scrapy_items"          # Optional, defaults to scrapy_items
```

## Usage

### Basic Usage

Run with default settings (monitors `jump_cal_op` and `bsp_prize` collections):

```bash
python scripts/translation_service.py
```

### Advanced Usage

#### Custom Collections and Fields

```bash
# Translate specific fields in custom collections
python scripts/translation_service.py --config "products:name,description;articles:title,content"
```

#### Custom MongoDB Settings

```bash
# Use custom MongoDB URI and database
python scripts/translation_service.py \
  --mongo-uri "mongodb://user:pass@localhost:27017" \
  --mongo-db "my_database"
```

#### Custom Check Interval

```bash
# Check for pending translations every 30 seconds
python scripts/translation_service.py --interval 30
```

#### Show Cache Statistics

```bash
# Display translation cache statistics and exit
python scripts/translation_service.py --show-cache
```

### Complete Example

```bash
python scripts/translation_service.py \
  --config "jump_cal_op:goodsName,description;bsp_prize:title,content" \
  --interval 15 \
  --mongo-uri "mongodb://localhost:27017" \
  --mongo-db "scrapy_items"
```

## Command Line Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--config` | `-c` | Collections config in format: `collection1:field1,field2;collection2:field3` | `jump_cal_op:goodsName,description;bsp_prize:title,content` |
| `--interval` | `-i` | Check interval in seconds | `10` |
| `--mongo-uri` | | MongoDB connection URI | `127.0.0.1` |
| `--mongo-db` | | MongoDB database name | `scrapy_items` |
| `--show-cache` | | Show cache statistics and exit | `false` |
| `--help` | `-h` | Show help message | |

## How It Works

### 1. Collection Structure

The service expects the following MongoDB collection structure:

- **Source Collection**: `{collection_name}` - Contains original documents
- **Translated Collection**: `{collection_name}_translated` - Stores translation results
- **Pending Collection**: `{collection_name}_translation_pending` - Queue of items awaiting translation
- **Cache Collection**: `translation_cache` - Stores cached translations

### 2. Translation Process

1. **Monitor**: Service continuously monitors pending collections
2. **Batch**: Retrieves items in configurable batches (default: 10)
3. **Cache Check**: Checks translation cache for existing translations
4. **Translate**: Sends uncached texts to DeepSeek API for translation
5. **Store**: Saves translations to cache and updates collections
6. **Cleanup**: Removes processed items from pending queue

### 3. Translation Cache

- **Hash-based**: Uses MD5 hash of original text + field name as key
- **Usage Tracking**: Tracks how often each translation is reused
- **Automatic Indexing**: Creates MongoDB indexes for optimal performance

## Alternative Scripts

### Direct Translation Script

For one-time translation of existing collections:

```bash
# Translate all documents in collection
MONGO_URI=mongodb://localhost:27017 python -m scripts.ds_trans --all

# Translate only untranslated documents
MONGO_URI=mongodb://localhost:27017 python -m scripts.ds_trans
```

### Monitoring

The service provides detailed logging:

- **Cache Statistics**: Shows cache hit/miss ratios
- **Processing Status**: Reports items processed per cycle
- **Error Handling**: Logs translation errors with details

### Performance Tips

1. **Batch Size**: Adjust batch size based on API rate limits
2. **Check Interval**: Increase interval for lower resource usage
3. **Cache Maintenance**: Monitor cache collection size and performance

## Configuration Examples

### E-commerce Products
```bash
python scripts/translation_service.py \
  --config "products:name,description,features;categories:title,description"
```

```
python scripts/translation_service.py
```