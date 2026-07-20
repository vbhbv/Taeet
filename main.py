import asyncio
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage, Redis
from logging.handlers import RotatingFileHandler
import logging
from config import BOT_TOKEN, DATABASE_URL, logger
import asyncpg
from services.queue_service import QueueService
from services.match_service import MatchmakingService
from services.health_service import SystemHealthService
from middlewares import EnterpriseLoggingMiddleware
import handlers_chat

def setup_production_logging():
    log_handler = RotatingFileHandler("debate_bot.log", maxBytes=15*1024*1024, backupCount=10)
    log_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] (Trace:%(name)s) - %(message)s"))
    logging.getLogger().addHandler(log_handler)

async def main() -> None:
    setup_production_logging()
    bot = Bot(token=BOT_TOKEN)
    
    redis_client = Redis(host='localhost', port=6379, decode_responses=True)
    storage = RedisStorage(redis=redis_client)
    dp = Dispatcher(storage=storage)
    
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)

    queue_service = QueueService(redis_client)
    match_service = MatchmakingService(db_pool, redis_client, queue_service)
    health_service = SystemHealthService(db_pool, redis_client, queue_service)

    # تشغيل الـ Automated Self-Healing عند الإقلاع لمزامنة النظام
    await health_service.run_startup_recovery()

    dp.message.outer_middleware(EnterpriseLoggingMiddleware({
        "match_service": match_service,
        "queue_service": queue_service
    }))
    dp.callback_query.outer_middleware(EnterpriseLoggingMiddleware({
        "match_service": match_service,
        "queue_service": queue_service
    }))

    dp.include_router(handlers_chat.router)
    
    logger.info("🚀 [ENTERPRISE READY] النظام يعمل الآن بأقصى درجات الحصانة الهندسية...")
    
    try:
        await dp.start_polling(bot)
    finally:
        logger.info("🛑 Shuting down production environment gracefully...")
        await dp.storage.close()
        await redis_client.close()
        await db_pool.close()
        await bot.session.close()
        logger.info("✨ Offline safely.")

if __name__ == "__main__":
    asyncio.run(main())
