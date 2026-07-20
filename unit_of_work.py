import asyncpg
from typing import Optional
from repositories import UserRepository
from context import correlation_id
from config import logger

class UnitOfWork:
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool
        self._conn: Optional[asyncpg.Connection] = None
        self._tx: Optional[asyncpg.transaction.Transaction] = None
        self.users: Optional[UserRepository] = None

    async def __aenter__(self):
        self._conn = await self._pool.acquire()
        self._tx = self._conn.transaction()
        await self._tx.start()
        self.users = UserRepository(self._conn)
        return self

    async def commit(self):
        if self._tx:
            await self._tx.commit()

    async def rollback(self):
        if self._tx:
            await self._tx.rollback()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type:
                await self.rollback()
        except Exception:
            logger.exception(f"[{correlation_id.get()}] Failed to rollback safely")
        finally:
            if self._conn:
                await self._pool.release(self._conn)
