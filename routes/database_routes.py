# routes/database_routes.py
from fastapi import APIRouter, Depends
from controller.database_controller import database_controller
from controller.backup_controller import backup_controller
from dependency.auth_dependency import auth_required
from models.backup_schemas import TriggerBackupRequest
from models.database_schema import DatabaseConfig

db_router = APIRouter(prefix="/db", tags=["Database"])

# Database config routes
@db_router.get("/")
async def get_all_dbs(page: int = 1, limit: int = 10, user: dict = Depends(auth_required)):
    return await database_controller.get_all_dbs(user, page, limit)

# Metrics routes
@db_router.get("/metrics")
async def get_metrics(user: dict = Depends(auth_required)):
    return await database_controller.get_metrics(user)

@db_router.get("/metrics/{db_id}")
async def get_metrics_by_db(db_id: str, user: dict = Depends(auth_required)):
    return await database_controller.get_metrics_by_db(user, db_id)

@db_router.get("/{db_id}")
async def get_db_config(db_id: str, user: dict = Depends(auth_required)):
    return await database_controller.get_db_config(db_id, user)

@db_router.post("/")
async def create_db_config(config: DatabaseConfig, user: dict = Depends(auth_required)):
    return await database_controller.create_db_config(config, user)

@db_router.put("/{db_id}")
async def update_db_config(db_id: str, config: DatabaseConfig, user: dict = Depends(auth_required)):
    return await database_controller.update_db_config(db_id, config, user)

@db_router.delete("/{db_id}")
async def delete_db(db_id: str, user: dict = Depends(auth_required)):
    return await database_controller.delete_db_config(db_id, user)

# Backup routes
@db_router.post("/{db_id}/backup")
async def trigger_backup(
    db_id: str, 
    backup_request: TriggerBackupRequest = None,
    user: dict = Depends(auth_required)
):
    """Trigger a manual backup for a specific database"""
    return await backup_controller.trigger_backup(user["user_id"], user.get("company_id"), db_id, backup_request)

@db_router.get("/{db_id}/backups")
async def get_backups(db_id: str, page: int = 1, limit: int = 10, user: dict = Depends(auth_required)):
    """Get all backups for a specific database with pagination"""
    return await backup_controller.get_backups(user.get("company_id"), db_id, page, limit)

@db_router.delete("/{db_id}/backups")
async def delete_all_backups(db_id: str, user: dict = Depends(auth_required)):
    """Delete all backups for a specific database"""
    return await backup_controller.delete_all_backups(user.get("company_id"), db_id)

@db_router.get("/backups/{backup_id}")
async def get_one_backup(backup_id: str, user: dict = Depends(auth_required)):
    """Get details of a single backup"""
    return await backup_controller.get_one_backup(user.get("company_id"), backup_id)

@db_router.delete("/backups/{backup_id}")
async def delete_one_backup(backup_id: str, user: dict = Depends(auth_required)):
    """Delete a single backup"""
    return await backup_controller.delete_one_backup(user.get("company_id"), backup_id)
