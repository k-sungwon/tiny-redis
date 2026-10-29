import unittest

from mini_redis.store import MiniRedisStore


def lru_keys(store):
    return [node.data.key for node in store._lru.iter_nodes()]


class FakeClock:
    def __init__(self, current=100.0):
        self.current = current

    def __call__(self):
        return self.current

    def advance(self, seconds):
        self.current += seconds


class MiniRedisStoreBasicTests(unittest.TestCase):
    def test_set_get_exists_delete_and_dbsize(self):
        store = MiniRedisStore()

        self.assertTrue(store.set("user:1", "Alice"))
        self.assertEqual("Alice", store.get("user:1"))
        self.assertIsNone(store.get("missing"))
        self.assertEqual(1, store.exists("user:1"))
        self.assertEqual(1, store.dbsize())
        self.assertEqual(1, store.delete("user:1"))
        self.assertEqual(0, store.delete("user:1"))
        self.assertEqual(0, store.dbsize())

    def test_keys_returns_all_current_keys(self):
        store = MiniRedisStore()
        store.set("user:1", "Alice")
        store.set("user:2", "Bob")

        self.assertCountEqual(["user:1", "user:2"], store.keys())

    def test_successful_get_moves_entry_to_lru_front(self):
        store = MiniRedisStore()
        store.set("a", "1")
        store.set("b", "2")
        store.set("c", "3")
        self.assertEqual(["c", "b", "a"], lru_keys(store))

        self.assertEqual("1", store.get("a"))

        self.assertEqual(["a", "c", "b"], lru_keys(store))

    def test_missing_get_and_exists_do_not_change_lru_order(self):
        store = MiniRedisStore()
        store.set("a", "1")
        store.set("b", "2")

        self.assertIsNone(store.get("missing"))
        self.assertEqual(0, store.exists("missing"))

        self.assertEqual(["b", "a"], lru_keys(store))

    def test_initial_memory_info_and_configuration(self):
        store = MiniRedisStore()

        self.assertEqual((0, 0, 0), store.info_memory())
        store.configure_maxmemory(30)
        self.assertEqual((0, 30, 0), store.info_memory())


class MiniRedisMemoryTests(unittest.TestCase):
    def test_memory_uses_exact_utf8_byte_lengths_and_delete_subtracts(self):
        store = MiniRedisStore()

        store.set("a", "1")
        store.set("키", "값")

        self.assertEqual((8, 0, 0), store.info_memory())
        store.delete("키")
        self.assertEqual((2, 0, 0), store.info_memory())

    def test_zero_maxmemory_is_unlimited(self):
        store = MiniRedisStore()

        self.assertTrue(store.set("large", "x" * 1000))

        self.assertEqual(1, store.dbsize())
        self.assertEqual(1005, store.used_memory)
        self.assertEqual(0, store.evicted_keys)

    def test_assignment_scenario_evicts_least_recently_used_key(self):
        store = MiniRedisStore()
        store.configure_maxmemory(30)
        store.set("menu:a", "pizza")
        store.set("menu:b", "burger")
        store.get("menu:a")

        self.assertTrue(store.set("menu:c", "pasta"))

        self.assertIsNone(store.get("menu:b"))
        self.assertEqual("pizza", store.get("menu:a"))
        self.assertEqual("pasta", store.get("menu:c"))
        self.assertEqual((22, 30, 1), store.info_memory())

    def test_one_write_can_evict_multiple_old_keys(self):
        store = MiniRedisStore()
        store.configure_maxmemory(12)
        store.set("a", "111")
        store.set("b", "222")
        store.set("c", "333")
        store.get("a")

        self.assertTrue(store.set("d", "1234567"))

        self.assertCountEqual(["a", "d"], store.keys())
        self.assertEqual(["d", "a"], lru_keys(store))
        self.assertEqual((12, 12, 2), store.info_memory())

    def test_overwrite_replaces_old_memory_size_without_growing_db(self):
        store = MiniRedisStore()
        store.set("a", "1")

        self.assertTrue(store.set("a", "123"))

        self.assertEqual("123", store.get("a"))
        self.assertEqual(1, store.dbsize())
        self.assertEqual(4, store.used_memory)

    def test_lowered_limit_is_enforced_by_next_set_not_configuration(self):
        store = MiniRedisStore()
        store.set("a", "111")
        store.set("b", "222")

        store.configure_maxmemory(4)
        self.assertEqual(8, store.used_memory)
        self.assertEqual(2, store.dbsize())
        store.set("c", "3")

        self.assertEqual(["c"], store.keys())
        self.assertEqual((2, 4, 2), store.info_memory())

    def test_oversized_new_entry_is_rejected_without_state_change(self):
        store = MiniRedisStore()
        store.configure_maxmemory(5)
        store.set("a", "1")
        before = (store.keys(), lru_keys(store), store.info_memory())

        self.assertFalse(store.set("large", "value"))

        self.assertEqual(before, (store.keys(), lru_keys(store), store.info_memory()))

    def test_oversized_replacement_preserves_value_ttl_lru_and_counters(self):
        store = MiniRedisStore(clock=FakeClock())
        store.configure_maxmemory(5)
        store.set("a", "1")
        entry = store._entries.get("a")
        entry.expire_at = 123.0
        entry.ttl_token = 7
        before = (lru_keys(store), store.info_memory())

        self.assertFalse(store.set("a", "12345"))

        current = store._entries.get("a")
        self.assertEqual("1", current.value)
        self.assertEqual(123.0, current.expire_at)
        self.assertEqual(7, current.ttl_token)
        self.assertEqual(before, (lru_keys(store), store.info_memory()))


class MiniRedisTTLTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.store = MiniRedisStore(clock=self.clock)

    def test_missing_key_expire_and_ttl_codes(self):
        self.assertEqual(0, self.store.expire("missing", 3))
        self.assertEqual(-2, self.store.ttl("missing"))

    def test_key_without_expiration_has_minus_one_ttl(self):
        self.store.set("a", "1")

        self.assertEqual(-1, self.store.ttl("a"))

    def test_non_positive_expiration_deletes_existing_key_immediately(self):
        self.store.set("zero", "1")
        self.store.set("negative", "2")

        self.assertEqual(1, self.store.expire("zero", 0))
        self.assertEqual(1, self.store.expire("negative", -5))

        self.assertEqual(0, self.store.dbsize())
        self.assertEqual(0, self.store.used_memory)

    def test_ttl_uses_ceiling_and_expires_at_boundary(self):
        self.store.set("a", "1")
        self.assertEqual(1, self.store.expire("a", 3))

        self.assertEqual(3, self.store.ttl("a"))
        self.clock.advance(2.2)
        self.assertEqual(1, self.store.ttl("a"))
        self.clock.advance(0.8)
        self.assertEqual(-2, self.store.ttl("a"))
        self.assertIsNone(self.store.get("a"))

    def test_expired_get_removes_entry_without_refresh_or_eviction_count(self):
        self.store.set("a", "1")
        self.store.set("b", "2")
        self.store.expire("a", 1)
        self.clock.advance(1)

        self.assertIsNone(self.store.get("a"))

        self.assertEqual(["b"], lru_keys(self.store))
        self.assertEqual(0, self.store.evicted_keys)

    def test_database_wide_commands_purge_expired_heap_roots(self):
        self.store.set("a", "1")
        self.store.set("b", "2")
        self.store.expire("a", 1)
        self.clock.advance(1)

        self.assertEqual(1, self.store.dbsize())
        self.assertEqual(["b"], self.store.keys())
        self.assertEqual((2, 0, 0), self.store.info_memory())

    def test_repeated_expire_ignores_old_heap_record(self):
        self.store.set("a", "1")
        self.store.expire("a", 10)
        self.clock.advance(5)
        self.store.expire("a", 30)

        self.clock.advance(5)

        self.assertEqual(1, self.store.dbsize())
        self.assertEqual(25, self.store.ttl("a"))

    def test_set_clears_ttl_and_old_heap_record_cannot_delete_value(self):
        self.store.set("a", "old")
        self.store.expire("a", 1)

        self.store.set("a", "new")
        self.clock.advance(1)

        self.assertEqual(1, self.store.dbsize())
        self.assertEqual("new", self.store.get("a"))
        self.assertEqual(-1, self.store.ttl("a"))

    def test_delete_and_recreate_same_key_survives_old_expiration(self):
        self.store.set("a", "old")
        self.store.expire("a", 1)
        self.store.delete("a")
        self.store.set("a", "new")

        self.clock.advance(1)

        self.assertEqual(1, self.store.dbsize())
        self.assertEqual("new", self.store.get("a"))

    def test_evicted_and_recreated_key_survives_old_expiration(self):
        self.store.configure_maxmemory(4)
        self.store.set("a", "1")
        self.store.expire("a", 1)
        self.store.set("b", "22")
        self.assertEqual(0, self.store.exists("a"))
        self.store.set("a", "1")

        self.clock.advance(1)

        self.assertEqual(1, self.store.dbsize())
        self.assertEqual("1", self.store.get("a"))
        self.assertEqual(2, self.store.evicted_keys)

    def test_set_purges_expired_recent_key_before_evicting_live_lru(self):
        self.store.configure_maxmemory(4)
        self.store.set("a", "1")
        self.store.set("b", "1")
        self.store.expire("b", 1)
        self.clock.advance(1)

        self.assertTrue(self.store.set("c", "1"))

        self.assertCountEqual(["a", "c"], self.store.keys())
        self.assertEqual((4, 4, 0), self.store.info_memory())

    def test_set_purges_expired_lru_key_without_counting_eviction(self):
        self.store.configure_maxmemory(4)
        self.store.set("a", "1")
        self.store.set("b", "1")
        self.store.expire("a", 1)
        self.clock.advance(1)

        self.assertTrue(self.store.set("c", "1"))

        self.assertCountEqual(["b", "c"], self.store.keys())
        self.assertEqual((4, 4, 0), self.store.info_memory())


if __name__ == "__main__":
    unittest.main()
