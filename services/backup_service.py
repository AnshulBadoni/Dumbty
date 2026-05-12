# services/backup_service.py
from database.connection import get_collection
from services.aws import aws_service
from services.audit_service import audit_service
from datetime import datetime, timezone
from bson import ObjectId
import subprocess
import os
import asyncio
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
        target_db = db_config.get("database") or db_config.get("db_name") or "all_databases"
        filename = f"{target_db}_{timestamp}.{extension}"
        filepath = os.path.join(self.backup_storage_path, filename)
        
        # Prepare environment (mostly for PGPASSWORD)
        env = os.environ.copy()
        
        try:
            dump_command = []
            use_stdout = True
            
            # Helper to get host without protocol
            raw_host = db_config.get('host', 'localhost')
            clean_host = raw_host
            if '://' in raw_host:
                clean_host = raw_host.split('://')[1].split('/')[0]
            elif '/' in raw_host:
                clean_host = raw_host.split('/')[0]
                
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
                    db_config.get('db_name') or db_config.get('database')
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
                        f"--dbname={db_config.get('db_name') or db_config.get('database')}",
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
                    
                    # Prioritize 'database' field for the actual target, fall back to 'db_name'
                    db_name = db_config.get('database') or db_config.get('db_name')
                    
                    # Construct options
                    options = [f"authSource={auth_source}"]
                    is_ssl = db_config.get("ssl") or db_config.get("tls")
                    if is_ssl:
                        options.append("tls=true")
                        # Also try adding it to the URI itself
                        options.append("tlsInsecure=true")
                        
                    options_str = "&".join(options)
                    
                    # Construct the base URI without the database path for better compatibility
                    uri = f"mongodb://{auth_part}{clean_host}:{db_config.get('port', 27017)}/?{options_str}"
                    
                    # Log URI for debugging (mask password)
                    masked_uri = uri.replace(password, "********") if 'password' in locals() else uri
                    print(f"DEBUG: SSL Detected: {is_ssl}")
                    print(f"Connecting to MongoDB at: {masked_uri}")
                    
                    dump_command = [
                        tool_name,
                        f"--uri={uri}",
                        f"--archive={filepath}",
                        "--gzip"
                    ]
                    
                    # Add insecure flags if SSL is enabled to handle self-signed certificates
                    if is_ssl:
                        # Try both modern and legacy flags
                        dump_command.append("--tlsInsecure")
                        # Note: We don't add both at once to avoid conflicts, 
                        # but we ensure the URI has it too.
                    
                    # If db_name is provided, target it explicitly
                    if db_name:
                        dump_command.append(f"--db={db_name}")
                    
                    # Support for specific collection backup
                    collection_name = db_config.get("collection_name")
                    if collection_name:
                        dump_command.append(f"--collection={collection_name}")
                        print(f"Targeting specific collection: {collection_name}")
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

            # Log the exact command (mask password in URI if present)
            masked_cmd = []
            for arg in dump_command:
                if "--uri=" in arg and 'password' in locals():
                    masked_cmd.append(arg.replace(password, "********"))
                else:
                    masked_cmd.append(arg)
            print(f"Executing Command: {' '.join(masked_cmd)}")

            # Execute command asynchronously to avoid blocking the event loop
            try:
                loop = asyncio.get_event_loop()
                async def run_backup_process(cmd):
                    if use_stdout:
                        def run_dump_to_file():
                            with open(filepath, 'w') as f:
                                return subprocess.run(cmd, env=env, stdout=f, stderr=subprocess.PIPE, text=True, check=True)
                        return await loop.run_in_executor(None, run_dump_to_file)
                    else:
                        return await loop.run_in_executor(
                            None, 
                            lambda: subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)
                        )

                try:
                    process_result = await run_backup_process(dump_command)
                except subprocess.CalledProcessError as e:
                    # SMART RETRY: If TLS failed, try one more time without TLS
                    if db_type == "mongodb" and ("EOF" in str(e.stderr) or "timeout" in str(e.stderr)) and "tls=true" in uri:
                        print("TLS connection failed (EOF). Retrying without TLS...")
                        # Strip TLS options from URI
                        new_uri = uri.replace("&tls=true", "").replace("tls=true&", "").replace("?tls=true", "?")
                        new_uri = new_uri.replace("&tlsInsecure=true", "").replace("tlsInsecure=true&", "").replace("?tlsInsecure=true", "?")
                        
                        retry_command = [arg for arg in dump_command if arg != "--tlsInsecure"]
                        for i, arg in enumerate(retry_command):
                            if arg.startswith("--uri="):
                                retry_command[i] = f"--uri={new_uri}"
                        
                        process_result = await run_backup_process(retry_command)
                    else:
                        raise e

                if process_result.stderr:
                    print(f"Backup Tool Output (stderr): {process_result.stderr}")
                    
            except (subprocess.CalledProcessError, Exception) as e:
                error_msg = getattr(e, 'stderr', str(e))
                print(f"Backup Failed: {error_msg}")
                
                # Save failure to database so it shows in UI history
                await self.backups_collection.insert_one({
                    "user_id": user_id,
                    "company_id": company_id,
                    "db_id": db_id,
                    "db_type": db_type,
                    "filename": filename,
                    "status": "failed",
                    "error": error_msg,
                    "size": 0,
                    "created_at": datetime.now(timezone.utc)
                })
                
                return {
                    "status": "failed", 
                    "error": f"Backup failed: {error_msg}"
                }
            
            # Get file size
            file_size = os.path.getsize(filepath)
            
            # Basic validation: flag backups that are suspiciously small
            is_empty_backup = False
            if db_type == "mongodb" and file_size < 200: # Empty mongodump --archive --gzip is ~116 bytes
                is_empty_backup = True
                print(f"WARNING: Backup file for {target_db} is very small ({file_size} bytes). It might be empty.")
            elif file_size < 100:
                is_empty_backup = True
                print(f"WARNING: Backup file for {target_db} is very small ({file_size} bytes).")
            
            # S3 Upload and metadata logic
            try:
                # S3 Upload logic - Run in executor to avoid blocking the event loop
                s3_key = f"dumpty/backups/{company_id}/{db_id}/{filename}"
                s3_url = await loop.run_in_executor(None, lambda: aws_service.upload_file(filepath, s3_key))
                
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
                    "status": "completed" if not is_empty_backup else "warning_empty",
                    "is_empty": is_empty_backup,
                    "created_at": datetime.now(timezone.utc)
                }
                
                if s3_url:
                    backup_doc["status"] = "completed" if not is_empty_backup else "warning_empty"
                else:
                    backup_doc["status"] = "completed_local_only"
                
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
                        print(f"Failed to cleanup local backup file: {e}")
                
                # Enforce retention policy (keep last 7)
                await self._enforce_retention(company_id, db_id, limit=7)

                return backup_doc
            except Exception as e:
                print(f"Post-backup processing failed: {str(e)}")
                # Even if S3/Audit fails, we have the file locally if use_stdout or pg_dump worked
                return {
                    "status": "failed",
                    "error": f"Backup completed but processing failed: {str(e)}",
                    "filename": filename
                }
            
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