# services/backup_service.py
from database.connection import get_collection
from services.aws import aws_service
from services.audit_service import audit_service
from datetime import datetime, timezone
from bson import ObjectId
import subprocess
import os
from typing import List, Dict

class BackupService:
    def __init__(self):
        self.db_configs_collection = get_collection("dumpty", "database_configs")
        self.backups_collection = get_collection("dumpty", "backups")
        self.backup_storage_path = os.getenv("BACKUP_STORAGE_PATH", "./backups")
        
        os.makedirs(self.backup_storage_path, exist_ok=True)
    
    async def get_db_config(self, company_id: str, db_id: str):
        """Get database configuration for a specific company"""
        return await self.db_configs_collection.find_one({
            "_id": ObjectId(db_id),
            "company_id": company_id
        })
    
    async def create_backup(self, user_id: str, company_id: str, db_id: str, description: str = None):
        """Create a new backup for a database"""
        # Get database config
        db_config = await self.get_db_config(company_id, db_id)
        if not db_config:
            return None
        
        # Determine database type and filename extension
        db_type = db_config.get("db_type", "mysql").lower()
        extension = "sql"
        if db_type == "mongodb":
            extension = "gz"
            
        # Generate backup filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        db_name = db_config.get("db_name", "unknown")
        filename = f"{db_name}_{timestamp}.{extension}"
        filepath = os.path.join(self.backup_storage_path, filename)
        
        # Prepare environment (mostly for PGPASSWORD)
        env = os.environ.copy()
        
        try:
            dump_command = []
            use_stdout = True
            
            # Helper to get host without protocol
            raw_host = db_config.get('host', 'localhost')
            clean_host = raw_host.replace('mongodb://', '').replace('postgresql://', '').replace('postgres://', '').split('/')[0]
            if '@' in clean_host:
                clean_host = clean_host.split('@')[1]

            # Determine the base executable name
            tool_name = ""
            if db_type == "mysql":
                tool_name = "mysqldump"
                dump_command = [
                    tool_name,
                    f"--host={clean_host}",
                    f"--port={db_config.get('port', 3306)}",
                    f"--user={db_config.get('username')}",
                    f"--password={db_config.get('password')}",
                    db_config.get('db_name')
                ]
            elif db_type in ["postgres", "postgresql"]:
                tool_name = "pg_dump"
                # Priority 1: Use full connection string if available
                if db_config.get("connection_string"):
                    dump_command = [
                        tool_name,
                        db_config["connection_string"],
                        "-f", filepath,
                        "--no-owner",
                        "--no-acl"
                    ]
                else:
                    dump_command = [
                        tool_name,
                        f"--host={clean_host}",
                        f"--port={db_config.get('port', 5432)}",
                        f"--username={db_config.get('username')}",
                        f"--dbname={db_config.get('db_name')}",
                        "-f", filepath
                    ]
                    env["PGPASSWORD"] = db_config.get('password')
                use_stdout = False
            elif db_type == "mongodb":
                tool_name = "mongodump"
                from urllib.parse import quote_plus
                
                # Priority 1: Use full connection string if available (critical for Atlas/SRV)
                if db_config.get("connection_string"):
                    dump_command = [
                        tool_name,
                        f"--uri={db_config['connection_string']}",
                        f"--archive={filepath}",
                        "--gzip"
                    ]
                else:
                    # Construct URI from parts
                    auth_part = ""
                    if db_config.get("username") and db_config.get("password"):
                        username = quote_plus(db_config['username'])
                        password = quote_plus(db_config['password'])
                        auth_part = f"{username}:{password}@"
                    
                    # Default authSource to admin if not specified (common for MongoDB)
                    auth_source = db_config.get("auth_source") or "admin"
                    uri = f"mongodb://{auth_part}{clean_host}:{db_config.get('port', 27017)}/{db_config.get('db_name')}?authSource={auth_source}"
                    
                    # Log URI for debugging (mask password)
                    masked_uri = uri.replace(password, "********") if 'password' in locals() else uri
                    print(f"Connecting to MongoDB at: {masked_uri}")
                    
                    dump_command = [
                        tool_name,
                        f"--uri={uri}",
                        f"--archive={filepath}",
                        "--gzip"
                    ]
                use_stdout = False
            else:
                return {"status": "failed", "error": f"Unsupported database type: {db_type}"}

            # On Windows, try to find the tool in common locations if not in PATH
            if os.name == 'nt':
                import shutil
                if not shutil.which(tool_name):
                    common_paths = []
                    if db_type == "mongodb":
                        common_paths = [
                            r"C:\Program Files\MongoDB\Tools\100\bin\mongodump.exe",
                            r"C:\Program Files\MongoDB\Server\current\bin\mongodump.exe"
                        ]
                    elif db_type == "mysql":
                        common_paths = [
                            r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe",
                            r"C:\xampp\mysql\bin\mysqldump.exe"
                        ]
                    elif db_type in ["postgres", "postgresql"]:
                        common_paths = [
                            r"C:\Program Files\PostgreSQL\16\bin\pg_dump.exe",
                            r"C:\Program Files\PostgreSQL\15\bin\pg_dump.exe"
                        ]
                    
                    for path in common_paths:
                        if os.path.exists(path):
                            dump_command[0] = path
                            break

            # Execute command
            try:
                if use_stdout:
                    with open(filepath, 'w') as f:
                        subprocess.run(dump_command, env=env, stdout=f, check=True)
                else:
                    subprocess.run(dump_command, env=env, check=True)
            except FileNotFoundError:
                return {
                    "status": "failed", 
                    "error": f"Backup tool '{tool_name}' not found. Please ensure it is installed and in your system PATH."
                }
            
            # Get file size
            file_size = os.path.getsize(filepath)
            
            # S3 Upload logic
            s3_key = f"dumpty/backups/{company_id}/{db_id}/{filename}"
            s3_url = aws_service.upload_file(filepath, s3_key)
            
            # Save backup metadata to database
            backup_doc = {
                "user_id": user_id,
                "company_id": company_id,
                "db_id": db_id,
                "db_type": db_type,
                "filename": filename,
                "s3_key": s3_key,
                "s3_url": s3_url,
                "storage_type": "s3" if s3_url else "local",
                "size": file_size,
                "description": description,
                "status": "completed" if s3_url else "completed_local_only",
                "created_at": datetime.now(timezone.utc)
            }
            
            result = await self.backups_collection.insert_one(backup_doc)
            backup_id = str(result.inserted_id)
            backup_doc["_id"] = backup_id
            
            # Log the action
            await audit_service.log_action(
                user_id=user_id,
                company_id=company_id,
                action="backup_created",
                target_id=backup_id,
                metadata={
                    "filename": filename,
                    "db_id": db_id,
                    "size": file_size,
                    "storage_type": backup_doc["storage_type"]
                }
            )
            
            # Cleanup local file if S3 upload was successful
            if s3_url and os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    backup_doc["local_cleaned"] = True
                except Exception as e:
                    logger.error(f"Failed to cleanup local backup file: {e}")
            
            # Enforce retention policy (keep last 7)
            await self._enforce_retention(company_id, db_id, limit=7)

            return backup_doc
            
        except subprocess.CalledProcessError as e:
            # Handle backup execution failure
            error_msg = f"Backup failed with exit code {e.returncode}"
            backup_doc = {
                "user_id": user_id,
                "company_id": company_id,
                "db_id": db_id,
                "filename": filename,
                "status": "failed",
                "error": error_msg,
                "created_at": datetime.now(timezone.utc)
            }
            await self.backups_collection.insert_one(backup_doc)
            return {"status": "failed", "error": error_msg}
        except Exception as e:
            # Handle other unexpected errors
            return {"status": "failed", "error": str(e)}



    
    async def get_all_backups(self, company_id: str, db_id: str = None, page: int = 1, limit: int = 10):
        """Get all backups for a specific database or all databases for a company with pagination"""
        skip = (page - 1) * limit
        query = {"company_id": company_id}
        if db_id:
            query["db_id"] = db_id
            
        # Get total count
        total_count = await self.backups_collection.count_documents(query)
            
        backups = await self.backups_collection.find(query).sort("created_at", -1).skip(skip).limit(limit).to_list(length=limit)
        
        # Convert ObjectId to string
        for backup in backups:
            backup["_id"] = str(backup["_id"])
        
        return {
            "backups": backups,
            "total_count": total_count,
            "page": page,
            "limit": limit,
            "total_pages": (total_count + limit - 1) // limit
        }
    
    async def get_one_backup(self, company_id: str, backup_id: str):
        """Get a single backup by ID"""
        backup = await self.backups_collection.find_one({
            "_id": ObjectId(backup_id),
            "company_id": company_id
        })
        
        if backup:
            backup["_id"] = str(backup["_id"])
        
        return backup
    
    async def delete_all_backups(self, company_id: str, db_id: str):
        """Delete all backups for a database"""
        # Get all backups to delete files
        backups = await self.backups_collection.find({
            "company_id": company_id,
            "db_id": db_id
        }).to_list(length=1000)
        
        # Delete physical files
        for backup in backups:
            # Delete from S3
            s3_key = backup.get("s3_key")
            if s3_key:
                aws_service.delete_file(s3_key)
            
            # Delete local file if it exists (legacy or cleanup failure)
            filepath = backup.get("filepath")
            if filepath and os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except OSError:
                    pass  # File already deleted or permission issue
        
        # Delete from database
        result = await self.backups_collection.delete_many({
            "company_id": company_id,
            "db_id": db_id
        })
        
        return {"deleted_count": result.deleted_count}
    
    async def delete_one_backup(self, company_id: str, backup_id: str):
        """Delete a single backup"""
        # Get backup to delete file
        backup = await self.backups_collection.find_one({
            "_id": ObjectId(backup_id),
            "company_id": company_id
        })
        
        if not backup:
            return False
        
        # Delete from S3
        s3_key = backup.get("s3_key")
        if s3_key:
            aws_service.delete_file(s3_key)
            
        # Delete special physical file if it exists locally
        filepath = backup.get("filepath")
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except OSError:
                pass
        
        # Delete from database
        result = await self.backups_collection.delete_one({
            "_id": ObjectId(backup_id),
            "company_id": company_id
        })
        
        return result.deleted_count > 0

    async def _enforce_retention(self, company_id: str, db_id: str, limit: int = 7):
        """Keep only the latest N backups and delete older ones"""
        try:
            # Get all successful backups for this DB, sorted by date (newest first)
            backups = await self.backups_collection.find({
                "company_id": company_id,
                "db_id": db_id,
                "status": {"$in": ["completed", "completed_local_only", "success"]}
            }).sort("created_at", -1).to_list(length=100)

            if len(backups) > limit:
                # Excess backups (the oldest ones)
                to_delete = backups[limit:]
                print(f"Retention: Deleting {len(to_delete)} old backups for DB {db_id}")
                
                for backup in to_delete:
                    # Delete from S3
                    s3_key = backup.get("s3_key")
                    if s3_key:
                        aws_service.delete_file(s3_key)
                    
                    # Delete from DB
                    await self.backups_collection.delete_one({"_id": backup["_id"]})
        except Exception as e:
            print(f"Retention policy error: {e}")

backup_service = BackupService()