import asyncpg
from typing import Optional, List
from models import UserEntity
from context import correlation_id
from config import logger

class UserRepository:
    def __init__(self, conn: asyncpg.Connection):
        self._conn = conn

    async def get_user(self, user_id: int) -> Optional[UserEntity]:
        row = await self._conn.fetchrow(
            """SELECT user_id, nickname, level, topic, status, in_chat_with, version, waiting_since, updated_at 
               FROM users WHERE user_id = $1;""", user_id
        )
        return UserEntity(**dict(row)) if row else None

    async def update_user(self, user: UserEntity) -> bool:
        cid = correlation_id.get()
        result = await self._conn.execute(
            """UPDATE users 
               SET status = $2, in_chat_with = $3, version = version + 1, topic = $4, waiting_since = $5, updated_at = NOW()
               WHERE user_id = $1 AND version = $6;""",
            user.user_id, user.status, user.in_chat_with, user.topic, user.waiting_since, user.version
        )
        success = result == "UPDATE 1"
        if not success:
            logger.warning(f"[{cid}] Optimistic Lock failed for user {user.user_id}, version {user.version}")
        return success
