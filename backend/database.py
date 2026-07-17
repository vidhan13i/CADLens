import os
from motor.motor_asyncio import AsyncIOMotorClient

# Check for the MONGODB_URL environment variable provided by Docker.
# If it's not found, fall back to localhost for local development.
MONGO_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DB_NAME = "cadproject"

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

documents_collection = db["documents"]
balloons_collection = db["balloons"]
