from services.settings_service import settings_service

class SettingsController:
    async def get_settings(self, current_user: dict):
        company_id = current_user.get("company_id")
        return await settings_service.get_settings(company_id)
    
    async def update_settings(self, current_user: dict, data: dict):
        company_id = current_user.get("company_id")
        return await settings_service.update_settings(company_id, data)

settings_controller = SettingsController()
