"""
MCP User Tools - FastMCP tool definitions for user operations

This module providers MCP tools for interacting with the Memento AI Memory System
for user operations. 

-   Query User Information
-   Update User Infomration
"""

from fastmcp import FastMCP, Context

from app.services.user_service import UserService
from app.models.user_models import User, UserUpdate
from app.middleware.mcp_auth import get_mcp_user


def register(mcp: FastMCP, service: UserService):
    "Register the user tools with the provided service instance"
    
    @mcp.tool()
    async def get_current_user() -> dict:
        """
        Returns informaiton about the current user

        **WHAT**: Returns information about the current user.

        **WHEN TO USE**: 1. When you any details about the user
                         2. When you might want to validate the users preferences

        **BEHAVIOUR**: 
        - Returns a User Object that contains infomration about the user
        - Includes fields that you can update 
        
        **WHEN NOT TO USE**::
        - When you already have context about the
        - When the request does not require information about the user or their preferences
        """
        current_user = get_mcp_user()
        return await current_user.model 
    
    @mcp.tool()
    async def update_user_notes(user_notes: str) -> User:
        user =  await get_mcp_user()

        user_update = UserUpdate(
            external_id=user.external_id,
            notes=user_notes
        )
        
        


        

        

