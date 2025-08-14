from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, EmailStr, ConfigDict


# Base schemas
class UserBase(BaseModel):
    email: EmailStr
    phone_number: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    phone_number: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    profile_picture: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class User(UserBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    profile_picture: Optional[str] = None
    email_verified: bool = False
    phone_verified: bool = False
    is_active: bool = True
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class UserProfile(User):
    pass


# Address schemas
class AddressBase(BaseModel):
    label: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    province: str
    postal_code: str
    country: str = "Zimbabwe"
    phone: Optional[str] = None
    is_default: bool = False


class AddressCreate(AddressBase):
    pass


class AddressUpdate(BaseModel):
    label: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    is_default: Optional[bool] = None


class Address(AddressBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime


# Auth schemas
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    user_id: Optional[int] = None


# Notification schemas
class NotificationBase(BaseModel):
    type: str
    title: str
    message: str


class NotificationCreate(NotificationBase):
    user_id: int
    metadata: Optional[str] = None


class Notification(NotificationBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    is_read: bool = False
    # metadata: Optional[str] = None
    created_at: datetime