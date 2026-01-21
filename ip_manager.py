"""IP Manager - Track and manage IP address usage in MongoDB"""

import json
from typing import Optional, Dict, List
from datetime import datetime, timezone
from pathlib import Path
from pymongo import ReturnDocument
from pymongo.errors import BulkWriteError
from utils import logger

# Import your DatabaseManager
from database import DatabaseManager

from dotenv import load_dotenv


# Load environment variables from .env file
env_path = Path.cwd() / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    try:
        load_dotenv()
    except AssertionError:
        pass


class IPManager:
    """
    Manage IP addresses - track usage, success/failure rates.
    
    Schema:
    {
        "ip": str (unique),
        "number-of-usage": int,
        "number-of-successful-usage": int,
        "number-of-failed-usage": int,
        "created_at": datetime,
        "updated_at": datetime
    }
    """
    
    COLLECTION_NAME = "ips"
    
    def __init__(self):
        """Initialize the manager."""
        self._db_manager = DatabaseManager()
        self._collection = self._db_manager.get_collection(self.COLLECTION_NAME)
        
        # Ensure indexes exist
        self._ensure_indexes()
    
    # =========================================================================
    # PRIVATE METHODS
    # =========================================================================
    
    def _ensure_indexes(self) -> None:
        """Create necessary indexes on the collection."""
        if self._collection is not None:
            # Unique index on ip
            self._collection.create_index("ip", unique=True)
            # Index for sorting by usage
            self._collection.create_index("number-of-usage")
    
    def _create_document(self, ip: str, success: bool) -> Dict:
        """Create a new IP document."""
        now = datetime.now(timezone.utc)
        return {
            "ip": ip,
            "number-of-usage": 1,
            "number-of-successful-usage": 1 if success else 0,
            "number-of-failed-usage": 0 if success else 1,
            "created_at": now,
            "updated_at": now
        }
    
    # =========================================================================
    # CORE METHODS
    # =========================================================================
    
    def get_all_ips(
        self, 
        skip: int = 0, 
        limit: int = 0,
        sort_by: str = "number-of-usage",
        ascending: bool = False
    ) -> List[Dict]:
        """
        Get all IPs from the collection.
        
        Args:
            skip: Number of documents to skip
            limit: Maximum number of documents to return (0 = no limit)
            sort_by: Field to sort by
            ascending: Sort order (True = ascending, False = descending)
            
        Returns:
            List of IP documents
        """
        cursor = self._collection.find({})
        
        # Apply sorting
        sort_order = 1 if ascending else -1
        cursor = cursor.sort(sort_by, sort_order)
        
        # Apply pagination
        if skip > 0:
            cursor = cursor.skip(skip)
        if limit > 0:
            cursor = cursor.limit(limit)
        
        return list(cursor)
    
    def get_ips_list(
        self,
        skip: int = 0,
        limit: int = 0,
        sort_by: str = "number-of-usage",
        ascending: bool = False,
        level: int = 0
    ) -> List[str]:
        """
        Get a list of all IP addresses in the collection.
        
        Args:
            skip: Number of documents to skip
            limit: Maximum number of documents to return (0 = no limit)
            sort_by: Field to sort by
            ascending: Sort order (True = ascending, False = descending)
        
        Returns:
            List of IP addresses
        """
        try:
            ips = self.get_all_ips(skip=skip, limit=limit, sort_by=sort_by, ascending=ascending)
            return [ip["ip"] for ip in ips]
        except Exception as e:
            logger(f"Error getting IP list: {e}", level=level)
            return []
    
    def get_ip(self, ip: str) -> Optional[Dict]:
        """
        Get a specific IP document.
        
        Args:
            ip: The IP address to look up
            
        Returns:
            The document if found, None otherwise
        """
        return self._collection.find_one({"ip": ip})
    
    def ip_exists(self, ip: str) -> bool:
        """
        Check if an IP exists in the database.
        
        Args:
            ip: The IP address to check
            
        Returns:
            True if exists, False otherwise
        """
        return self._collection.find_one({"ip": ip}) is not None
    
    def add_ip_usage(self, ip: str, success: bool, level: int = 0) -> Optional[Dict]:
        """
        Add or update IP usage.
        
        - If IP doesn't exist -> creates a new document
        - If IP exists -> increments the usage counters
        - number-of-usage always increments by 1
        - If success=True -> increments number-of-successful-usage
        - If success=False -> increments number-of-failed-usage
        - Updates updated_at timestamp
        
        Args:
            ip: The IP address
            success: Whether the usage was successful
            
        Returns:
            The updated/created document
        """
        try:
            now = datetime.now(timezone.utc)
            
            # Build increment values based on success
            inc_values = {
                "number-of-usage": 1,
                "number-of-successful-usage": 1 if success else 0,
                "number-of-failed-usage": 0 if success else 1
            }
            
            # Use upsert with $inc and $setOnInsert for atomic operation
            result = self._collection.find_one_and_update(
                {"ip": ip},
                {
                    "$inc": inc_values,
                    "$set": {
                        "updated_at": now
                    },
                    "$setOnInsert": {
                        "ip": ip,
                        "created_at": now
                    }
                },
                upsert=True,
                return_document=ReturnDocument.AFTER
            )
            
            return result
        except Exception as e:
            logger(f"Error adding IP usage: {e}", level=level)
            return None
    
    def add_ip_success(self, ip: str) -> Optional[Dict]:
        """
        Shorthand for add_ip_usage with success=True.
        
        Args:
            ip: The IP address
            
        Returns:
            The updated/created document
        """
        return self.add_ip_usage(ip, success=True)
    
    def add_ip_failure(self, ip: str) -> Optional[Dict]:
        """
        Shorthand for add_ip_usage with success=False.
        
        Args:
            ip: The IP address
            
        Returns:
            The updated/created document
        """
        return self.add_ip_usage(ip, success=False)
    
    # =========================================================================
    # BULK OPERATIONS
    # =========================================================================
    
    def add_multiple_ips(self, ip_list: List[Dict[str, bool]]) -> Dict[str, int]:
        """
        Add multiple IPs with their success status.
        
        Args:
            ip_list: List of dicts with 'ip' and 'success' keys
                     Example: [{"ip": "1.2.3.4", "success": True}, ...]
            
        Returns:
            Dictionary with operation statistics
        """
        stats = {
            "total": len(ip_list),
            "processed": 0,
            "errors": 0
        }
        
        for item in ip_list:
            try:
                self.add_ip_usage(item["ip"], item["success"])
                stats["processed"] += 1
            except Exception as e:
                stats["errors"] += 1
                print(f"[Error] Failed to add IP {item.get('ip')}: {e}")
        
        return stats
    
    def import_from_json_file(self, file_path: str) -> Dict[str, int]:
        """
        Import IPs from a JSON file and reorganize duplicates.
        
        Args:
            file_path: Path to JSON file
            
        Returns:
            Dictionary with import statistics
        """
        stats = {
            "total_read": 0,
            "imported": 0,
            "errors": 0
        }
        
        path = Path(file_path)
        if not path.exists():
            print(f"[Error] File not found: {file_path}")
            return stats
        
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        stats["total_read"] = len(data)
        print(f"[Import] Read {len(data)} records from file")
        
        # Aggregate data by IP first
        aggregated = {}
        for item in data:
            ip = item.get("ip")
            if not ip:
                continue
            
            if ip not in aggregated:
                aggregated[ip] = {
                    "number-of-usage": 0,
                    "number-of-successful-usage": 0,
                    "number-of-failed-usage": 0
                }
            
            aggregated[ip]["number-of-usage"] += item.get("number-of-usage", 0)
            aggregated[ip]["number-of-successful-usage"] += item.get("number-of-successful-usage", 0)
            aggregated[ip]["number-of-failed-usage"] += item.get("number-of-failed-usage", 0)
        
        print(f"[Import] Aggregated to {len(aggregated)} unique IPs")
        
        # Insert/update each IP
        now = datetime.now(timezone.utc)
        for ip, counts in aggregated.items():
            try:
                self._collection.update_one(
                    {"ip": ip},
                    {
                        "$inc": {
                            "number-of-usage": counts["number-of-usage"],
                            "number-of-successful-usage": counts["number-of-successful-usage"],
                            "number-of-failed-usage": counts["number-of-failed-usage"]
                        },
                        "$set": {"updated_at": now},
                        "$setOnInsert": {"ip": ip, "created_at": now}
                    },
                    upsert=True
                )
                stats["imported"] += 1
            except Exception as e:
                stats["errors"] += 1
                print(f"[Error] Failed to import IP {ip}: {e}")
        
        print(f"[Import Complete] {json.dumps(stats, indent=2)}")
        return stats
    
    # =========================================================================
    # QUERY METHODS
    # =========================================================================
    
    def get_ips_by_usage(self, min_usage: int = 0, max_usage: int = None) -> List[Dict]:
        """
        Get IPs filtered by usage count.
        
        Args:
            min_usage: Minimum number of usages
            max_usage: Maximum number of usages (None = no limit)
            
        Returns:
            List of matching IP documents
        """
        query = {"number-of-usage": {"$gte": min_usage}}
        
        if max_usage is not None:
            query["number-of-usage"]["$lte"] = max_usage
        
        return list(self._collection.find(query).sort("number-of-usage", -1))
    
    def get_ips_with_failures(self) -> List[Dict]:
        """
        Get all IPs that have at least one failure.
        
        Returns:
            List of IP documents with failures
        """
        return list(
            self._collection.find({"number-of-failed-usage": {"$gt": 0}})
            .sort("number-of-failed-usage", -1)
        )
    
    def get_ips_with_only_failures(self) -> List[Dict]:
        """
        Get IPs that have only failures (no successes).
        
        Returns:
            List of IP documents with only failures
        """
        return list(
            self._collection.find({
                "number-of-successful-usage": 0,
                "number-of-failed-usage": {"$gt": 0}
            })
            .sort("number-of-failed-usage", -1)
        )
    
    def get_top_ips(self, 
                   limit: int = 10, 
                   sort_by: str = "number-of-usage") -> List[Dict]:
        """
        Get top IPs by a specific field.
        
        Args:
            limit: Number of IPs to return
            sort_by: Field to sort by (descending)
            
        Returns:
            List of top IP documents
        """
        return list(
            self._collection.find({})
            .sort(sort_by, -1)
            .limit(limit)
        )
    
    # =========================================================================
    # STATISTICS METHODS
    # =========================================================================
    
    def get_stats(self) -> Dict:
        """
        Get aggregate statistics about all IPs.
        
        Returns:
            Dictionary with aggregate statistics
        """
        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total_ips": {"$sum": 1},
                    "total_usage": {"$sum": "$number-of-usage"},
                    "total_successful": {"$sum": "$number-of-successful-usage"},
                    "total_failed": {"$sum": "$number-of-failed-usage"},
                    "avg_usage": {"$avg": "$number-of-usage"},
                    "max_usage": {"$max": "$number-of-usage"},
                    "min_usage": {"$min": "$number-of-usage"}
                }
            }
        ]
        
        result = list(self._collection.aggregate(pipeline))
        
        if result:
            stats = result[0]
            del stats["_id"]
            # Calculate success rate
            if stats["total_usage"] > 0:
                stats["success_rate"] = round(
                    (stats["total_successful"] / stats["total_usage"]) * 100, 2
                )
            else:
                stats["success_rate"] = 0.0
            return stats
        
        return {
            "total_ips": 0,
            "total_usage": 0,
            "total_successful": 0,
            "total_failed": 0,
            "avg_usage": 0,
            "max_usage": 0,
            "min_usage": 0,
            "success_rate": 0.0
        }
    
    def count_ips(self) -> int:
        """
        Count total number of IPs in the database.
        
        Returns:
            Number of IPs
        """
        return self._collection.count_documents({})
    
    def get_ip_success_rate(self, ip: str) -> Optional[float]:
        """
        Get success rate for a specific IP.
        
        Args:
            ip: The IP address
            
        Returns:
            Success rate as percentage (0-100), None if IP not found
        """
        doc = self.get_ip(ip)
        if not doc:
            return None
        
        total = doc.get("number-of-usage", 0)
        if total == 0:
            return 0.0
        
        successful = doc.get("number-of-successful-usage", 0)
        return round((successful / total) * 100, 2)


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    manager = IPManager()
    
    print("=" * 60)
    print("IP Manager - Example Usage")
    print("=" * 60)
    
    # 1. Add IP with success
    print("\n[1] Adding IP with success...")
    result = manager.add_ip_success("192.168.1.100")
    print(f"    Result: {result['ip']} - Usage: {result['number-of-usage']}, "
          f"Success: {result['number-of-successful-usage']}, "
          f"Failed: {result['number-of-failed-usage']}")
    
    # 2. Add IP with failure
    print("\n[2] Adding same IP with failure...")
    result = manager.add_ip_failure("192.168.1.100")
    print(f"    Result: {result['ip']} - Usage: {result['number-of-usage']}, "
          f"Success: {result['number-of-successful-usage']}, "
          f"Failed: {result['number-of-failed-usage']}")
    
    # 3. Add another IP
    print("\n[3] Adding new IP with success...")
    result = manager.add_ip_usage("10.0.0.1", success=True)
    print(f"    Result: {result['ip']} - Usage: {result['number-of-usage']}")
    
    # 4. Get all IPs
    print("\n[4] Getting all IPs...")
    all_ips = manager.get_all_ips()
    for ip_doc in all_ips:
        print(f"    - {ip_doc['ip']}: {ip_doc['number-of-usage']} usages")
    
    # 5. Get specific IP
    print("\n[5] Getting specific IP...")
    ip_doc = manager.get_ip("192.168.1.100")
    if ip_doc:
        print(f"    Found: {ip_doc['ip']}")
        print(f"    Success Rate: {manager.get_ip_success_rate('192.168.1.100')}%")
    
    # 6. Get statistics
    print("\n[6] Getting statistics...")
    stats = manager.get_stats()
    print(f"    Total IPs: {stats['total_ips']}")
    print(f"    Total Usage: {stats['total_usage']}")
    print(f"    Total Successful: {stats['total_successful']}")
    print(f"    Total Failed: {stats['total_failed']}")
    print(f"    Success Rate: {stats['success_rate']}%")
    
    # 7. Bulk add
    print("\n[7] Bulk adding IPs...")
    bulk_data = [
        {"ip": "8.8.8.8", "success": True},
        {"ip": "8.8.4.4", "success": True},
        {"ip": "1.1.1.1", "success": False},
    ]
    bulk_stats = manager.add_multiple_ips(bulk_data)
    print(f"    Processed: {bulk_stats['processed']}/{bulk_stats['total']}")
    
    # 8. Import from JSON file (if exists)
    # print("\n[8] Importing from JSON file...")
    # manager.import_from_json_file("ips.json")
    
    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)