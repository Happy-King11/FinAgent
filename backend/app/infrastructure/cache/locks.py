"""Redis locks with ownership tokens for cross-process coordination."""

from uuid import uuid4


_RELEASE = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end"


class RedisLock:
    def __init__(self, client, key: str, *, ttl_seconds: int = 30):
        self.client = client
        self.key = key
        self.ttl_seconds = ttl_seconds
        self.token = uuid4().hex

    def acquire(self) -> bool:
        return bool(self.client.set(self.key, self.token, nx=True, ex=self.ttl_seconds))

    def release(self) -> bool:
        return bool(self.client.eval(_RELEASE, 1, self.key, self.token))
