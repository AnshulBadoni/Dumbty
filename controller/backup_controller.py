from fastapi import HTTPException, status
from services.backup_service import backup_service
from services.audit_service import audit_service
from models.backup_schemas import TriggerBackupRequest

class BackupController:
    
    async def trigger_backup(self, user_id: str, company_id: str, db_id: str, backup_request: TriggerBackupRequest = None):
        """Trigger a manual backup for a database"""
        description = backup_request.description if backup_request else None
        
        backup = await backup_service.create_backup(user_id, company_id, db_id, description)
        
        if not backup or (isinstance(backup, dict) and backup.get("status") == "failed"):
            error_msg = backup.get("error") if backup and isinstance(backup, dict) else "Database configuration not found or backup failed"
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR if backup else status.HTTP_404_NOT_FOUND,
                detail=error_msg
            )
        
        return {
            "message": "Backup created successfully",
            "backup_id": backup["_id"],
            "filename": backup["filename"],
            "size": backup["size"]
        }

    async def get_backups(self, company_id: str, db_id: str, page: int = 1, limit: int = 10):
        return await backup_service.get_all_backups(company_id, db_id, page, limit)
    
    async def get_all_backups(self, company_id: str, page: int = 1, limit: int = 10):
        return await backup_service.get_all_backups(company_id, page=page, limit=limit)
    
    async def get_one_backup(self, company_id: str, backup_id: str):
        """Get details of a single backup"""
        backup = await backup_service.get_one_backup(company_id, backup_id)
        
        if not backup:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Backup not found"
            )
        
        return backup
    


    async def download_backup(self, user_id: str, company_id: str, backup_id: str):
        """Download a backup"""
        backup = await backup_service.get_one_backup(company_id, backup_id)
        
        if not backup:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Backup not found"
            )
        
        # Generate presigned URL
        from services.aws import aws_service
        from fastapi.responses import RedirectResponse
        
        s3_key = backup.get("s3_key")
        if not s3_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Backup file not found in S3"
            )
            
        download_url = aws_service.generate_presigned_url(s3_key)
        
        if not download_url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate download link"
            )
            
        # Log the download action
        await audit_service.log_action(
            user_id=user_id,
            company_id=company_id,
            action="backup_downloaded",
            target_id=backup_id,
            metadata={
                "filename": backup.get("filename"),
                "db_id": backup.get("db_id")
            }
        )
        
        return RedirectResponse(url=download_url)

    async def delete_all_backups(self, company_id: str, db_id: str):
        """Delete all backups for a database"""
        result = await backup_service.delete_all_backups(company_id, db_id)
        
        return {
            "message": f"Deleted {result['deleted_count']} backup(s)",
            "deleted_count": result["deleted_count"]
        }
    
    async def delete_one_backup(self, company_id: str, backup_id: str):
        """Delete a single backup"""
        deleted = await backup_service.delete_one_backup(company_id, backup_id)
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Backup not found"
            )
        
        return {"message": "Backup deleted successfully"}

backup_controller = BackupController()