from pydantic import BaseModel, EmailStr

class RegisterUser(BaseModel):
    name: str
    email: EmailStr
    password: str
    company_id: str

class LoginUser(BaseModel):
    email: EmailStr
    password: str