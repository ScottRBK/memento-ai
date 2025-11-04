"""
MCP User Tools - FastMCP tool definitions for user operations

This module provides MCP tools for interacting with the Memento AI Memory System
for user operations.

-   Query User Information
-   Update User Information
"""

from fastmcp import FastMCP

from app.models.user_models import UserUpdate
from app.middleware.auth import get_user_from_auth, get_user_service
from app.config.logging_config import logging
from app.exceptions import NotFoundError

logger = logging.getLogger(__name__)


def register(mcp: FastMCP):
    """Register the user tools with the provided service instance"""

    @mcp.tool(
        output_schema={
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "data": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "external_id": {"type": "string"},
                        "name": {"type": "string"},
                        "email": {"type": "string"},
                        "notes": {"type": ["string", "null"]},
                        "created_at": {"type": "string"},
                        "updated_at": {"type": "string"}
                    }
                },
                "error": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string"},
                        "message": {"type": "string"}
                    }
                }
            }
        }
    )
    async def get_current_user() -> dict:
        """
        Returns information about the current user

        **WHAT**: Returns information about the current authenticated user.

        **WHEN TO USE**:
        1. When you need any details about the user
        2. When you want to validate the user's preferences or settings
        3. At the start of a conversation to understand user context

        **BEHAVIOR**:
        - Returns a User object containing information about the authenticated user
        - Includes fields like id, external_id, name, email, notes, timestamps
        - Auto-provisions user if they don't exist (when AUTH_ENABLED=false)

        **WHEN NOT TO USE**:
        - When you already have cached user context
        - When the request does not require information about the user or their preferences
        - During repeated operations where user data hasn't changed
        """
        try:
            user = await get_user_from_auth()
            logger.info("successfully retrieved current user", extra={"user": user.name, "user_id": user.id, "external_id": user.external_id})
            return {
                "success": True,
                "data": user.model_dump()
            }
        except Exception as e:
            logger.exception(
                msg="Retrieving user information failed",
                extra={"error": str(e)}
            )
            return {
                "success": False,
                "error": {
                    "code": "USER_FETCH_ERROR",
                    "message": f"Failed to retrieve user: {str(e)}"
                }
            }

    @mcp.tool(
        output_schema={
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "data": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "external_id": {"type": "string"},
                        "name": {"type": "string"},
                        "email": {"type": "string"},
                        "notes": {"type": ["string", "null"]},
                        "created_at": {"type": "string"},
                        "updated_at": {"type": "string"}
                    }
                },
                "error": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string"},
                        "message": {"type": "string"}
                    }
                }
            }
        }
    )
    async def update_user_notes(user_notes: str) -> dict:
        """
        Update the notes field for the current user

        **WHAT**: Updates the notes/metadata field for the authenticated user.

        **WHEN TO USE**:
        1. When the user wants to store personal preferences or context
        2. When you need to persist user-specific information for future conversations
        3. When updating user metadata that doesn't fit other structured fields

        **BEHAVIOR**:
        - Updates only the 'notes' field for the current user
        - Returns the updated User object with new notes value
        - Does not modify other user fields (name, email, etc.)
        - Auto-creates user if they don't exist
        - Replaces existing value of notes field so remember to pass persist if still relevant

        **WHEN NOT TO USE**:
        - When you need to update other user fields (name, email) - those are managed by IDP
        - When notes haven't actually changed
        - For storing temporary conversation context (use memory system instead)

        Args:
            user_notes: The new notes content to store for the user
        """
        try:
            user = await get_user_from_auth()
            service = get_user_service()
            # Create update with only the notes field
            user_update = UserUpdate(
                external_id=user.external_id,  # Needed for lookup
                notes=user_notes
            )

            updated_user = await service.update_user(user_update=user_update)

            if not updated_user:
                return {
                    "success": False,
                    "error": {
                        "code": "UPDATE_FAILED",
                        "message": "Failed to update user notes"
                    }
                }

            return {
                "success": True,
                "data": updated_user.model_dump()
            }
        except NotFoundError as e:
            logger.error(
                msg="User not found during update",
                extra={"error": str(e)}
            )
            return {
                "success": False,
                "error": {
                    "code": "USER_NOT_FOUND",
                    "message": str(e)
                }
            }
        except Exception as e:
            logger.exception(
                msg="User update failed",
                extra={"error": str(e)}
            )
            return {
                "success": False,
                "error": {
                    "code": "UPDATE_ERROR",
                    "message": f"Error updating user notes: {str(e)}"
                }
            }
