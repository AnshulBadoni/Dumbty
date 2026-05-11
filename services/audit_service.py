from database.connection import get_collection
from datetime import datetime, timezone
from typing import Dict, Any

class AuditService:
    def __init__(self):
        self.collection = get_collection("dumpty", "audit_logs")
    
    async def log_action(self, user_id: str, company_id: str, action: str, target_id: str = None, metadata: Dict[str, Any] = None):
        """
        Log an action for audit purposes.
        :param user_id: ID of the user performing the action
        :param company_id: ID of the company
        :param action: Name of the action (e.g., 'backup_created', 'backup_downloaded')
        :param target_id: ID of the target object (e.g., backup_id or db_id)
        :param metadata: Additional context
        """
        log_entry = {
            "user_id": user_id,
            "company_id": company_id,
            "action": action,
            "target_id": target_id,
            "metadata": metadata or {},
            "timestamp": datetime.now(timezone.utc)
        }
        
        await self.collection.insert_one(log_entry)
        print(f"Audit Log: {action} by {user_id} for company {company_id}")

audit_service = AuditService()
