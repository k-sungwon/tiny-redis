"""Parse Mini Redis commands and format Redis-style responses."""

import json
import shlex
from typing import Optional

from .store import MiniRedisStore


class CommandProcessor:
    """Translate one command line into a store operation and response."""

    def __init__(self, store: Optional[MiniRedisStore] = None) -> None:
        self.store = store if store is not None else MiniRedisStore()
        self.should_exit = False

    def execute(self, line: str) -> Optional[str]:
        try:
            tokens = shlex.split(line)
        except ValueError:
            return "(error) ERR syntax error"
        if not tokens:
            return None
        original_command = tokens[0]
        command = original_command.upper()

        if command in ("EXIT", "QUIT"):
            if len(tokens) != 1:
                return self._wrong_arity(command)
            self.should_exit = True
            return None

        if command == "SET":
            if len(tokens) != 3:
                return self._wrong_arity(command)
            if not self.store.set(tokens[1], tokens[2]):
                return "(error) OOM command not allowed when used_memory > 'maxmemory'"
            return "OK"

        if command == "GET":
            if len(tokens) != 2:
                return self._wrong_arity(command)
            value = self.store.get(tokens[1])
            return "(nil)" if value is None else self._quote(value)

        if command == "DEL":
            if len(tokens) != 2:
                return self._wrong_arity(command)
            return self._integer(self.store.delete(tokens[1]))

        if command == "EXISTS":
            if len(tokens) != 2:
                return self._wrong_arity(command)
            return self._integer(self.store.exists(tokens[1]))

        if command == "DBSIZE":
            if len(tokens) != 1:
                return self._wrong_arity(command)
            return self._integer(self.store.dbsize())

        if command == "KEYS":
            if len(tokens) != 1:
                return self._wrong_arity(command)
            keys = self.store.keys()
            if not keys:
                return "(empty array)"
            return "\n".join(
                "{}. {}".format(index, self._quote(key))
                for index, key in enumerate(keys, start=1)
            )

        if command == "CONFIG":
            if len(tokens) != 4:
                return self._wrong_arity(command)
            if tokens[1].upper() != "SET" or tokens[2].upper() != "MAXMEMORY":
                return "(error) ERR syntax error"
            maxmemory = self._parse_integer(tokens[3], nonnegative=True)
            if maxmemory is None:
                return "(error) ERR value is not an integer or out of range"
            self.store.configure_maxmemory(maxmemory)
            return "OK"

        if command == "INFO":
            if len(tokens) != 2:
                return self._wrong_arity(command)
            if tokens[1].upper() != "MEMORY":
                return "(error) ERR syntax error"
            used, maximum, evicted = self.store.info_memory()
            return "used_memory:{}\nmaxmemory:{}\nevicted_keys:{}".format(
                used, maximum, evicted
            )

        if command == "EXPIRE":
            if len(tokens) != 3:
                return self._wrong_arity(command)
            seconds = self._parse_integer(tokens[2])
            if seconds is None:
                return "(error) ERR value is not an integer or out of range"
            return self._integer(self.store.expire(tokens[1], seconds))

        if command == "TTL":
            if len(tokens) != 2:
                return self._wrong_arity(command)
            return self._integer(self.store.ttl(tokens[1]))

        return "(error) ERR unknown command '{}'".format(original_command)

    @staticmethod
    def _quote(value: str) -> str:
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def _integer(value: int) -> str:
        return "(integer) {}".format(value)

    @staticmethod
    def _wrong_arity(command: str) -> str:
        return "(error) ERR wrong number of arguments for '{}' command".format(command)

    @staticmethod
    def _parse_integer(value: str, nonnegative: bool = False) -> Optional[int]:
        try:
            parsed = int(value)
        except ValueError:
            return None
        if parsed < -(2**63) or parsed > 2**63 - 1:
            return None
        if nonnegative and parsed < 0:
            return None
        return parsed
