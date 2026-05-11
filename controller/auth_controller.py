from fastapi import HTTPException, status
from models.auth_schemas import RegisterUser, LoginUser

from dependency.auth_dependency import auth_service 

class AuthController:
    
    async def register(self, user_data: RegisterUser):
        existing_user = await auth_service.get_user_by_email(user_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        user_dict = user_data.model_dump()
        user_id = await auth_service.create_user(user_dict)
        
        token = auth_service.create_token(
            payload={"user_id": user_id, "email": user_data.email, "company_id": user_data.company_id, "name": user_data.name}
        )
        
        return {
            "message": "User registered successfully", 
            "access_token": token, 
            "token_type": "bearer"
        }

    async def login(self, login_data: LoginUser):
        user = await auth_service.get_user_by_email(login_data.email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        if not auth_service.verify_password(login_data.password, user["password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        token = auth_service.create_token(
            payload={"user_id": str(user["_id"]), "email": user["email"], "company_id": user.get("company_id"), "name": user.get("name")}
        )
        
        return {
            "message": "Login successful", 
            "access_token": token, 
            "token_type": "bearer"
        }

    async def update_profile(self, user_id: str, data: dict):
        # We only allow updating specific fields
        allowed_fields = ["name"]
        update_data = {k: v for k, v in data.items() if k in allowed_fields}
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid fields to update"
            )
            
        await auth_service.update_user(user_id, update_data)
        
        # Get updated user to issue fresh token
        from bson import ObjectId
        user = await auth_service.collection.find_one({"_id": ObjectId(user_id)})
        new_token = auth_service.create_token(
            payload={"user_id": user_id, "email": user["email"], "company_id": user.get("company_id"), "name": user.get("name")}
        )
        
        return {
            "message": "Profile updated successfully",
            "access_token": new_token
        }


auth_controller = AuthController()