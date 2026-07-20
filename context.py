from contextvars import ContextVar

correlation_id: ContextVar[str] = ContextVar("correlation_id", default="SYSTEM")
