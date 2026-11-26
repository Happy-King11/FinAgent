"""仅用于开发的本地对象存储；生产必须切换 S3/MinIO。"""

from pathlib import Path


class LocalObjectStorage:
    def __init__(self, root: Path):
        self.root = root

    def put(self, key: str, content: bytes, content_type: str = "application/octet-stream") -> str:
        target = (self.root / key).resolve()
        if self.root.resolve() not in target.parents:
            raise ValueError("object key escapes storage root")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return key

    def get(self, key: str) -> bytes:
        return (self.root / key).read_bytes()
