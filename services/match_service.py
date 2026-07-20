import asyncio
import asyncpg
from dataclasses import replace
from datetime import datetime
from typing import Optional
from redis.asyncio import Redis
from unit_of_work import UnitOfWork
from models import UserDTO
from services.queue_service import QueueService
from context import correlation_id
from config import logger

class MatchmakingService:
    def __init__(self, pool: asyncpg.Pool, redis: Redis, queue_service: QueueService):
        self._pool = pool
        self._redis = redis
        self._queue = queue_service

    async def get_user_profile(self, user_id: int) -> Optional[UserDTO]:
        async with UnitOfWork(self._pool) as uow:
            user = await uow.users.get_user(user_id)
            if not user:
                return None
            return UserDTO(
                user_id=user.user_id, nickname=user.nickname,
                level=user.level, topic=user.topic, status=user.status,
                is_in_chat=user.status == "in_chat"
            )

    async def request_match(self, user_id: int, topic: str, request_id: str) -> Optional[int]:
        cid = correlation_id.get()
        lock_key = f"lock:user:{user_id}:{request_id}"
        
        if not await self._redis.set(lock_key, "1", ex=5, nx=True):
            logger.warning(f"[{cid}] Idempotent block triggered for request {request_id}")
            return None

        try:
            async with UnitOfWork(self._pool) as uow:
                user = await uow.users.get_user(user_id)
                if not user or user.status != "idle":
                    return None

                partner_id = await self._queue.pop_oldest_match(user_id, topic, user.level)
                
                if partner_id:
                    partner = await uow.users.get_user(partner_id)
                    if partner and partner.status == "searching" and partner.topic == topic:
                        
                        updated_user = replace(user, status="in_chat", in_chat_with=partner_id, topic=topic, waiting_since=None)
                        updated_partner = replace(partner, status="in_chat", in_chat_with=user_id)

                        if await uow.users.update_user(updated_user) and await uow.users.update_user(updated_partner):
                            await uow.commit()
                            logger.info(f"[{cid}] Real Atomic Match Engaged: {user_id} <-> {partner_id}")
                            return partner_id
                        
                updated_searcher = replace(user, status="searching", topic=topic, waiting_since=datetime.utcnow())
                if await uow.users.update_user(updated_searcher):
                    await uow.commit()
                    await self._queue.add_to_queue(user_id, topic, user.level)
                
                return None
        finally:
            await self._redis.delete(lock_key)

    async def cancel_search_session(self, user_id: int, topic: str, level: str) -> None:
        async with UnitOfWork(self._pool) as uow:
            user = await uow.users.get_user(user_id)
            if user and user.status == "searching":
                updated = replace(user, status="idle", topic=None, waiting_since=None)
                if await uow.users.update_user(updated):
                    await uow.commit()
        await self._queue.remove_from_queue(user_id, topic, level)

    async def terminate_debate_session(self, user_id: int) -> Optional[int]:
        async with UnitOfWork(self._pool) as uow:
            user = await uow.users.get_user(user_id)
            if not user or user.status != "in_chat" or not user.in_chat_with:
                return None
            
            partner = await uow.users.get_user(user.in_chat_with)
            partner_id = user.in_chat_with
            
            updated_user = replace(user, status="idle", in_chat_with=None, topic=None)
            await uow.users.update_user(updated_user)
            
            if partner:
                updated_partner = replace(partner, status="idle", in_chat_with=None, topic=None)
                await uow.users.update_user(updated_partner)
                
            await uow.commit()
            return partner_id
