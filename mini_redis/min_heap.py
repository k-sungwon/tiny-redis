"""An array-backed minimum heap for expiration records."""

from typing import Any, List, Optional


class MinHeap:
    """Keep the smallest comparable item at the root."""

    def __init__(self) -> None:
        self._items: List[Any] = []

    def push(self, item: Any) -> None:
        """Add an item and restore heap order upward."""
        self._items.append(item)
        self._heapify_up(len(self._items) - 1)

    def pop(self) -> Optional[Any]:
        """Remove and return the smallest item, or None when empty."""
        if not self._items:
            return None
        root = self._items[0]
        last = self._items.pop()
        if self._items:
            self._items[0] = last
            self._heapify_down(0)
        return root

    def peek(self) -> Optional[Any]:
        """Return the smallest item without removing it."""
        if not self._items:
            return None
        return self._items[0]

    def size(self) -> int:
        return len(self._items)

    def _heapify_up(self, index: int) -> None:
        while index > 0:
            parent = (index - 1) // 2
            if self._items[parent] <= self._items[index]:
                return
            self._items[parent], self._items[index] = (
                self._items[index],
                self._items[parent],
            )
            index = parent

    def _heapify_down(self, index: int) -> None:
        size = len(self._items)
        while True:
            left = 2 * index + 1
            right = left + 1
            smallest = index
            if left < size and self._items[left] < self._items[smallest]:
                smallest = left
            if right < size and self._items[right] < self._items[smallest]:
                smallest = right
            if smallest == index:
                return
            self._items[index], self._items[smallest] = (
                self._items[smallest],
                self._items[index],
            )
            index = smallest
