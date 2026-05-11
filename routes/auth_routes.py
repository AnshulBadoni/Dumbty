from fastapi import APIRouter
from models.auth_schemas import RegisterUser, LoginUser
from controller.auth_controller import auth_controller

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])

@auth_router.post("/register", status_code=201)
async def register_user(user: RegisterUser):
    """ Register a new user. """
    return await auth_controller.register(user)

@auth_router.post("/login", status_code=200)
async def login_user(credentials: LoginUser):
    """ Login and receive a JWT Bearer token. """
    return await auth_controller.login(credentials)

from dependency.auth_dependency import auth_required
from fastapi import Depends

@auth_router.put("/profile")
async def update_profile(data: dict, current_user: dict = Depends(auth_required)):
    """ Update the current user's profile. """
    return await auth_controller.update_profile(current_user["user_id"], data)