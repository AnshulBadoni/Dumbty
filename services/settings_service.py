from database.connection import get_collection
from datetime import datetime, timezone

class SettingsService:
    def __init__(self):
        self.collection = get_collection("dumpty", "settings")
    
    async def get_settings(self, company_id: str):
        """Get settings for a company"""
        settings = await self.collection.find_one({"company_id": company_id})
        if not settings:
            # Default settings
            return {
                "company_id": company_id,
                "backup_success": False,
                "backup_failed": True
            }
        
        # Cleanup internal ID
        settings["_id"] = str(settings["_id"])
        return settings
    
    async def update_settings(self, company_id: str, data: dict):
        """Update or create settings for a company"""
        # Ensure company_id is set
        data["company_id"] = company_id
        data["updated_at"] = datetime.now(timezone.utc)
        
        # Remove _id if present
        data.pop("_id", None)
        
        result = await self.collection.update_one(
            {"company_id": company_id},
            {"$set": data},
            upsert=True
        )
        return {"updated": True}

settings_service = SettingsService()
