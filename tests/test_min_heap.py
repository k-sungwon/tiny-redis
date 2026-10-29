import unittest

from mini_redis.min_heap import MinHeap


class MinHeapTests(unittest.TestCase):
    def test_empty_heap_returns_none(self):
        heap = MinHeap()

        self.assertEqual(0, heap.size())
        self.assertIsNone(heap.peek())
        self.assertIsNone(heap.pop())

    def test_single_item_can_be_peeked_and_popped(self):
        heap = MinHeap()
        heap.push(7)

        self.assertEqual(7, heap.peek())
        self.assertEqual(1, heap.size())
        self.assertEqual(7, heap.pop())
        self.assertEqual(0, heap.size())

    def test_unsorted_values_pop_in_ascending_order(self):
        heap = MinHeap()
        for value in (8, 3, 10, 1, 6, 2, 9, 4, 7, 5):
            heap.push(value)

        self.assertEqual(list(range(1, 11)), [heap.pop() for _ in range(10)])

    def test_tuple_tokens_order_equal_expiration_times(self):
        heap = MinHeap()
        later_token = (10.0, 2, "b")
        earlier_token = (10.0, 1, "a")

        heap.push(later_token)
        heap.push(earlier_token)

        self.assertEqual(earlier_token, heap.pop())
        self.assertEqual(later_token, heap.pop())


if __name__ == "__main__":
    unittest.main()
