"""GitHub Username Manager - Filter, store, and manage GitHub usernames"""

import os
import time
import requests
import json
from typing import Optional, Dict, List
from enum import Enum
from pathlib import Path
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError, BulkWriteError
from datetime import datetime, timedelta, timezone

from utils import renew_tor
from config import TOR_PORT

# Import your DatabaseManager
from database import DatabaseManager


class UsernameStatus(str, Enum):
    """Status enum for GitHub usernames."""
    UNUSED = "unused"
    USED = "used"
    NOT_ACCEPTED = "not-accepted"


class GitHubUsernameManager:
    """
    Manage GitHub usernames - check availability, store in MongoDB, and handle usage.
    
    Schema:
    {
        "username": str (unique),
        "status": "unused" | "used" | "not-accepted",
        "in_use": bool,
        "locked_at": datetime | None,
        "used_by": str | None,
        "created_at": datetime,
        "updated_at": datetime
    }
    """
    
    COLLECTION_NAME = "github_usernames"
    
    def __init__(self, github_token: Optional[str] = None, use_tor: bool = False):
        """
        Initialize the manager.
        
        Args:
            github_token: GitHub API token for higher rate limits (optional).
                          Falls back to GITHUB_TOKEN env variable.
        """
        self._db_manager = DatabaseManager()
        self._collection = self._db_manager.get_collection(self.COLLECTION_NAME)
        self._use_tor = use_tor
        self._headers = {
            "Accept": "application/vnd.github+json"
        }
        self.proxies = {}

        if self._use_tor:
            self.proxies = {
                "http": f"socks5://127.0.0.1:{TOR_PORT}",
                "https": f"socks5://127.0.0.1:{TOR_PORT}"
            }
        
        # Ensure indexes exist
        self._ensure_indexes()
    
    # =========================================================================
    # PRIVATE METHODS
    # =========================================================================
    
    def _ensure_indexes(self) -> None:
        """Create necessary indexes on the collection."""
        if self._collection is not None:
            # Unique index on username
            self._collection.create_index("username", unique=True)
            # Compound index for efficient querying of available usernames
            self._collection.create_index([("status", 1), ("in_use", 1)])
            # Index for releasing stale locks
            self._collection.create_index([("in_use", 1), ("locked_at", 1)])
    
    def _check_exists_on_github(self, username: str) -> bool:
        """
        Check if a username exists on GitHub.
        
        Args:
            username: The username to check
            
        Returns:
            True if exists, False if available
        """
        url = f"https://api.github.com/users/{username}"

        for _ in range(3):
            try:
                response = requests.get(url, headers=self._headers, timeout=20, proxies=self.proxies)
                
                if response.status_code == 200:
                    return True  # Username exists
            
                if response.status_code == 404:
                    return False  # Username available
            
                if response.status_code == 403:
                    time.sleep(5)
                    if self._use_tor:
                        renew_tor()
                    continue
            
                response.raise_for_status()
            
            except requests.exceptions.RequestException as e:
                time.sleep(5)
                if self._use_tor:
                    renew_tor()
                continue
        
        return None
    
    def _create_document(self, username: str) -> Dict:
        """Create a new username document."""
        now = datetime.now(timezone.utc)
        return {
            "username": username,
            "status": UsernameStatus.UNUSED.value,
            "in_use": False,
            "locked_at": None,
            "used_by": None,
            "created_at": now,
            "updated_at": now
        }
    
    # =========================================================================
    # IMPORT METHODS
    # =========================================================================
    
    def import_from_file(
        self, 
        file_path: str, 
        check_github: bool = True,
        batch_size: int = 100,
        skip_duplicates: bool = True
    ) -> Dict[str, int]:
        """
        Import usernames from a text file, filter non-existing ones, and save to MongoDB.
        
        Args:
            file_path: Path to the text file containing usernames (one per line)
            check_github: Whether to check if usernames exist on GitHub
            batch_size: Number of usernames to insert at once
            skip_duplicates: Skip usernames already in database
            
        Returns:
            Dictionary with import statistics
        """
        stats = {
            "total_read": 0,
            "already_in_db": 0,
            "exists_on_github": 0,
            "error_checking_github": 0,
            "invalid_format": 0,
            "saved": 0,
            "errors": 0
        }
        
        path = Path(file_path)
        if not path.exists():
            print(f"File not found: {file_path}")
            return None
        
        # Read all usernames from file
        with open(path, "r", encoding="utf-8") as f:
            usernames = [line.strip() for line in f if line.strip()]
        
        stats["total_read"] = len(usernames)
        print(f"[Import] Read {len(usernames)} usernames from file")
        
        to_insert: List[Dict] = []
        
        for i, username in enumerate(usernames, 1):
            print(f"Processing username {i}/{len(usernames)}: {username}")

            # Validate username format
            if not self._is_valid_github_username(username):
                stats["invalid_format"] += 1
                print("\tInvalid format")
                continue
            
            # Check if already in database
            if skip_duplicates and self._collection.find_one({"username": username}):
                stats["already_in_db"] += 1
                print("\tAlready in database")
                continue
            
            # Check if exists on GitHub
            if check_github:
                username_exists_on_github = self._check_exists_on_github(username)
                if username_exists_on_github == True:
                    stats["exists_on_github"] += 1
                    print("\tExists on GitHub")
                    continue
                elif username_exists_on_github == None:
                    stats["error_checking_github"] += 1
                    print("\tError checking GitHub")
                    continue
            
            # Prepare document for insertion
            to_insert.append(self._create_document(username))
            print("\tAdded to insert list")
            
            # Batch insert
            if len(to_insert) >= batch_size:
                saved = self._batch_insert(to_insert)
                print(f"\tBatch inserted {saved} usernames")
                stats["saved"] += saved
                stats["errors"] += len(to_insert) - saved
                to_insert = []
        
        # Insert remaining documents
        if to_insert:
            saved = self._batch_insert(to_insert)
            print(f"\tBatch inserted {saved} usernames")
            stats["saved"] += saved
            stats["errors"] += len(to_insert) - saved
        
        print(f"\n[Import Complete] Stats:")
        print(json.dumps(stats, indent=4))
        return stats
    
    def _is_valid_github_username(self, username: str) -> bool:
        """
        Validate GitHub username format.
        
        Rules:
        - 1-39 characters
        - Alphanumeric or single hyphens
        - Cannot start/end with hyphen
        - No consecutive hyphens
        """
        if not username or len(username) > 39:
            return False
        
        if username.startswith("-") or username.endswith("-"):
            return False
        
        if "--" in username:
            return False
        
        for char in username:
            if not (char.isalnum() or char == "-"):
                return False
        
        return True
    
    def _batch_insert(self, documents: List[Dict]) -> int:
        """
        Insert documents in batch, handling duplicates gracefully.
        
        Returns:
            Number of successfully inserted documents
        """
        if not documents:
            return 0
        
        try:
            result = self._collection.insert_many(documents, ordered=False)
            return len(result.inserted_ids)
        except BulkWriteError as e:
            # Some succeeded, some failed (likely duplicates)
            return e.details.get("nInserted", 0)
        except Exception as e:
            print(f"[Error] Batch insert failed: {e}")
            return 0
    
    # =========================================================================
    # ACQUIRE / RELEASE METHODS
    # =========================================================================
    
    def acquire_username(self, used_by: str) -> Optional[Dict]:
        """
        Get an unused username and lock it for use.
        
        This atomically finds an unused username and locks it so no other
        process can acquire it.
        
        Args:
            used_by: Identifier of who/what is using this username
            
        Returns:
            The username document if found, None if no unused usernames available
            
        Example:
            doc = manager.acquire_username("worker-1")
            if doc:
                username = doc["username"]
                # use the username...
        """
        now = datetime.now(timezone.utc)
        
        result = self._collection.find_one_and_update(
            {
                "status": UsernameStatus.UNUSED.value,
                "in_use": False
            },
            {
                "$set": {
                    "in_use": True,
                    "locked_at": now,
                    "used_by": used_by,
                    "updated_at": now
                }
            },
            return_document=ReturnDocument.AFTER
        )
        
        return result
    
    def mark_as_used(self, username: str) -> bool:
        """
        Mark a username as successfully used and release the lock.
        
        Call this after successfully creating a GitHub account with the username.
        
        Args:
            username: The username to mark as used
            
        Returns:
            True if updated, False otherwise
        """
        result = self._collection.update_one(
            {"username": username},
            {
                "$set": {
                    "status": UsernameStatus.USED.value,
                    "in_use": False,
                    "locked_at": None,
                    "used_by": None,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        return result.modified_count > 0
    
    def mark_as_not_accepted(self, username: str) -> bool:
        """
        Mark a username as not accepted (rejected by GitHub) and release the lock.
        
        Call this if GitHub rejects the username (e.g., reserved, inappropriate).
        
        Args:
            username: The username to mark as not accepted
            
        Returns:
            True if updated, False otherwise
        """
        result = self._collection.update_one(
            {"username": username},
            {
                "$set": {
                    "status": UsernameStatus.NOT_ACCEPTED.value,
                    "in_use": False,
                    "locked_at": None,
                    "used_by": None,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        return result.modified_count > 0
    
    def release_username(self, username: str) -> bool:
        """
        Release a locked username without changing its status.
        
        Useful if you need to abort an operation without marking the username
        as used or not-accepted. The username returns to the pool.
        
        Args:
            username: The username to release
            
        Returns:
            True if updated, False otherwise
        """
        result = self._collection.update_one(
            {"username": username},
            {
                "$set": {
                    "in_use": False,
                    "locked_at": None,
                    "used_by": None,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        return result.modified_count > 0
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def release_stale_locks(self, max_age_minutes: int = 30) -> int:
        """
        Release usernames that have been locked for too long (stale locks).
        
        Useful for recovering from crashed workers that didn't release their locks.
        
        Args:
            max_age_minutes: Maximum age of a lock in minutes before considered stale
            
        Returns:
            Number of released locks
        """
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)
        
        result = self._collection.update_many(
            {
                "in_use": True,
                "locked_at": {"$lt": cutoff}
            },
            {
                "$set": {
                    "in_use": False,
                    "locked_at": None,
                    "used_by": None,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        if result.modified_count > 0:
            print(f"[Cleanup] Released {result.modified_count} stale locks")
        
        return result.modified_count
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get statistics about usernames in the database.
        
        Returns:
            Dictionary with counts by status and usage
        """
        pipeline = [
            {
                "$group": {
                    "_id": "$status",
                    "count": {"$sum": 1}
                }
            }
        ]
        
        status_counts = {
            doc["_id"]: doc["count"] 
            for doc in self._collection.aggregate(pipeline)
        }
        
        return {
            "total": self._collection.count_documents({}),
            "unused": status_counts.get(UsernameStatus.UNUSED.value, 0),
            "used": status_counts.get(UsernameStatus.USED.value, 0),
            "not_accepted": status_counts.get(UsernameStatus.NOT_ACCEPTED.value, 0),
            "currently_locked": self._collection.count_documents({"in_use": True})
        }
    
    def get_username_by_name(self, username: str) -> Optional[Dict]:
        """
        Get a username document by username.
        
        Args:
            username: The username to look up
            
        Returns:
            The document if found, None otherwise
        """
        return self._collection.find_one({"username": username})
    
    def count_available(self) -> int:
        """
        Count how many unused usernames are available (not locked).
        
        Returns:
            Number of available usernames
        """
        return self._collection.count_documents({
            "status": UsernameStatus.UNUSED.value,
            "in_use": False
        })


if __name__ == "__main__":
    manager = GitHubUsernameManager(use_tor=True)

    # # 1. Check GitHub availability
    # exists1 = manager._check_exists_on_github("za-zo")
    # print("1.exists:", exists1)
    # exists2 = manager._check_exists_on_github("zazo-lazazo")
    # print("2.exists:", exists2)

    # 2. Import usernames from file (checks GitHub availability)
    stats = manager.import_from_file(
        file_path="usernames.txt",
        check_github=True,
        batch_size=100
    )

    # # 3. Acquire, use, and release usernames
    # # Acquire a username
    # doc = manager.acquire_username(used_by="worker-1")

    # if doc:
    #     username = doc["username"]
    #     print(f"Acquired username: {username}")
        
    #     try:
    #         # Try to create GitHub account with this username
    #         success = create_github_account(username)  # Your function
            
    #         if success:
    #             manager.mark_as_used(username)
    #             print(f"Successfully used: {username}")
    #         else:
    #             manager.mark_as_not_accepted(username)
    #             print(f"Rejected: {username}")
                
    #     except Exception as e:
    #         # Something went wrong - release back to pool
    #         manager.release_username(username)
    #         print(f"Released {username} due to error: {e}")
    # else:
    #     print("No unused usernames available!")