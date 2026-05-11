from pymongo import AsyncMongoClient
from os import getenv

MONGO_URI = getenv("MONGO_URI", "mongodb://localhost:27017")
print(f"Connecting to MongoDB at: {MONGO_URI}")

client = AsyncMongoClient(MONGO_URI)

def get_database(db_name: str):
    return client[db_name]

def get_collection(db_name: str, collection_name: str):
    return client[db_name][collection_name]