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
                          local_only: bool = False, administrator: bool = False, profile_picture_url: Optional[str] = None) -> dict:
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
            create_user_profile = {"id": self.message_id, "type": "person/create", "name": name, "user_id": user_id}
            if profile_picture_url:
                create_user_profile["picture"] = profile_picture_url
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
        Connects to the Home Assistant websocket to request a list of users
        (config/auth/list) and then appends each user's profile picture
        from the person registry (config/person/list).
        """
        if not self.websocket:
            raise Exception("Not connected")

        try:
            # 1) Get the raw user list
            auth_msg = {
                "id": self.message_id,
                "type": "config/auth/list",
            }
            self.message_id += 1
            await self.websocket.send(json.dumps(auth_msg))
            auth_resp = json.loads(await self.websocket.recv())
            if not auth_resp.get("success", False):
                raise Exception(f"auth/list failed: {auth_resp}")

            users = auth_resp["result"]

            # 2) Get the person registry (which includes `picture`)
            person_msg = {
                "id": self.message_id,
                "type": "person/list",
            }
            self.message_id += 1
            await self.websocket.send(json.dumps(person_msg))
            person_resp = json.loads(await self.websocket.recv())
            if not person_resp.get("success", False):
                raise Exception(f"person/list failed: {person_resp}")

            persons = person_resp["result"]["storage"]
            # 3) Build a map user_id → picture
            picture_map = {
                person["user_id"]: person.get("picture")
                for person in persons
                if person.get("user_id")
            }

            # 4) Append `picture` onto each user entry
            for user in users:
                user_id = user.get("id")
                user["picture"] = picture_map.get(user_id)

            # Return the enriched auth/list response
            return {
                **auth_resp,
                "result": users,
            }

        except Exception as e:
            logger.error(f"Failed to list persons with pictures: {e}")
            raise
    

    async def update_person(
        self,
        user_id: str,
        display_name: str,
        group_ids: list[str],
        local_only: bool,
        user_name: str = None,
        new_password: str = None,
        profile_picture_url: Optional[str] = None
    ) -> dict:
        """
        Update a person's display name, group, and optionally their username and password.

        Parameters:
        user_id: The Home Assistant user ID to update.
        display_name: New display name.
        group_ids: List of group IDs this user should belong to.
        local_only: Whether the account is local only.
        username: Optional new username.
        password: Optional new password.

        Returns:
        A dict containing responses from:
            - config/auth/update
            - person/update
            - change_password (if applicable)
        """
        if not self.websocket:
            raise Exception("Not connected")

        try:
            # Step 1: Update auth user (without username or password)
            auth_message = {
                "id": self.message_id,
                "type": "config/auth/update",
                "user_id": user_id,
                "name": display_name,
                "local_only": local_only,
                "group_ids": group_ids
            }
            print("Sending auth update:", auth_message)
            self.message_id += 1
            await self.websocket.send(json.dumps(auth_message))
            response = json.loads(await self.websocket.recv())
            print("Auth update response:", response)

            # Step 2 (optional): Update username
            if user_name:
                try:

                    change_username_msg = {
                        "id": self.message_id,
                        "type": "config/auth_provider/homeassistant/admin_change_username",
                        "user_id": user_id,
                        "username": user_name
                    }
                    print("Sending username update:", change_username_msg)
                    self.message_id += 1
                    await self.websocket.send(json.dumps(change_username_msg))
                    response = json.loads(await self.websocket.recv())
                    print("Username update response:", response)
                except Exception as e:
                    print(f"Failed to update username: {e}")
                    raise

            # Step 3 (optional): Update password
            if new_password:
                change_password_msg = {
                    "id": self.message_id,
                    "type": "config/auth_provider/homeassistant/admin_change_password",
                    "user_id": user_id,
                    "password": new_password
                }
                print("Sending password update:", change_password_msg)
                self.message_id += 1
                await self.websocket.send(json.dumps(change_password_msg))
                response = json.loads(await self.websocket.recv())
                print("Password update response:", response)

            # Step 4: Get persons to find person_id
            person_id = await self.get_person_id(user_id)

            # Step 5: Update the person
            update_person_message = {
                "id": self.message_id,
                "type": "person/update",
                "person_id": person_id,
                "user_id": user_id,
                "name": display_name
            }
            if profile_picture_url:
                update_person_message["picture"] = profile_picture_url
                
            print("Sending person update:", update_person_message)
            self.message_id += 1
            await self.websocket.send(json.dumps(update_person_message))
            response = json.loads(await self.websocket.recv())
            print("Person update response:", response)

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
            # construct the person/delete message.
            person_id = await self.get_person_id(user_id)
            message = {"id": self.message_id, "type": "person/delete", "person_id": person_id}
            self.message_id += 1
            await self.websocket.send(json.dumps(message))
            # Wait for and return the response.
            response = json.loads(await self.websocket.recv())
            # Construct the config/delete message.
            message = {"id": self.message_id, "type": "config/auth/delete", "user_id": user_id}
            self.message_id += 1
            await self.websocket.send(json.dumps(message))
            # Wait for and return the response.
            response = json.loads(await self.websocket.recv())
            
            if "error" in response:
                raise Exception(f"Error deleting person: {response['error']}")
            return response
        except Exception as e:
            logger.error(f"Failed to delete person: {e}")
            raise

    async def get_person_id(self, user_id: str) -> str:
        """
        Retrieves the person_id associated with a given user_id.

        Parameters:
        user_id: The Home Assistant user ID.

        Returns:
        The person_id associated with the user_id.

        Raises:
        Exception if no person is linked with the given user_id.
        """
        get_persons_message = {
            "id": self.message_id,
            "type": "person/list"
        }
        self.message_id += 1
        await self.websocket.send(json.dumps(get_persons_message))
        persons_response = json.loads(await self.websocket.recv())
        print("Persons response:", persons_response)

        persons_result = persons_response.get("result", {})
        storage = persons_result.get("storage", [])
        for person in storage:
            if person.get("user_id") == user_id:
                return person.get("id")

        raise Exception(f"No person linked with user_id {user_id}")

    async def close(self) -> None:
        if self.websocket:
            await self.websocket.close()
