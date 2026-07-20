import asyncio
import asyncpg
from redis.asyncio import Redis
from unit_of_work import UnitOfWork
from services.queue_service import QueueService
from config import logger

class SystemHealthService:
    def __init__(self, pool: asyncpg.Pool, redis: Redis, queue_service: QueueService):
        self._pool = pool
        self._redis = redis
        self._queue = queue_service

    async def run_startup_recovery(self):
        logger.info("⚡ System Startup: Re-building Redis Queues from PostgreSQL State...")
        async with UnitOfWork(self._pool) as uow:
            rows = await uow._conn.fetch(
                "SELECT user_id, topic, level FROM users WHERE status = 'searching' ORDER BY waiting_since ASC;"
            )
            
            buckets = {}
            for r in rows:
                buckets.setdefault((r['topic'], r['level']), []).append(r['user_id'])
            
            for (topic, level), uids in buckets.items():
                await self._queue.clear_and_repopulate(topic, level, uids)
        logger.info("✨ Recovery complete. Database and Cache layers are fully synchronized.")

    async def monitor_diagnostics(self) -> dict:
        metrics = {}
        try:
            t0 = asyncio.get_event_loop().time()
            async with UnitOfWork(self._pool) as uow:
                await uow._conn.execute("SELECT 1;")
            metrics["postgres_latency_ms"] = (asyncio.get_event_loop().time() - t0) * 1000
            metrics["postgres_status"] = "HEALTHY"
        except Exception as e:
            metrics["postgres_status"] = f"CRITICAL: {str(e)}"

        try:
            t0 = asyncio.get_event_loop().time()
            await self._redis.ping()
            metrics["redis_latency_ms"] = (asyncio.get_event_loop().time() - t0) * 1000
            metrics["redis_status"] = "HEALTHY"
        except Exception as e:
            metrics["redis_status"] = f"CRITICAL: {str(e)}"

        return metrics
