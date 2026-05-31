from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "cadproject"

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

documents_collection = db["documents"]
balloons_collection = db["balloons"]
