import uuid
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from typing import Callable, Dict, Any, Awaitable
from context import correlation_id

class EnterpriseLoggingMiddleware(BaseMiddleware):
    def __init__(self, services: dict):
        super().__init__()
        self._services = services

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        req_id = str(uuid.uuid4())[:8]
        token = correlation_id.set(req_id)
        
        try:
            for name, service in self._services.items():
                data[name] = service
            return await handler(event, data)
        finally:
            correlation_id.reset(token)
