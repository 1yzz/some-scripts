# MongoDB History Tracking

Complete documentation for the MongoDB history tracking feature in the Toy News scraper.

## Overview

The MongoDB pipelines now support automatic history tracking. Every time an item is created or updated, the system:
- Stores the latest version in the main collection
- Saves a complete snapshot to a separate history collection
- Tracks which fields changed and their old/new values
- Assigns version numbers to track evolution over time

## Features

✅ **Full Snapshot Storage** - Complete item data saved for each version  
✅ **Change Detection** - Automatic detection of modified fields  
✅ **Version Numbering** - Sequential version tracking  
✅ **Configurable** - Enable/disable via settings  
✅ **Indexed** - Optimized queries with proper indexes  
✅ **Query Tools** - Built-in utility for analyzing history  

## Collections Structure

### Main Collection (e.g., `toys_normalized`)
Latest snapshot with version tracking:

```javascript
{
  "_id": ObjectId("..."),
  "url": "https://example.com/item",
  "name": "Product Name",
  "price": "¥3,500",
  "version": 3,  // Current version number
  "createdAt": ISODate("2024-01-01T00:00:00Z"),
  "updatedAt": ISODate("2024-01-15T10:30:00Z")
}
```

### History Collection (e.g., `toys_normalized_history`)
Complete history with all versions:

```javascript
{
  "_id": ObjectId("..."),
  "product_id": ObjectId("..."),  // Reference to main document
  "url": "https://example.com/item",
  "version": 2,
  "timestamp": ISODate("2024-01-10T08:15:00Z"),
  "source": "bandai_hobby",
  "spider_name": "bandai_hobby_gundam",
  
  // Full snapshot of data at this version
  "snapshot": {
    "url": "https://example.com/item",
    "name": "Product Name",
    "price": "¥3,000",
    // ... all fields ...
  },
  
  // Changed fields only
  "changes": {
    "price": {
      "old": "¥2,500",
      "new": "¥3,000"
    },
    "releaseDate": {
      "old": "2024-02-01",
      "new": "2024-02-15"
    }
  }
}
```

## Configuration

### Enable/Disable History Tracking

In your Scrapy `settings.py`:

```python
# Enable history tracking (default: True)
MONGO_ENABLE_HISTORY = True

# Disable history tracking
MONGO_ENABLE_HISTORY = False
```

### Per-Spider Configuration

You can also disable history for specific spiders:

```python
# In your spider
class MySpider(scrapy.Spider):
    custom_settings = {
        'MONGO_ENABLE_HISTORY': False
    }
```

## Usage Examples

### View History for a Specific Item

```bash
python scripts/query_history.py \
    --collection toys_normalized \
    --url "https://example.com/item" \
    --limit 10
```

Output:
```
==================================================================================================
History for: https://example.com/item
Total versions: 5
==================================================================================================

Version 5 - 2024-01-15 10:30:00
Source: bandai_hobby | Spider: bandai_hobby_gundam
  2 field(s) changed:
    price: ¥3,000 → ¥3,500
    stock: In Stock → Out of Stock
--------------------------------------------------------------------------------------------------

Version 4 - 2024-01-10 08:15:00
Source: bandai_hobby | Spider: bandai_hobby_gundam
  1 field(s) changed:
    price: ¥2,500 → ¥3,000
--------------------------------------------------------------------------------------------------

Version 1 - 2024-01-01 00:00:00
Source: bandai_hobby | Spider: bandai_hobby_gundam
  Initial creation
```

### Show Statistics

```bash
python scripts/query_history.py \
    --collection toys_normalized \
    --stats
```

Output shows:
- Total items and history entries
- Average versions per item
- Items with changes
- Most frequently changed items
- Most frequently changed fields

### List Recent Changes

```bash
# Show last 20 changes in the past 7 days
python scripts/query_history.py \
    --collection toys_normalized \
    --recent 20 \
    --days 7
```

### Compare Two Versions

```bash
python scripts/query_history.py \
    --collection toys_normalized \
    --url "https://example.com/item" \
    --compare 2 5
```

Shows a side-by-side comparison of fields that changed between versions.

## MongoDB Queries

### Find All Versions of an Item

```javascript
db.toys_normalized_history.find({
  url: "https://example.com/item"
}).sort({version: -1})
```

### Find Items Changed Recently

```javascript
db.toys_normalized_history.find({
  timestamp: {
    $gte: new Date(Date.now() - 7*24*60*60*1000)
  }
}).sort({timestamp: -1})
```

### Find Items with Price Changes

```javascript
db.toys_normalized_history.find({
  "changes.price": {$exists: true}
})
```

### Get Latest Version Number

```javascript
db.toys_normalized.findOne(
  {url: "https://example.com/item"},
  {version: 1}
)
```

### Count Total Versions for Each Item

```javascript
db.toys_normalized_history.aggregate([
  {$group: {
    _id: "$url",
    totalVersions: {$sum: 1}
  }},
  {$sort: {totalVersions: -1}}
])
```

## Indexes

The following indexes are automatically created:

**Main Collection:**
- `url` (unique)
- `updatedAt`
- `version`

**History Collection:**
- `product_id`
- `url`
- `timestamp`
- `version`
- `(product_id, version)` (compound, descending on version)
- `(url, timestamp)` (compound, descending on timestamp)

## Implementation Details

### MongoDBPipeline (Base Class)

The base pipeline in `toy_news/pipelines/mongo.py` provides:
- History collection initialization
- Change detection logic
- Version management
- Snapshot storage

**Key Methods:**
- `_setup_history_collection()` - Creates indexes
- `_detect_changes()` - Compares old vs new data
- `_save_to_history()` - Saves snapshot to history

### Child Pipelines

#### JumpCalMongoPipeline
Uses `goodsName` as unique identifier (overrides parent's `url` key).

#### BspMongoPipeline
Uses `url` as unique identifier (default behavior, no override needed).

### Custom Pipelines

To create your own pipeline with history tracking:

```python
from toy_news.pipelines.mongo import MongoDBPipeline

class MyCustomPipeline(MongoDBPipeline):
    """
    Custom pipeline with history tracking
    """
    # If using 'url' as unique key, no override needed!
    pass

# Or override for custom unique key:
class MyCustomPipeline(MongoDBPipeline):
    def open_spider(self, spider):
        # Initialize MongoDB
        self.client = pymongo.MongoClient(self.mongo_uri)
        self.db = self.client[self.mongo_db]
        self.collection = self.db[self.mongo_collection]
        
        if self.enable_history:
            self.history_collection = self.db[self.history_collection_name]
            self._setup_history_collection(spider)
        
        # Custom unique index
        self.collection.create_index("custom_id", unique=True)
        # ... rest of setup ...
    
    def process_item(self, item, spider):
        # Custom query using your unique key
        query = {"custom_id": adapter["custom_id"]}
        # ... rest inherits from parent ...
```

## Performance Considerations

### Storage

- Each version stores a complete snapshot
- Storage grows with: number of items × number of updates
- Typical overhead: ~2-5x main collection size

### Query Performance

- All common queries are indexed
- Recent changes queries are very fast
- Full history reconstruction is O(n) where n = versions

### Optimization Tips

1. **Disable for Testing**
   ```python
   MONGO_ENABLE_HISTORY = False  # During development
   ```

2. **Archive Old History**
   ```javascript
   // Archive history older than 1 year
   db.toys_normalized_history.deleteMany({
     timestamp: {$lt: new Date(Date.now() - 365*24*60*60*1000)}
   })
   ```

3. **Index Maintenance**
   ```javascript
   // Rebuild indexes if performance degrades
   db.toys_normalized_history.reIndex()
   ```

## Troubleshooting

### History Not Being Saved

Check:
1. `MONGO_ENABLE_HISTORY` is `True` in settings
2. No errors in spider logs
3. History collection exists: `db.getCollectionNames()`

### Version Numbers Not Incrementing

- Versions only increment when changes are detected
- Check if fields are actually changing
- Excluded fields: `_id`, `updatedAt`, `createdAt`, `version`

### Too Many History Entries

- Expected behavior for frequently changing items
- Consider archiving old history
- Or adjust scraping frequency

## Best Practices

1. **Monitor Storage**
   - Regularly check database size
   - Archive or delete old history as needed

2. **Query Patterns**
   - Use indexes for efficient queries
   - Limit results when querying large histories

3. **Change Detection**
   - Keep field names consistent
   - Normalize data before saving

4. **Logging**
   - Review spider logs for history activity
   - Monitor for duplicate key errors

## Examples in Production

### Tracking Price Changes

```bash
# Find all items with price changes in last 30 days
python scripts/query_history.py \
    --collection toys_normalized \
    --recent 100 \
    --days 30 | grep -i price
```

### Auditing Data Quality

```bash
# Check which fields change most often (data quality indicator)
python scripts/query_history.py \
    --collection toys_normalized \
    --stats
```

### Rollback Detection

```javascript
// Find items that changed then changed back
db.toys_normalized_history.aggregate([
  {$match: {"changes.price": {$exists: true}}},
  {$sort: {url: 1, version: 1}},
  {$group: {
    _id: "$url",
    prices: {$push: "$changes.price.new"}
  }},
  {$match: {
    $expr: {
      $ne: [
        {$arrayElemAt: ["$prices", 0]},
        {$arrayElemAt: ["$prices", -1]}
      ]
    }
  }}
])
```

## Support

For issues or questions:
1. Check spider logs for errors
2. Verify MongoDB connection and permissions
3. Test with a small dataset first
4. Review this documentation

## Future Enhancements

Potential improvements:
- [ ] Differential storage (only store changes, not full snapshots)
- [ ] Compression for old history entries
- [ ] Web UI for browsing history
- [ ] Automated anomaly detection
- [ ] History export to time-series database

