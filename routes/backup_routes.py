from fastapi import APIRouter, Depends
from controller.backup_controller import backup_controller
from dependency.auth_dependency import auth_required

backup_router = APIRouter(prefix="/backup", tags=["Backup"])

@backup_router.post("/{db_id}/backup")
async def trigger_backup(db_id: str, user=Depends(auth_required)):
    return await backup_controller.trigger_backup(user["user_id"], user.get("company_id"), db_id)

@backup_router.get("/{db_id}/backups")
async def get_backups(db_id: str, page: int = 1, limit: int = 10, user=Depends(auth_required)):
    return await backup_controller.get_backups(user.get("company_id"), db_id, page, limit)

@backup_router.get("/all")
async def get_all_backups(page: int = 1, limit: int = 10, user=Depends(auth_required)):
    return await backup_controller.get_all_backups(user.get("company_id"), page, limit)

@backup_router.get("/{backup_id}")  
async def get_one_backup(backup_id: str, user=Depends(auth_required)):
    return await backup_controller.get_one_backup(user.get("company_id"), backup_id)

@backup_router.get("/{backup_id}/download")
async def download_backup(backup_id: str, user=Depends(auth_required)):
    return await backup_controller.download_backup(user["user_id"], user.get("company_id"), backup_id)

@backup_router.delete("/{db_id}/backups")
async def delete_all_backups(db_id: str, user=Depends(auth_required)):
    return await backup_controller.delete_all_backups(user.get("company_id"), db_id)

@backup_router.delete("/{backup_id}")
async def delete_one_backup(backup_id: str, user=Depends(auth_required)):
    return await backup_controller.delete_one_backup(user.get("company_id"), backup_id)