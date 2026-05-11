from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class BackupResponse(BaseModel):
    backup_id: str
    db_id: str
    filename: str
    size: int
    created_at: datetime
    status: str

class TriggerBackupRequest(BaseModel):
    description: Optional[str] = None