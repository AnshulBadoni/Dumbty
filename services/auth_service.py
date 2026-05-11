from jose import jwt, JWTError 
from datetime import datetime, timedelta
import bcrypt
from database.connection import get_collection

class AuthService:
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
        self.algorithm = "HS256"
        self.collection = get_collection("dumpty", "users")
    
    def hash_password(self, password: str) -> str:
        # Bcrypt has a 72-byte limit. We encode and truncate.
        # Truncating to 72 characters is usually enough for standard passwords.
        # If we need to support longer passwords securely, we should pre-hash them.
        password_bytes = password[:72].encode('utf-8')
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode('utf-8')
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        password_bytes = plain_password[:72].encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    
    def create_token(self, payload: dict, expires_delta: timedelta = timedelta(hours=24)) -> str:
        to_encode = payload.copy()
        expire = datetime.utcnow() + expires_delta
        to_encode.update({"exp": expire})
        
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str) -> dict:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError:
            return None

    async def get_user_by_email(self, email: str):
        return await self.collection.find_one({"email": email})
    
    async def create_user(self, user_data: dict):
        user_data["password"] = self.hash_password(user_data["password"])
        user_data["created_at"] = datetime.utcnow()
        result = await self.collection.insert_one(user_data)
        return str(result.inserted_id)

    async def update_user(self, user_id: str, data: dict):
        from bson import ObjectId
        await self.collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": data}
        )