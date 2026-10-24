import logging
import sys

import structlog


def configure_logging(log_format: str = "console", level: str = "INFO"):
    """Route structlog AND the standard logging module through one formatter.

    Returns the handler we installed (tests swap its output stream)."""
    shared = [
        structlog.contextvars.merge_contextvars,  
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.ExtraAdder(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *shared,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    if log_format == "json":
        renderers = [structlog.processors.dict_tracebacks, structlog.processors.JSONRenderer()]
    else:
        renderers = [structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty())]

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared, 
            processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, *renderers],
        )
    )
    handler._bantr = True  

    root = logging.getLogger()
    for old in [h for h in root.handlers if getattr(h, "_bantr", False)]:
        root.removeHandler(old)
    root.addHandler(handler)
    root.setLevel(level.upper())
    logging.getLogger("werkzeug").setLevel(logging.WARNING)  
    return handler