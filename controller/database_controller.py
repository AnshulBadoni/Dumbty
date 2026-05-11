from services.db_service import db_service

class DatabaseController:
    
    async def get_all_dbs(self, current_user: dict, page: int = 1, limit: int = 10):
        company_id = current_user.get("company_id")
        return await db_service.get_all_dbs(company_id, page, limit)
    
    async def get_db_config(self, db_id: str, current_user: dict):
        company_id = current_user.get("company_id")
        return await db_service.get_db_config(company_id, db_id)
    
    async def create_db_config(self, config, current_user: dict):
        user_id = current_user.get("user_id")
        company_id = current_user.get("company_id")
        # Convert Pydantic model to dict if needed
        config_data = config.dict() if hasattr(config, "dict") else config
        return await db_service.create_db_config(user_id, company_id, config_data)
        
    async def update_db_config(self, db_id: str, config, current_user: dict):
        user_id = current_user.get("user_id")
        company_id = current_user.get("company_id")
        # Convert Pydantic model to dict if needed
        config_data = config.dict() if hasattr(config, "dict") else config
        return await db_service.update_db_config(user_id, company_id, db_id, config_data)
    
    async def delete_db_config(self, config_id: str, current_user: dict):
        company_id = current_user.get("company_id")
        return await db_service.delete_db_config(company_id, config_id)

    async def get_metrics(self, current_user: dict):
        company_id = current_user.get("company_id")
        return await db_service.get_metrics(company_id)

    async def get_metrics_by_db(self, current_user: dict, db_id: str):
        company_id = current_user.get("company_id")
        return await db_service.get_metric_by_db(company_id, db_id)

database_controller = DatabaseController()