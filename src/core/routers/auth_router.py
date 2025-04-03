from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, Request, Path, HTTPException, UploadFile, File, Form
from src.core.ha_websocket.main import HomeAssistantWS
from src.core.models.building import Building
from src.database import yield_db_session
from src.exceptions import BadRequest, NotFound
from src.responses import success
from src.logger import get_logger
from src.core.schemas.user_schema import BuildingInputField,BuildingUserInputField,BuildingUserUpdateField
import os
import uuid
from pathlib import Path as PathLib
from typing import Optional
from urllib.parse import urljoin

logger = get_logger(__name__)

router = APIRouter()

# Ensure the profile pictures directory exists
PROFILE_PICTURES_DIR = PathLib("static/profile_pictures")
PROFILE_PICTURES_DIR.mkdir(parents=True, exist_ok=True)

async def save_profile_picture(file: UploadFile, base_url: str) -> str:
    # Generate a unique filename
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = PROFILE_PICTURES_DIR / unique_filename
    
    # Save the file
    try:
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
        # Create the full URL using the base URL
        relative_path = f"/static/profile_pictures/{unique_filename}"
        full_url = urljoin(base_url, relative_path)
        return full_url
    except Exception as e:
        logger.error(f"Error saving profile picture: {e}")
        raise HTTPException(status_code=500, detail="Failed to save profile picture")

@router.get('/building/list', description="List All Buildings")
async def list_buildings(
    db_session: AsyncSession = Depends(yield_db_session)
):
    buildings = await Building.list(db_session)
    return success([building.to_dict for building in buildings])

@router.post('/building/register', description="Register a New Building")
async def register_building(
    request: Request,
    body: BuildingInputField,
    db_session: AsyncSession = Depends(yield_db_session)
):
    the_user = await Building.filter_by(
        db_session,
        building_url=body.building_url
    )

    if the_user:
        logger.info(
            f"{body.building_url!r} is  registered in the system."
        )

        raise BadRequest(
            "Sorry, but the building is already registered in the system."
        )

    new_building = await Building.create(db_session, name=body.name, building_url=body.building_url, access_token=body.access_token)

    return new_building.to_dict

@router.put('/building/edit/{building_id}', description="Edit an Existing Building")
async def edit_building(
    request: Request,
    building_id: int = Path(..., description="The ID of the building to edit"),
    body: BuildingInputField = Depends(),
    db_session: AsyncSession = Depends(yield_db_session)
):
    building = await Building.get(db_session, building_id)
    
    if not building:
       raise HTTPException(status_code=404, detail="Building not found.")


    await building.update(
        db_session,
        id=building_id,
        name=body.name,
        building_url=body.building_url,
        access_token=body.access_token
    )
    
    return success(building.to_dict)

@router.delete('/building/delete/{building_id}', description="Delete a Building")
async def delete_building(
    building_id: int = Path(..., description="The ID of the building to delete"),
    db_session: AsyncSession = Depends(yield_db_session)
):
    success_flag = await Building.delete(db_session, building_id)
    if not success_flag:
        raise HTTPException(status_code=404, detail="Building not found.")
    return success({"message": "Building deleted successfully."})

@router.post("/building/create-user/{building_id}", description="Create User via WebSocket")
async def create_user_via_ws(
    request: Request,
    building_id: int = Path(..., description="The ID of the building"),
    username: str = Form(...),
    password: str = Form(...),
    display_name: Optional[str] = Form(None),
    local_access_only: Optional[bool] = Form(False),
    administrator: Optional[bool] = Form(False),
    profile_picture: Optional[UploadFile] = File(None),
    db_session: AsyncSession = Depends(yield_db_session)
):
    building = await Building.get(db_session, building_id)
    if not building:
        raise HTTPException(status_code=404, detail="Building not found.")

    profile_picture_url = None
    if profile_picture:
        # Get the base URL from the request
        base_url = str(request.base_url)
        profile_picture_url = await save_profile_picture(profile_picture, base_url)

    client = HomeAssistantWS(domain=building.building_url, access_token=building.access_token)
    
    try:
        await client.connect()
        response = await client.create_user(
            username=username,
            password=password,
            display_name=display_name,
            local_only=local_access_only,
            administrator=administrator,
            profile_picture_url=profile_picture_url
        )
        return success(response)
    except Exception as e:
        logger.error(f"Error in create_user_via_ws: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create user: {e}")
    finally:
        await client.close()
        logger.info("WebSocket connection closed")

@router.put("/building/edit-user/{building_id}", description="Edit User via WebSocket")
async def edit_user_via_ws(
    body: BuildingUserUpdateField,
    building_id: int = Path(..., description="The ID of the building"),
    db_session: AsyncSession = Depends(yield_db_session)
):
    building = await Building.get(db_session, building_id)
    if not building:
        raise HTTPException(status_code=404, detail="Building not found.")
    client = HomeAssistantWS(domain=building.building_url, access_token=building.access_token)
    try:
        await client.connect()
        response = await client.update_person(
            display_name=body.display_name,
            local_only=body.local_access_only if body.local_access_only is not None else False,
            user_id=body.user_id,
            group_ids=body.group_ids
        )
        return success(response)
    except Exception as e:
        logger.error(f"Error in edit_user_via_ws: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to edit user: {e}")
    finally:
        await client.close()
        logger.info("WebSocket connection closed")

@router.delete("/building/delete-user/{building_id}/{user_id}", description="Delete User via WebSocket")
async def delete_user_via_ws(
    building_id: int = Path(..., description="The ID of the building"),
    user_id: str = Path(..., description="The ID of the user to delete"),
    db_session: AsyncSession = Depends(yield_db_session)
):
    building = await Building.get(db_session, building_id)
    if not building:
        raise HTTPException(status_code=404, detail="Building not found.")
    client = HomeAssistantWS(domain=building.building_url, access_token=building.access_token)
    try:
        await client.connect()
        response = await client.delete_person(user_id)
        return success(response)
    except Exception as e:
        logger.error(f"Error in delete_user_via_ws: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete user: {e}")
    finally:
        await client.close()
        logger.info("WebSocket connection closed")

@router.get("/building/users", description="List all users from each building")
async def list_building_users(db_session: AsyncSession = Depends(yield_db_session)):
    buildings = await Building.list(db_session)
    results = {}

    for building in buildings:
        client = HomeAssistantWS(
            domain=building.building_url,
            access_token=building.access_token
        )
        try:
            await client.connect()
            # Send the person/list command and await the response.
            response = await client.list_persons()
            # Use the building name as the top-level key.
            response['building_id'] = building.id
            results[building.name] = response
        except Exception as e:
            logger.error(f"Error retrieving users from building {building.name}: {e}")
            results[building.name] = {"error": str(e)}
        finally:
            await client.close()

    return success(results)
