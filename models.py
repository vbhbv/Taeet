from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass(frozen=True)
class UserEntity:
    user_id: int
    nickname: str
    level: str
    topic: Optional[str]
    status: str  # 'idle', 'searching', 'in_chat'
    in_chat_with: Optional[int]
    version: int
    waiting_since: Optional[datetime]
    updated_at: datetime

@dataclass(frozen=True)
class UserDTO:
    user_id: int
    nickname: str
    level: str
    topic: Optional[str]
    status: str
    is_in_chat: bool
