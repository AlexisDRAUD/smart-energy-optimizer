from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    full_name: str
    is_active: bool
    roles: list[RoleRead]


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=12, max_length=128)
    role_names: list[str] = Field(min_length=1)