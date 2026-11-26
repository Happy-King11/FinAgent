"""对象存储协议。"""

from typing import Protocol


class ObjectStorage(Protocol):
    def put(self, key: str, content: bytes, content_type: str) -> str: ...
    def get(self, key: str) -> bytes: ...
