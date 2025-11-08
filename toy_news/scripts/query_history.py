#!/usr/bin/env python
"""
MongoDB History Query Utility

Query and analyze history data from MongoDB collections.

Examples:
    # View history for a specific URL
    python scripts/query_history.py --collection toys_normalized --url "https://example.com/item"
    
    # Show statistics
    python scripts/query_history.py --collection toys_normalized --stats
    
    # List recent changes
    python scripts/query_history.py --collection toys_normalized --recent 10
    
    # Compare two versions
    python scripts/query_history.py --collection toys_normalized --url "https://..." --compare 1 2
"""

import os
import sys
import argparse
from datetime import datetime, timedelta
from bson import ObjectId
from pymongo import MongoClient, DESCENDING
from tabulate import tabulate
import json

def get_mongo_connection(mongo_uri, mongo_db):
    """Connect to MongoDB"""
    client = MongoClient(mongo_uri)
    db = client[mongo_db]
    return client, db

def view_history(db, collection_name, url, limit=10):
    """View complete history for an item"""
    history_col = db[f"{collection_name}_history"]
    
    history = list(history_col.find({'url': url}).sort('version', DESCENDING).limit(limit))
    
    if not history:
        print(f"\nNo history found for URL: {url}")
        return
    
    print(f"\n{'='*100}")
    print(f"History for: {url}")
    print(f"Total versions: {len(history)}")
    print(f"{'='*100}\n")
    
    for entry in history:
        print(f"Version {entry['version']} - {entry['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Source: {entry.get('source', 'N/A')} | Spider: {entry.get('spider_name', 'N/A')}")
        
        changes = entry.get('changes', {})
        if '_initial' in changes:
            print("  Initial creation")
        elif changes:
            print(f"  {len(changes)} field(s) changed:")
            for field, change in changes.items():
                print(f"    {field}: {change.get('old')} → {change.get('new')}")
        else:
            print("  No changes")
        print("-" * 100)

def show_statistics(db, collection_name):
    """Show statistics about history data"""
    main_col = db[collection_name]
    history_col = db[f"{collection_name}_history"]
    
    total_items = main_col.count_documents({})
    total_history = history_col.count_documents({})
    
    print(f"\n{'='*80}")
    print(f"Statistics for: {collection_name}")
    print(f"{'='*80}\n")
    print(f"Total items: {total_items}")
    print(f"Total history entries: {total_history}")
    
    if total_items > 0:
        avg_versions = total_history / total_items
        print(f"Average versions per item: {avg_versions:.2f}")
    
    # Items with changes
    pipeline = [
        {"$group": {"_id": "$product_id", "count": {"$sum": 1}}},
        {"$match": {"count": {"$gt": 1}}},
        {"$count": "items_with_changes"}
    ]
    result = list(history_col.aggregate(pipeline))
    items_with_changes = result[0]['items_with_changes'] if result else 0
    print(f"Items with changes: {items_with_changes}")
    
    # Most changed items
    print("\n\nTop 10 Most Changed Items:")
    pipeline = [
        {"$group": {"_id": "$url", "versions": {"$sum": 1}}},
        {"$sort": {"versions": -1}},
        {"$limit": 10}
    ]
    top_items = list(history_col.aggregate(pipeline))
    
    if top_items:
        table_data = [[item['_id'][:60], item['versions']] for item in top_items]
        print(tabulate(table_data, headers=["URL", "Versions"], tablefmt="grid"))
    
    # Field change frequency
    print("\n\nMost Frequently Changed Fields:")
    pipeline = [
        {"$project": {"changes": {"$objectToArray": "$changes"}}},
        {"$unwind": "$changes"},
        {"$group": {"_id": "$changes.k", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    field_stats = list(history_col.aggregate(pipeline))
    
    if field_stats:
        table_data = [
            [item['_id'], item['count']] 
            for item in field_stats 
            if item['_id'] != '_initial'
        ]
        print(tabulate(table_data, headers=["Field", "Change Count"], tablefmt="grid"))

def list_recent(db, collection_name, limit=10, days=7):
    """List recent changes"""
    history_col = db[f"{collection_name}_history"]
    
    since = datetime.now() - timedelta(days=days)
    history = list(history_col.find({
        'timestamp': {'$gte': since}
    }).sort('timestamp', DESCENDING).limit(limit))
    
    print(f"\n{'='*100}")
    print(f"Recent Changes (last {days} days, showing {min(limit, len(history))} items)")
    print(f"{'='*100}\n")
    
    if not history:
        print("No recent changes found")
        return
    
    table_data = []
    for entry in history:
        timestamp = entry['timestamp'].strftime('%Y-%m-%d %H:%M')
        url = entry['url'][:50]
        version = entry['version']
        change_count = len([k for k in entry.get('changes', {}).keys() if k != '_initial'])
        spider = entry.get('spider_name', 'N/A')[:20]
        
        table_data.append([timestamp, url, version, change_count, spider])
    
    print(tabulate(table_data, 
                   headers=["Timestamp", "URL", "Ver", "Changes", "Spider"], 
                   tablefmt="grid"))

def compare_versions(db, collection_name, url, v1, v2):
    """Compare two versions"""
    history_col = db[f"{collection_name}_history"]
    
    version1 = history_col.find_one({'url': url, 'version': v1})
    version2 = history_col.find_one({'url': url, 'version': v2})
    
    if not version1:
        print(f"Version {v1} not found")
        return
    if not version2:
        print(f"Version {v2} not found")
        return
    
    print(f"\n{'='*100}")
    print(f"Comparing Version {v1} vs Version {v2}")
    print(f"URL: {url}")
    print(f"{'='*100}\n")
    
    snap1 = version1.get('snapshot', {})
    snap2 = version2.get('snapshot', {})
    
    all_keys = set(snap1.keys()) | set(snap2.keys())
    exclude = {'_id', 'createdAt', 'updatedAt', 'version'}
    all_keys = all_keys - exclude
    
    table_data = []
    for key in sorted(all_keys):
        val1 = snap1.get(key, 'N/A')
        val2 = snap2.get(key, 'N/A')
        
        if val1 != val2:
            status = "CHANGED"
            val1_str = str(val1)[:40]
            val2_str = str(val2)[:40]
        else:
            status = "Same"
            val1_str = str(val1)[:40]
            val2_str = "-"
        
        table_data.append([key, val1_str, val2_str, status])
    
    print(tabulate(table_data, 
                   headers=["Field", f"Version {v1}", f"Version {v2}", "Status"],
                   tablefmt="grid"))

def main():
    parser = argparse.ArgumentParser(description='MongoDB History Query Tool')
    parser.add_argument('--mongo-uri', 
                       default=os.getenv('MONGO_URI', 'mongodb://localhost:27017/'),
                       help='MongoDB URI')
    parser.add_argument('--mongo-db', 
                       default=os.getenv('MONGO_DATABASE', 'scrapy_items'),
                       help='MongoDB database name')
    parser.add_argument('--collection', required=True, 
                       help='Collection name')
    
    # Actions
    parser.add_argument('--url', help='Item URL to query')
    parser.add_argument('--limit', type=int, default=10, 
                       help='Limit number of results')
    parser.add_argument('--stats', action='store_true', 
                       help='Show statistics')
    parser.add_argument('--recent', type=int, 
                       help='Show N recent changes')
    parser.add_argument('--compare', nargs=2, type=int, metavar=('V1', 'V2'),
                       help='Compare two versions (requires --url)')
    parser.add_argument('--days', type=int, default=7,
                       help='Days to look back for recent changes')
    
    args = parser.parse_args()
    
    try:
        client, db = get_mongo_connection(args.mongo_uri, args.mongo_db)
        
        if args.stats:
            show_statistics(db, args.collection)
        elif args.recent is not None:
            list_recent(db, args.collection, args.recent, args.days)
        elif args.compare:
            if not args.url:
                print("Error: --compare requires --url")
                return 1
            compare_versions(db, args.collection, args.url, args.compare[0], args.compare[1])
        elif args.url:
            view_history(db, args.collection, args.url, args.limit)
        else:
            parser.print_help()
            return 1
        
        client.close()
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())

