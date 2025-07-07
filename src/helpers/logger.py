import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from src.core.config import settings


def Logger(name: str = settings.PROJECT_NAME) -> logging.Logger:
    log = logging.getLogger(name)
    log.setLevel(logging.DEBUG if settings.ENV == "development" else logging.INFO)
    log.propagate = False

    if log.hasHandlers():
        log.handlers.clear()

    formatter = logging.Formatter(
        fmt="%(levelname)s [%(asctime)s] [%(name)s:%(funcName)s:%(lineno)d] : %(message)s ",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    log.addHandler(console_handler)

    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        filename=log_dir / settings.LOG_FILE,
        maxBytes=settings.LOG_FILE_MAX_BYTES,
        backupCount=settings.LOG_FILE_BACKUP_COUNT,
    )
    file_handler.setFormatter(formatter)
    log.addHandler(file_handler)

    return log


logger = Logger()
