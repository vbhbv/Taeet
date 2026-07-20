import time
from redis.asyncio import Redis
from typing import List, Optional

class QueueService:
    def __init__(self, redis: Redis):
        self._redis = redis

    def _get_queue_key(self, topic: str, level: str) -> str:
        return f"queue:{topic}:{level}"

    async def add_to_queue(self, user_id: int, topic: str, level: str) -> None:
        key = self._get_queue_key(topic, level)
        await self._redis.zadd(key, {str(user_id): time.time()})
        await self._redis.expire(key, 1800)

    async def pop_oldest_match(self, user_id: int, topic: str, level: str) -> Optional[int]:
        key = self._get_queue_key(topic, level)
        results = await self._redis.zrange(key, 0, 10)
        for uid_bytes in results:
            uid = int(uid_bytes)
            if uid != user_id:
                if await self._redis.zrem(key, uid_bytes) > 0:
                    return uid
        return None

    async def remove_from_queue(self, user_id: int, topic: str, level: str) -> None:
        key = self._get_queue_key(topic, level)
        await self._redis.zrem(key, str(user_id))

    async def clear_and_repopulate(self, topic: str, level: str, user_ids: List[int]) -> None:
        key = self._get_queue_key(topic, level)
        await self._redis.delete(key)
        if user_ids:
            mapping = {str(uid): time.time() for uid in user_ids}
            await self._redis.zadd(key, mapping)
