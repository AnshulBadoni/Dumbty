from fastapi import APIRouter, Depends
from dependency.auth_dependency import auth_required
from controller.settings_controller import settings_controller

settings_router = APIRouter(prefix="/settings", tags=["Settings"])

@settings_router.get("/")
async def get_settings(current_user: dict = Depends(auth_required)):
    return await settings_controller.get_settings(current_user)

@settings_router.post("/")
async def update_settings(data: dict, current_user: dict = Depends(auth_required)):
    return await settings_controller.update_settings(current_user, data)
