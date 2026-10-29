import unittest

from mini_redis.hash_map import HashMap


class HashMapBasicTests(unittest.TestCase):
    def test_empty_map_reports_missing_values(self):
        hash_map = HashMap()

        self.assertEqual(0, hash_map.size())
        self.assertEqual([], hash_map.keys())
        self.assertFalse(hash_map.contains("missing"))
        self.assertIsNone(hash_map.get("missing"))
        self.assertEqual("fallback", hash_map.get("missing", "fallback"))
        self.assertIsNone(hash_map.remove("missing"))

    def test_put_and_get_distinct_keys(self):
        hash_map = HashMap()

        hash_map.put("user:1", "Alice")
        hash_map.put("user:2", "Bob")

        self.assertEqual("Alice", hash_map.get("user:1"))
        self.assertEqual("Bob", hash_map.get("user:2"))
        self.assertTrue(hash_map.contains("user:1"))
        self.assertEqual(2, hash_map.size())
        self.assertCountEqual(["user:1", "user:2"], hash_map.keys())

    def test_updating_key_does_not_increase_size(self):
        hash_map = HashMap()
        hash_map.put("user:1", "Alice")

        hash_map.put("user:1", "Alicia")

        self.assertEqual("Alicia", hash_map.get("user:1"))
        self.assertEqual(1, hash_map.size())


class HashMapCollisionAndResizeTests(unittest.TestCase):
    def test_collision_chain_preserves_other_keys_when_one_is_removed(self):
        hash_map = HashMap(initial_capacity=4)
        self.assertEqual(hash_map._hash("a") % 4, hash_map._hash("e") % 4)
        self.assertEqual(hash_map._hash("e") % 4, hash_map._hash("i") % 4)
        hash_map.put("a", 1)
        hash_map.put("e", 2)
        hash_map.put("i", 3)

        self.assertEqual(2, hash_map.remove("e"))

        self.assertEqual(1, hash_map.get("a"))
        self.assertEqual(3, hash_map.get("i"))
        self.assertFalse(hash_map.contains("e"))

    def test_exact_load_factor_boundary_does_not_resize(self):
        hash_map = HashMap(initial_capacity=4)

        hash_map.put("a", 1)
        hash_map.put("b", 2)
        hash_map.put("c", 3)

        self.assertEqual(3, hash_map.size())
        self.assertEqual(4, hash_map.capacity)

    def test_next_new_key_doubles_capacity_and_rehashes_all_values(self):
        hash_map = HashMap(initial_capacity=4)
        for key, value in (("a", 1), ("b", 2), ("c", 3), ("d", 4)):
            hash_map.put(key, value)

        self.assertEqual(8, hash_map.capacity)
        self.assertEqual(4, hash_map.size())
        for key, value in (("a", 1), ("b", 2), ("c", 3), ("d", 4)):
            self.assertEqual(value, hash_map.get(key))

    def test_update_at_boundary_does_not_resize(self):
        hash_map = HashMap(initial_capacity=4)
        hash_map.put("a", 1)
        hash_map.put("b", 2)
        hash_map.put("c", 3)

        hash_map.put("a", 10)

        self.assertEqual(4, hash_map.capacity)
        self.assertEqual(3, hash_map.size())
        self.assertEqual(10, hash_map.get("a"))

    def test_empty_string_is_a_present_value(self):
        hash_map = HashMap()

        hash_map.put("empty", "")

        self.assertTrue(hash_map.contains("empty"))
        self.assertEqual("", hash_map.get("empty"))

    def test_remove_returns_value_and_removes_only_target_key(self):
        hash_map = HashMap()
        hash_map.put("user:1", "Alice")
        hash_map.put("user:2", "Bob")

        removed = hash_map.remove("user:1")

        self.assertEqual("Alice", removed)
        self.assertFalse(hash_map.contains("user:1"))
        self.assertEqual("Bob", hash_map.get("user:2"))
        self.assertEqual(1, hash_map.size())


if __name__ == "__main__":
    unittest.main()
