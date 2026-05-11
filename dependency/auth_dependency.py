from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from services.auth_service import AuthService
from os import getenv
from typing import Optional

security = HTTPBearer(auto_error=False)

auth_service = AuthService(secret_key=getenv("SECRET_KEY", "afcf9154-6e9a-4ef9-9dcb-01d7ae5a7017"))

class AuthDependency:
    def __init__(self, auth_service: AuthService):
        self.auth_service = auth_service
    
    async def __call__(self, request: Request, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> dict:
        token = None
        
        # 1. Try Bearer Token
        if credentials:
            token = credentials.credentials
            
        # 2. Try Query Parameter (useful for downloads)
        if not token:
            token = request.query_params.get("token")
            
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication credentials missing"
            )
            
        payload = self.auth_service.verify_token(token)
        
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        
        return payload

auth_required = AuthDependency(auth_service)