from typing import Optional
from fastapi import UploadFile, File
from src.core.schemas.base_schema import CustomModel


class UserInputField(CustomModel):
    first_name: Optional[str] = ''
    last_name: Optional[str] = ''
    address: Optional[str] = ''
    city: Optional[str] = ''
    state: Optional[str] = ''
    zip: Optional[str] = ''
    dob: Optional[str] = ''
    email: Optional[str] = ''
    cell_phone: Optional[str] = ''

    class Config:
        exclude_defaults = True
        from_attributes = True
        exclude_unset = True


class BuildingInputField(CustomModel):
    name: Optional[str] = ''
    access_token: Optional[str] = ''
    building_url: Optional[str] = ''

    class Config:
        exclude_defaults = True
        from_attributes = True
        exclude_unset = True


class BuildingUserInputField(CustomModel):
    username: str
    password: str
    display_name: Optional[str] = None
    local_access_only: Optional[bool] = False
    administrator: Optional[bool] = False

    class Config:
        exclude_defaults = True
        from_attributes = True
        exclude_unset = True


class BuildingUserUpdateField(CustomModel):
    group_ids: Optional[list[str]] = None
    display_name: Optional[str] = None
    user_name: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None
    profile_picture_url: Optional[str] = None

    local_access_only: Optional[bool] = False
    administrator: Optional[bool] = False
    user_id: Optional[str] = None

    class Config:
        exclude_defaults = True
        from_attributes = True
        exclude_unset = True