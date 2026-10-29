"""Core Mini Redis storage composed from the custom data structures."""

import math
import time
from typing import Callable, List, Optional, Tuple

from .doubly_linked_list import DoublyLinkedList, Node
from .hash_map import HashMap
from .min_heap import MinHeap


class CacheEntry:
    """Hold a value and its LRU and expiration metadata."""

    def __init__(self, key: str, value: str) -> None:
        self.key = key
        self.value = value
        self.lru_node: Optional[Node] = None
        self.expire_at: Optional[float] = None
        self.ttl_token: Optional[int] = None


class MiniRedisStore:
    """Coordinate lookup, LRU order, expiration, and memory counters."""

    def __init__(self, clock: Callable[[], float] = time.time) -> None:
        self._clock = clock
        self._entries = HashMap()
        self._lru = DoublyLinkedList()
        self._ttl_heap = MinHeap()
        self._next_ttl_token = 0
        self.used_memory = 0
        self.maxmemory = 0
        self.evicted_keys = 0

    def set(self, key: str, value: str) -> bool:
        """Store a string value and mark the key most recently used."""
        self._expire_key(key)
        new_size = self._entry_size(key, value)
        if self.maxmemory > 0 and new_size > self.maxmemory:
            return False
        self._purge_expired()

        entry = self._entries.get(key)
        if entry is not None:
            self.used_memory -= self._entry_size(entry.key, entry.value)
            entry.value = value
            entry.expire_at = None
            entry.ttl_token = None
            self._lru.move_to_front(entry.lru_node)
            self.used_memory += new_size
            self._evict_until_within_limit()
            return True

        entry = CacheEntry(key, value)
        entry.lru_node = self._lru.insert_front(entry)
        self._entries.put(key, entry)
        self.used_memory += new_size
        self._evict_until_within_limit()
        return True

    def get(self, key: str) -> Optional[str]:
        """Return a value and refresh LRU order when the key exists."""
        self._expire_key(key)
        entry = self._entries.get(key)
        if entry is None:
            return None
        self._lru.move_to_front(entry.lru_node)
        return entry.value

    def delete(self, key: str) -> int:
        """Delete one key from the map and LRU list."""
        self._expire_key(key)
        entry = self._entries.get(key)
        if entry is None:
            return 0
        self._delete_entry(entry)
        return 1

    def exists(self, key: str) -> int:
        self._expire_key(key)
        return 1 if self._entries.contains(key) else 0

    def dbsize(self) -> int:
        self._purge_expired()
        return self._entries.size()

    def keys(self) -> List[str]:
        self._purge_expired()
        return self._entries.keys()

    def configure_maxmemory(self, maxmemory: int) -> None:
        self.maxmemory = maxmemory

    def info_memory(self) -> Tuple[int, int, int]:
        self._purge_expired()
        return self.used_memory, self.maxmemory, self.evicted_keys

    def expire(self, key: str, seconds: int) -> int:
        """Assign a lifetime in seconds to an existing key."""
        now = self._clock()
        self._expire_key(key, now)
        entry = self._entries.get(key)
        if entry is None:
            return 0
        if seconds <= 0:
            self._delete_entry(entry)
            return 1
        self._next_ttl_token += 1
        entry.expire_at = now + seconds
        entry.ttl_token = self._next_ttl_token
        self._ttl_heap.push((entry.expire_at, entry.ttl_token, key))
        return 1

    def ttl(self, key: str) -> int:
        """Return remaining lifetime using Redis-style sentinel values."""
        now = self._clock()
        self._expire_key(key, now)
        entry = self._entries.get(key)
        if entry is None:
            return -2
        if entry.expire_at is None:
            return -1
        return int(math.ceil(entry.expire_at - now))

    def _entry_size(self, key: str, value: str) -> int:
        return len(key.encode("utf-8")) + len(value.encode("utf-8"))

    def _delete_entry(self, entry: CacheEntry, evicted: bool = False) -> None:
        self._entries.remove(entry.key)
        if entry.lru_node is not None:
            self._lru.remove_node(entry.lru_node)
            entry.lru_node = None
        self.used_memory -= self._entry_size(entry.key, entry.value)
        entry.expire_at = None
        entry.ttl_token = None
        if evicted:
            self.evicted_keys += 1

    def _evict_until_within_limit(self) -> None:
        while self.maxmemory > 0 and self.used_memory > self.maxmemory:
            entry = self._lru.remove_back()
            if entry is None:
                return
            entry.lru_node = None
            self._entries.remove(entry.key)
            self.used_memory -= self._entry_size(entry.key, entry.value)
            entry.expire_at = None
            entry.ttl_token = None
            self.evicted_keys += 1

    def _expire_key(self, key: str, now: Optional[float] = None) -> bool:
        if now is None:
            now = self._clock()
        entry = self._entries.get(key)
        if entry is None or entry.expire_at is None or entry.expire_at > now:
            return False
        self._delete_entry(entry)
        return True

    def _purge_expired(self, now: Optional[float] = None) -> None:
        if now is None:
            now = self._clock()
        while True:
            item = self._ttl_heap.peek()
            if item is None or item[0] > now:
                return
            expire_at, token, key = self._ttl_heap.pop()
            entry = self._entries.get(key)
            if (
                entry is not None
                and entry.expire_at == expire_at
                and entry.ttl_token == token
            ):
                self._delete_entry(entry)
