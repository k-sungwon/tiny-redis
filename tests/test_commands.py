import unittest

from mini_redis.cli import run_repl
from mini_redis.command_processor import CommandProcessor
from mini_redis.store import MiniRedisStore


class FakeClock:
    def __init__(self, current=100.0):
        self.current = current

    def __call__(self):
        return self.current


class CommandProcessorHappyPathTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.store = MiniRedisStore(clock=self.clock)
        self.processor = CommandProcessor(self.store)

    def test_string_commands_and_database_size(self):
        self.assertEqual("OK", self.processor.execute("SET user:1 Alice"))
        self.assertEqual('"Alice"', self.processor.execute("GET user:1"))
        self.assertEqual("(integer) 1", self.processor.execute("EXISTS user:1"))
        self.assertEqual("(integer) 1", self.processor.execute("DBSIZE"))
        self.assertEqual("(integer) 1", self.processor.execute("DEL user:1"))
        self.assertEqual("(nil)", self.processor.execute("GET user:1"))
        self.assertEqual("(empty array)", self.processor.execute("KEYS"))

    def test_ttl_commands(self):
        self.processor.execute("SET user:1 Alice")

        self.assertEqual("(integer) 1", self.processor.execute("EXPIRE user:1 3"))
        self.assertEqual("(integer) 3", self.processor.execute("TTL user:1"))

    def test_memory_commands(self):
        self.assertEqual(
            "OK",
            self.processor.execute("CONFIG SET maxmemory 30"),
        )

        self.assertEqual(
            "used_memory:0\nmaxmemory:30\nevicted_keys:0",
            self.processor.execute("INFO memory"),
        )

    def test_commands_and_fixed_subcommands_are_case_insensitive(self):
        self.assertEqual(
            "OK",
            self.processor.execute("config set MAXMEMORY 30"),
        )
        self.assertEqual("OK", self.processor.execute("set User:1 Alice"))
        self.assertEqual('"Alice"', self.processor.execute("get User:1"))
        self.assertEqual(
            "used_memory:11\nmaxmemory:30\nevicted_keys:0",
            self.processor.execute("info MEMORY"),
        )


class CommandProcessorValidationTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.store = MiniRedisStore(clock=self.clock)
        self.processor = CommandProcessor(self.store)

    def test_blank_input_and_quoted_values_with_spaces(self):
        self.assertIsNone(self.processor.execute("   "))
        self.assertEqual("OK", self.processor.execute('SET greeting "안녕 세계"'))
        self.assertEqual('"안녕 세계"', self.processor.execute("GET greeting"))
        self.assertEqual("OK", self.processor.execute('SET empty ""'))
        self.assertEqual('""', self.processor.execute("GET empty"))

    def test_get_and_keys_use_json_style_escaping(self):
        value = 'quote " slash \\ tab\t line\n한글'
        self.store.set('key"\\', value)

        self.assertEqual(
            '"quote \\" slash \\\\ tab\\t line\\n한글"',
            self.processor.execute('GET "key\\\"\\\\"'),
        )
        self.assertEqual('1. "key\\\"\\\\"', self.processor.execute("KEYS"))

    def test_malformed_quoting_returns_syntax_error(self):
        self.assertEqual(
            "(error) ERR syntax error",
            self.processor.execute('SET key "unterminated'),
        )

    def test_unknown_command_and_wrong_arities(self):
        self.assertEqual(
            "(error) ERR unknown command 'HELLO'",
            self.processor.execute("HELLO"),
        )
        cases = (
            ("SET key", "SET"),
            ("GET", "GET"),
            ("DEL", "DEL"),
            ("EXISTS", "EXISTS"),
            ("DBSIZE extra", "DBSIZE"),
            ("KEYS extra", "KEYS"),
            ("CONFIG SET maxmemory", "CONFIG"),
            ("INFO", "INFO"),
            ("EXPIRE key", "EXPIRE"),
            ("TTL", "TTL"),
        )
        for line, command in cases:
            with self.subTest(line=line):
                self.assertEqual(
                    "(error) ERR wrong number of arguments for '{}' command".format(
                        command
                    ),
                    self.processor.execute(line),
                )

    def test_invalid_and_out_of_range_integers(self):
        error = "(error) ERR value is not an integer or out of range"
        self.store.set("a", "1")

        self.assertEqual(error, self.processor.execute("CONFIG SET maxmemory abc"))
        self.assertEqual(error, self.processor.execute("CONFIG SET maxmemory -1"))
        self.assertEqual(error, self.processor.execute("EXPIRE a abc"))
        self.assertEqual(error, self.processor.execute("EXPIRE a 9223372036854775808"))
        self.assertEqual(error, self.processor.execute("EXPIRE a -9223372036854775809"))

    def test_invalid_fixed_subcommands_return_syntax_error(self):
        self.assertEqual(
            "(error) ERR syntax error",
            self.processor.execute("CONFIG GET maxmemory 10"),
        )
        self.assertEqual(
            "(error) ERR syntax error",
            self.processor.execute("INFO clients"),
        )

    def test_non_positive_expire_deletes_immediately(self):
        self.processor.execute("SET a 1")

        self.assertEqual("(integer) 1", self.processor.execute("EXPIRE a -1"))
        self.assertEqual("(nil)", self.processor.execute("GET a"))

    def test_oom_error_is_exact_and_preserves_existing_state(self):
        self.processor.execute("CONFIG SET maxmemory 5")
        self.processor.execute("SET a 1")

        self.assertEqual(
            "(error) OOM command not allowed when used_memory > 'maxmemory'",
            self.processor.execute("SET large value"),
        )
        self.assertEqual('"1"', self.processor.execute("GET a"))

    def test_invalid_command_does_not_mutate_store(self):
        self.processor.execute("SET a 1")
        before = (self.store.keys(), self.store.info_memory())

        self.processor.execute("SET only-key")
        self.processor.execute("CONFIG SET maxmemory invalid")

        self.assertEqual(before, (self.store.keys(), self.store.info_memory()))

    def test_exit_and_quit_set_exit_flag(self):
        self.assertFalse(self.processor.should_exit)
        self.assertIsNone(self.processor.execute("QuIt"))
        self.assertTrue(self.processor.should_exit)


class ReplTests(unittest.TestCase):
    def test_repl_prompts_executes_and_stops_on_quit(self):
        lines = iter(("SET a 1", "GET a", "quit"))
        prompts = []
        outputs = []

        def input_fn(prompt):
            prompts.append(prompt)
            return next(lines)

        run_repl(input_fn=input_fn, output_fn=outputs.append)

        self.assertEqual(["mini-redis> "] * 3, prompts)
        self.assertEqual(["OK", '"1"'], outputs)

    def test_blank_input_prints_nothing(self):
        lines = iter(("", "exit"))
        outputs = []

        run_repl(input_fn=lambda prompt: next(lines), output_fn=outputs.append)

        self.assertEqual([], outputs)

    def test_eof_exits_cleanly(self):
        def input_fn(prompt):
            raise EOFError

        run_repl(input_fn=input_fn, output_fn=lambda output: self.fail(output))

    def test_keyboard_interrupt_exits_cleanly(self):
        def input_fn(prompt):
            raise KeyboardInterrupt

        run_repl(input_fn=input_fn, output_fn=lambda output: self.fail(output))


if __name__ == "__main__":
    unittest.main()
