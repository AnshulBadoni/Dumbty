from pymongo import AsyncMongoClient
from os import getenv
import logging

logger = logging.getLogger(__name__)

MONGO_URI = getenv("MONGO_URI", "mongodb://localhost:27017")
logger.info(f"Connecting to MongoDB at: {MONGO_URI.split('@')[-1]}") # Mask credentials if present

client = AsyncMongoClient(MONGO_URI)

def get_database(db_name: str):
    return client[db_name]

def get_collection(db_name: str, collection_name: str):
    return client[db_name][collection_name]