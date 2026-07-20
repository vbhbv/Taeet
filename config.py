import os
import logging

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/dbname")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DebateBot")

