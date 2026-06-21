"""JSON file-based cache with TTL support."""
import json
import os
import time
import hashlib
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class JSONCache:
    """Simple file-based cache with TTL expiration."""

    def __init__(self, cache_dir: str = "./cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _key_to_path(self, key: str) -> Path:
        """Convert a cache key to a file path using hash."""
        safe_key = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{safe_key}.json"

    def get(self, key: str) -> dict | None:
        """Get cached data if not expired."""
        path = self._key_to_path(key)
        if not path.exists():
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                entry = json.load(f)

            if time.time() > entry.get("expires_at", 0):
                path.unlink(missing_ok=True)
                logger.debug(f"Cache expired: {key}")
                return None

            logger.debug(f"Cache hit: {key}")
            return entry["data"]
        except (json.JSONDecodeError, KeyError):
            path.unlink(missing_ok=True)
            return None

    def set(self, key: str, data: dict, ttl: int = 300) -> None:
        """Set cache with TTL in seconds."""
        path = self._key_to_path(key)
        entry = {
            "data": data,
            "created_at": time.time(),
            "expires_at": time.time() + ttl,
            "key": key,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entry, f, ensure_ascii=False, default=str)
        logger.debug(f"Cache set: {key} (TTL: {ttl}s)")

    def invalidate(self, key: str) -> None:
        """Remove a specific cache entry."""
        path = self._key_to_path(key)
        path.unlink(missing_ok=True)

    def clear(self) -> None:
        """Clear all cached data."""
        for f in self.cache_dir.glob("*.json"):
            f.unlink()
        logger.info("Cache cleared")

    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count removed."""
        count = 0
        now = time.time()
        for f in self.cache_dir.glob("*.json"):
            try:
                with open(f, "r") as fp:
                    entry = json.load(fp)
                if now > entry.get("expires_at", 0):
                    f.unlink()
                    count += 1
            except (json.JSONDecodeError, KeyError):
                f.unlink()
                count += 1
        return count


# Global cache instance
cache = JSONCache()
