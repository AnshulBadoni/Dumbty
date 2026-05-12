from database.connection import get_collection
from datetime import datetime, timezone

class DBService:
    def __init__(self):
        self.collection = get_collection("dumpty", "database_configs")
        self.backups_collection = get_collection("dumpty", "backups")
    
    async def get_all_dbs(self, company_id: str, page: int = 1, limit: int = 10):
        """Get all database configs for a company with pagination"""
        skip = (page - 1) * limit
        
        # Get total count
        total_count = await self.collection.count_documents({"company_id": company_id})
        
        configs = await self.collection.find({"company_id": company_id}).skip(skip).limit(limit).to_list(length=limit)
        
        # We still need all backups to calculate storage/counts if we want accuracy across pages, 
        # or we can just fetch all backups for this company once.
        # For now, let's keep the logic of fetching backups to calculate these fields.
        backups = await self.backups_collection.find({"company_id": company_id}).to_list(length=1000)
        
        for config in configs:
            config["_id"] = str(config["_id"])
            config["total_storage"] = 0
            config["total_backups"] = 0
            config["status_history"] = []
            
            # Filter and sort backups for this specific DB
            db_backups = [b for b in backups if b["db_id"] == config["_id"]]
            db_backups.sort(key=lambda x: x.get("created_at", datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
            
            # Take last 30 for history
            for b in db_backups[:30]:
                status = b.get("status", "failed")
                if status in ["completed", "success"]:
                    config["status_history"].append("success")
                elif status in ["warning_empty", "completed_local_only"]:
                    config["status_history"].append("warning")
                else:
                    config["status_history"].append("failed")
                
                config["total_storage"] += b.get("size", 0)
                config["total_backups"] += 1
            
            # The UI expects history to be chronological (oldest to newest)
            config["status_history"].reverse()
            print(f"DEBUG: DB {config['db_name']} has {len(config['status_history'])} history points")
        
        return {
            "databases": configs, 
            "total_count": total_count,
            "page": page,
            "limit": limit,
            "total_pages": (total_count + limit - 1) // limit
        }
    
    async def get_db_config(self, company_id: str, config_id: str):
        """Get a single database config"""
        from bson import ObjectId
        config = await self.collection.find_one({
            "_id": ObjectId(config_id),
            "company_id": company_id
        })
        backups = await self.backups_collection.find({
            "db_id": config_id,
            "company_id": company_id
        }).to_list(length=100)
        # total storage of its backup
        total_storage = 0
        status_history = []
        
        # Sort backups by date
        backups.sort(key=lambda x: x.get("created_at", datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
        
        for backup in backups:
            total_storage += backup.get("size", 0)
        
        # Last 30 for history
        for b in backups[:30]:
            status = b.get("status", "failed")
            if status in ["completed", "success"]:
                status_history.append("success")
            elif status in ["warning_empty", "completed_local_only"]:
                status_history.append("warning")
            else:
                status_history.append("failed")
        
        status_history.reverse()

        if config:
            config["_id"] = str(config["_id"])
            config["total_storage"] = total_storage
            config["total_backups"] = len(backups)
            config["status_history"] = status_history
        return config
    
    async def create_db_config(self, user_id: str, company_id: str, config: dict):
        """Save a new database config"""
        config["user_id"] = user_id
        config["company_id"] = company_id
        config["created_at"] = datetime.now(timezone.utc)
        config["updated_at"] = datetime.now(timezone.utc)
        result = await self.collection.insert_one(config)
        return {"id": str(result.inserted_id), "message": "Config saved"}

    async def update_db_config(self, user_id: str, company_id: str, db_id: str, config: dict):
        """Update a database config"""
        from bson import ObjectId
        print(f"DIAGNOSTIC: Received update for DB {db_id}: {config}")
        # Remove _id if present in config to avoid trying to update immutable field
        config.pop("_id", None)
        config.pop("id", None)
        
        result = await self.collection.update_one({
            "_id": ObjectId(db_id),
            "company_id": company_id
        }, {"$set": config})
        return {"updated": result.modified_count > 0}
    
    async def delete_db_config(self, company_id: str, config_id: str):
        """Delete a database config"""
        from bson import ObjectId
        result = await self.collection.delete_one({
            "_id": ObjectId(config_id),
            "company_id": company_id
        })
        return {"deleted": result.deleted_count > 0}

    async def get_metrics(self, company_id: str):
        """Get metrics for a company"""
        configs = await self.collection.find({"company_id": company_id}).to_list(length=100)
        backups = await self.backups_collection.find({"company_id": company_id}).to_list(length=100)
        total_dbs = len(configs)
        total_backups = len(backups)
        total_size = 0
        for backup in backups:
            total_size += backup.get("size", 0)
        print("metrics", {"total_dbs": total_dbs, "total_backups": total_backups, "total_size": total_size})
        return {"total_dbs": total_dbs, "total_backups": total_backups, "total_size": total_size}

    async def get_metric_by_db(self, company_id: str, db_id: str):
        """Get metrics for a specific database"""
        backups = await self.backups_collection.find({"company_id": company_id, "db_id": db_id}).to_list(length=100)
        total_backups = len(backups)
        total_size = 0
        for backup in backups:
            total_size += backup.get("size", 0)
        return {"total_backups": total_backups, "total_size": total_size}

db_service = DBService()
