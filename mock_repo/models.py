from pydantic import BaseModel, EmailStr

model_config = ConfigDict(from_attributes=True)

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    username: str

class UserOut(BaseModel):
    id: int
    email: EmailStr
    username: str