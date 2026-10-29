"""A deterministic string-key hash map using separate chaining."""

from typing import Any, List, Optional, Tuple

from .doubly_linked_list import DoublyLinkedList, Node


class MapEntry:
    """Store one key-value pair inside a hash bucket."""

    def __init__(self, key: str, value: Any) -> None:
        self.key = key
        self.value = value


class HashMap:
    """Map string keys to values without using Python's built-in dict."""

    def __init__(self, initial_capacity: int = 8) -> None:
        if initial_capacity <= 0:
            raise ValueError("initial_capacity must be positive")
        self._capacity = initial_capacity
        self._buckets: List[Optional[DoublyLinkedList]] = [None] * initial_capacity
        self._size = 0

    def _hash(self, key: str) -> int:
        hash_value = 0
        for byte in key.encode("utf-8"):
            hash_value = (hash_value * 31 + byte) & 0xFFFFFFFFFFFFFFFF
        return hash_value

    def _bucket_index(self, key: str) -> int:
        return self._hash(key) % self._capacity

    def _find_node(self, key: str) -> Tuple[Optional[DoublyLinkedList], Optional[Node]]:
        bucket = self._buckets[self._bucket_index(key)]
        if bucket is None:
            return None, None
        for node in bucket.iter_nodes():
            entry = node.data
            if entry.key == key:
                return bucket, node
        return bucket, None

    def put(self, key: str, value: Any) -> None:
        bucket, node = self._find_node(key)
        if node is not None:
            node.data.value = value
            return
        if bucket is None:
            index = self._bucket_index(key)
            bucket = DoublyLinkedList()
            self._buckets[index] = bucket
        bucket.insert_back(MapEntry(key, value))
        self._size += 1
        if self._size / self._capacity > 0.75:
            self._resize(self._capacity * 2)

    def get(self, key: str, default: Any = None) -> Any:
        _, node = self._find_node(key)
        if node is None:
            return default
        return node.data.value

    def remove(self, key: str, default: Any = None) -> Any:
        bucket, node = self._find_node(key)
        if bucket is None or node is None:
            return default
        entry = bucket.remove_node(node)
        self._size -= 1
        return entry.value

    def contains(self, key: str) -> bool:
        _, node = self._find_node(key)
        return node is not None

    def keys(self) -> List[str]:
        result: List[str] = []
        for bucket in self._buckets:
            if bucket is None:
                continue
            for node in bucket.iter_nodes():
                result.append(node.data.key)
        return result

    def size(self) -> int:
        return self._size

    def _resize(self, new_capacity: int) -> None:
        old_buckets = self._buckets
        self._capacity = new_capacity
        self._buckets = [None] * new_capacity
        for bucket in old_buckets:
            if bucket is None:
                continue
            for node in bucket.iter_nodes():
                entry = node.data
                index = self._bucket_index(entry.key)
                destination = self._buckets[index]
                if destination is None:
                    destination = DoublyLinkedList()
                    self._buckets[index] = destination
                destination.insert_back(entry)

    @property
    def capacity(self) -> int:
        return self._capacity
