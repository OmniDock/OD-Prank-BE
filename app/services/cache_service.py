from __future__ import annotations

import json
import asyncio
from typing import Any, Optional

import redis.asyncio as redis

from app.core.config import settings
from app.core.logging import console_logger

def _sanitize_prefix(p: Optional[str]) -> Optional[str]:
    if p is None:
        return None
    return p.strip(":") or None

class CacheService:
    _global: Optional["CacheService"] = None
    _lock: Optional[asyncio.Lock] = None

    def __init__(self, url: Optional[str] = None, prefix: str = "od"):
        self.url = url or settings.REDIS_URL
        self.prefix = prefix.rstrip(":")
        self.client: Optional[redis.Redis] = None

    def _k(self, key: str) -> str:
        return f"{self.prefix}:{key}"
    
    def _individual_prefix(self, prefix: str | None, key: str) -> str:
        p = _sanitize_prefix(prefix)
        return f"{p}:{key}" if p else key

    async def connect(self) -> None:
        if self.client is None:
            self.client = redis.from_url(self.url, encoding="utf-8", decode_responses=True)
            try:
                await self.client.ping()
                console_logger.info("Redis connected", url=self.url)
            except Exception as e:
                console_logger.error("Redis connection failed", url=self.url, error=str(e))
                raise

    async def close(self) -> None:
        if self.client is not None:
            await self.client.close()
            self.client = None

    async def get(self, key: str, prefix: Optional[str] = None) -> Optional[str]:
        if not self.client:
            raise RuntimeError("CacheService not connected")
        return await self.client.get(self._k(self._individual_prefix(prefix, key)))

    async def set(self, key: str, value: str, ttl: Optional[int] = None, prefix: Optional[str] = None) -> bool:
        if not self.client:
            raise RuntimeError("CacheService not connected")
        res = await self.client.set(self._k(self._individual_prefix(prefix, key)), value, ex=ttl)
        return bool(res)

    async def delete(self, key: str, prefix: Optional[str] = None) -> int:
        if not self.client:
            raise RuntimeError("CacheService not connected")
        return int(await self.client.delete(self._k(self._individual_prefix(prefix, key))))
    
    async def delete_prefix(self, prefix: str) -> int:
        if not self.client:
            raise RuntimeError("CacheService not connected")
        full_prefix = self._k(prefix.rstrip(":"))
        pattern = f"{full_prefix}:*"
        deleted = 0
        batch: list[str] = []
        async for key in self.client.scan_iter(match=pattern):
            batch.append(key)
            if len(batch) >= 500:
                deleted += await self.client.delete(*batch)
                batch.clear()
        if batch:
            deleted += await self.client.delete(*batch)
        return int(deleted)

    async def get_json(self, key: str, prefix: Optional[str] = None) -> Optional[Any]:
        raw = await self.get(key, prefix)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    async def set_json(self, key: str, value: Any, ttl: Optional[int] = None, prefix: Optional[str] = None) -> bool:
        return await self.set(key, json.dumps(value, separators=(",", ":")), ttl=ttl, prefix=prefix)

    def namespace(self, ns: str):
        ns = _sanitize_prefix(ns)
        parent = self
        class _Namespaced:
            async def get(self, key): return await parent.get(key, prefix=ns)
            async def set(self, key, value, ttl=None): return await parent.set(key, value, ttl=ttl, prefix=ns)
            async def delete(self, key): return await parent.delete(key, prefix=ns)
            async def get_json(self, key): return await parent.get_json(key, prefix=ns)
            async def set_json(self, key, value, ttl=None): return await parent.set_json(key, value, ttl=ttl, prefix=ns)
        return _Namespaced()
    

    async def clear_all(self) -> None:
        if not self.client:
            raise RuntimeError("CacheService not connected")
        await self.client.flushall()

    # ===== Global (class-level) helpers =====
    @classmethod
    async def get_global(cls) -> "CacheService":
        if cls._global and cls._global.client:
            return cls._global
        if cls._lock is None:
            cls._lock = asyncio.Lock()
        async with cls._lock:
            if cls._global and cls._global.client:
                return cls._global
            inst = cls()
            await inst.connect()
            cls._global = inst
            return inst

    @classmethod
    async def close_global(cls) -> None:
        if cls._global:
            await cls._global.close()
            cls._global = None