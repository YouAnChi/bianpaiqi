import logging
import sys
from rich.logging import RichHandler

def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(level)
        # 使用 RichHandler 提供更美观的日志输出
        handler = RichHandler(rich_tracebacks=True, markup=True)
        formatter = logging.Formatter('%(message)s', datefmt="[%X]")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        # 防止日志向上传播导致重复
        logger.propagate = False
    return logger
