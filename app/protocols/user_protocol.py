from typing import Protocol 

class UserRepository(Protocol):
    "Contract for user repository"
    
    async def get_user_by_id(self, user_id: it)