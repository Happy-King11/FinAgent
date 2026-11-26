"""结构化日志初始化，避免记录密钥、JWT 和完整个人敏感信息。"""

import logging


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(name)s %(message)s")
