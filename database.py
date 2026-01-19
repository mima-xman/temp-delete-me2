"""Centralized MongoDB Database Manager (Singleton)"""

import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()


class DatabaseManager:
    """Singleton MongoDB connection manager."""
    
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize MongoDB connection."""
        mongodb_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
        db_name = os.getenv('DB_NAME', 'github_accounts_manager')

        try:
            self._client = MongoClient(mongodb_uri)
            self._db = self._client[db_name]
            print(f"✅ DatabaseManager connected to {db_name}")
        except Exception as e:
            print(f"❌ DatabaseManager Error: {e}")
            self._client = None
            self._db = None

    @property
    def db(self):
        """Get database, reconnecting if needed."""
        if self._db is None:
            self._initialize()
        return self._db

    def get_collection(self, name):
        """Get a collection by name."""
        return self.db[name] if self.db is not None else None

    def close(self):
        """Close the connection."""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None