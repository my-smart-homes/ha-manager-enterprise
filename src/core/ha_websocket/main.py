import json
import websockets
import logging
from typing import Optional
from src.logger import get_logger
logger = get_logger(__name__)

class HomeAssistantWS:
    def __init__(self, domain: str, access_token: str):
        self.domain = domain
        self.access_token = access_token
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.message_id = 1

    async def connect(self) -> None:
        try:
            print('------connecting----')
            self.websocket = await websockets.connect(f"ws://{self.domain}/api/websocket")
            print('----test--',self.websocket)
            auth_required = await self.websocket.recv()
            logger.info("Authentication required")
            auth_message = {"type": "auth", "access_token": self.access_token}
            await self.websocket.send(json.dumps(auth_message))
            auth_response = json.loads(await self.websocket.recv())
            if auth_response.get("type") == "auth_ok":
                logger.info("Authentication successful")
            else:
                raise Exception("Authentication failed")
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            if self.websocket:
                await self.websocket.close()
            raise

    async def create_user(self, username: str, password: str, display_name: Optional[str] = None,
                          local_only: bool = False, administrator: bool = False) -> dict:
        if not self.websocket:
            raise Exception("Not connected")
        try:
            name = display_name if display_name else username
            group_ids = ["system-admin"] if administrator else ["system-users"]
            create_user_message = {"id": self.message_id, "type": "config/auth/create", "name": name, "group_ids": group_ids, "local_only": local_only}
            await self.websocket.send(json.dumps(create_user_message))
            user_response = await self.websocket.recv()
            logger.info("Create User Response: %s", user_response)
            user_data = json.loads(user_response)
            user_id = user_data.get("result", {}).get("user", {}).get("id")
            self.message_id += 1
            create_user_profile = {"id": self.message_id, "type": "person/create", "name": name, "user_id": user_id,"picture":"/api/image/serve/683ba0392fe20c40b5616ffab3b876d0/512x512"}
            await self.websocket.send(json.dumps(create_user_profile))
            # response = json.loads(await self.websocket.recv())
            self.message_id += 1
            message = {"id": self.message_id, "type": "config/auth_provider/homeassistant/create", "user_id": user_id, "username": username, "password": password}
            await self.websocket.send(json.dumps(message))
            response = json.loads(await self.websocket.recv())
            if "error" in response:
                raise Exception(f"Error creating user: {response['error']}")
            return response
        except Exception as e:
            logger.error(f"Failed to create user: {e}")
            raise
    async def list_persons(self) -> dict:
        """
        Connects to the Home Assistant websocket to request a list of persons.
        """
        if not self.websocket:
            raise Exception("Not connected")
        try:
            # Construct the person/list message.
            message = {"id": self.message_id, "type": "config/auth/list"}
            self.message_id += 1
            await self.websocket.send(json.dumps(message))
            # Wait for and return the response.
            response = json.loads(await self.websocket.recv())
            return response
        except Exception as e:
            logger.error(f"Failed to list persons: {e}")
            raise
    async def update_person(self, user_id: str, display_name: str, group_ids: list[str],local_only:bool) -> dict:
        """
        Connects to the Home Assistant websocket to update a person.
        """
        if not self.websocket:
            raise Exception("Not connected")
        try:
            # Construct the person/update message.
            message = {"id": self.message_id, "type": "config/auth/update", "user_id": user_id, "name": display_name,"local_only":local_only, "group_ids": group_ids}
            self.message_id += 1
            await self.websocket.send(json.dumps(message))
            # Wait for and return the response.
            response = json.loads(await self.websocket.recv())
            return response
        except Exception as e:
            logger.error(f"Failed to update person: {e}")
            raise
    async def delete_person(self, user_id: str) -> dict:
        """
        Connects to the Home Assistant websocket to delete a person.
        """
        if not self.websocket:
            raise Exception("Not connected")
        try:
            # Construct the person/delete message.
            message = {"id": self.message_id, "type": "config/auth/delete", "user_id": user_id}
            self.message_id += 1
            await self.websocket.send(json.dumps(message))
            # Wait for and return the response.
            response = json.loads(await self.websocket.recv())
            return response
        except Exception as e:
            logger.error(f"Failed to delete person: {e}")
            raise
    async def close(self) -> None:
        if self.websocket:
            await self.websocket.close()
