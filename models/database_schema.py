from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class DatabaseConfig(BaseModel):
    db_name: str
    db_type: str
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    database: Optional[str] = None
    backup_interval: int
    backup_interval_unit: Optional[str] = 'hours' # 'hours' or 'minutes'
    ssl: Optional[bool] = None
    auth_source: Optional[str] = None
    connection_string: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
