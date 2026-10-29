import unittest

from mini_redis.doubly_linked_list import DoublyLinkedList


class DoublyLinkedListInsertionTests(unittest.TestCase):
    def test_new_list_is_empty(self):
        linked_list = DoublyLinkedList()

        self.assertEqual(0, len(linked_list))
        self.assertEqual([], list(linked_list.iter_nodes()))

    def test_insert_front_returns_node_and_updates_length(self):
        linked_list = DoublyLinkedList()

        node = linked_list.insert_front("a")

        self.assertEqual("a", node.data)
        self.assertEqual(1, len(linked_list))

    def test_front_and_back_insertion_preserve_expected_order(self):
        linked_list = DoublyLinkedList()

        linked_list.insert_front("b")
        linked_list.insert_front("a")
        linked_list.insert_back("c")

        self.assertEqual(
            ["a", "b", "c"],
            [node.data for node in linked_list.iter_nodes()],
        )


class DoublyLinkedListRemovalTests(unittest.TestCase):
    def test_remove_from_empty_list_returns_none(self):
        linked_list = DoublyLinkedList()

        self.assertIsNone(linked_list.remove_front())
        self.assertIsNone(linked_list.remove_back())
        self.assertEqual(0, len(linked_list))

    def test_remove_front_and_back_update_order_and_length(self):
        linked_list = DoublyLinkedList()
        linked_list.insert_back("a")
        linked_list.insert_back("b")
        linked_list.insert_back("c")

        self.assertEqual("a", linked_list.remove_front())
        self.assertEqual("c", linked_list.remove_back())
        self.assertEqual(["b"], [node.data for node in linked_list.iter_nodes()])
        self.assertEqual(1, len(linked_list))
        self.assertEqual("b", linked_list.remove_back())
        self.assertEqual(0, len(linked_list))

    def test_remove_middle_node_repairs_neighbor_links(self):
        linked_list = DoublyLinkedList()
        first = linked_list.insert_back("a")
        middle = linked_list.insert_back("b")
        last = linked_list.insert_back("c")

        removed = linked_list.remove_node(middle)

        self.assertEqual("b", removed)
        self.assertIs(first.next, last)
        self.assertIs(last.prev, first)
        self.assertIsNone(middle.prev)
        self.assertIsNone(middle.next)
        self.assertEqual(2, len(linked_list))

    def test_move_to_front_handles_back_middle_and_front_nodes(self):
        linked_list = DoublyLinkedList()
        first = linked_list.insert_back("a")
        middle = linked_list.insert_back("b")
        last = linked_list.insert_back("c")

        linked_list.move_to_front(last)
        self.assertEqual(
            ["c", "a", "b"],
            [node.data for node in linked_list.iter_nodes()],
        )

        linked_list.move_to_front(middle)
        self.assertEqual(
            ["b", "c", "a"],
            [node.data for node in linked_list.iter_nodes()],
        )

        linked_list.move_to_front(middle)
        self.assertEqual(
            ["b", "c", "a"],
            [node.data for node in linked_list.iter_nodes()],
        )
        self.assertEqual(3, len(linked_list))
        self.assertEqual("c", first.prev.data)


if __name__ == "__main__":
    unittest.main()
