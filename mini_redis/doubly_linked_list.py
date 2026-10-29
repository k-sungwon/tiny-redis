"""A doubly linked list used by hash buckets and LRU tracking."""

from typing import Any, Iterator, Optional


class Node:
    """Store one value and links to the previous and next nodes."""

    def __init__(self, data: Any) -> None:
        self.prev: Optional["Node"] = None
        self.next: Optional["Node"] = None
        self.data = data


class DoublyLinkedList:
    """Maintain ordered nodes with constant-time link changes."""

    def __init__(self) -> None:
        self._head = Node(None)
        self._tail = Node(None)
        self._head.next = self._tail
        self._tail.prev = self._head
        self._length = 0

    def insert_front(self, data: Any) -> Node:
        """Insert data at the front and return its node."""
        node = Node(data)
        first = self._head.next
        node.prev = self._head
        node.next = first
        self._head.next = node
        if first is not None:
            first.prev = node
        self._length += 1
        return node

    def insert_back(self, data: Any) -> Node:
        """Insert data at the back and return its node."""
        node = Node(data)
        last = self._tail.prev
        node.prev = last
        node.next = self._tail
        self._tail.prev = node
        if last is not None:
            last.next = node
        self._length += 1
        return node

    def remove_front(self) -> Optional[Any]:
        """Remove and return the front value, or None when empty."""
        first = self._head.next
        if first is self._tail:
            return None
        if first is None:
            return None
        return self.remove_node(first)

    def remove_back(self) -> Optional[Any]:
        """Remove and return the back value, or None when empty."""
        last = self._tail.prev
        if last is self._head:
            return None
        if last is None:
            return None
        return self.remove_node(last)

    def remove_node(self, node: Node) -> Any:
        """Unlink a known data node in constant time and return its value."""
        previous = node.prev
        following = node.next
        if previous is None or following is None:
            raise ValueError("node is not attached to this list")
        previous.next = following
        following.prev = previous
        node.prev = None
        node.next = None
        self._length -= 1
        return node.data

    def move_to_front(self, node: Node) -> None:
        """Move a known data node to the front in constant time."""
        if node.prev is self._head:
            return
        data = self.remove_node(node)
        first = self._head.next
        node.data = data
        node.prev = self._head
        node.next = first
        self._head.next = node
        if first is not None:
            first.prev = node
        self._length += 1

    def iter_nodes(self) -> Iterator[Node]:
        """Yield data nodes from front to back."""
        current = self._head.next
        while current is not None and current is not self._tail:
            yield current
            current = current.next

    def __len__(self) -> int:
        return self._length
