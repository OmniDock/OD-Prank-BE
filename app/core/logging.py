import logging 
import sys 
import structlog 
import logging.handlers 
from app.core.config import settings 


# Basic logging config 
logging.basicConfig(
    format="%(message)s",  # structlog takes care of final rendering
    stream=sys.stdout,
    level=settings.LOG_LEVEL,
)

shared_processors: list[structlog.typing.Processor] = [
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.add_log_level,
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,  # renders exception tracebacks nicely
]

console_renderer = structlog.dev.ConsoleRenderer(colors=True)

structlog.configure(
    processors=shared_processors + [console_renderer],
    wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, settings.LOG_LEVEL)),
    logger_factory=structlog.stdlib.LoggerFactory(),
    context_class=dict,
    cache_logger_on_first_use=True,
)


# Importable loggers
console_logger: structlog.BoundLogger = structlog.get_logger("console")

# Silencing other loggers
# logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
# logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
# logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
# logging.getLogger("sqlalchemy.dialects").setLevel(logging.WARNING)
# logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
# logging.getLogger("sqlalchemy.orm").setLevel(logging.WARNING)

# logging.getLogger("httpx").setLevel(logging.WARNING)
# logging.getLogger("httpcore").setLevel(logging.WARNING)

# logging.getLogger("postgrest").setLevel(logging.WARNING)    
# logging.getLogger("supabase").setLevel(logging.WARNING)