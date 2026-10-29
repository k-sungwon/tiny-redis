# Mini Redis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a tested Python 3.8+ CLI Mini Redis that uses a custom chaining hash map, doubly linked LRU list, and min-heap TTL manager.

**Architecture:** Keep each required data structure in its own package module, then compose them in `MiniRedisStore`. A separate command processor owns parsing and Redis-style formatting, while a thin CLI owns the REPL loop.

**Tech Stack:** Python 3.8+, standard library only, `unittest`, `shlex`, `json`, `time`

**Spec:** `docs/superpowers/specs/2026-10-29-mini-redis-design.md`

## Global Constraints

- Python 3.8 or newer; use `typing.Optional`, not Python 3.10 union syntax.
- Standard library only.
- Do not use `dict`, `set`, `heapq`, `OrderedDict`, or a third-party cache as a substitute for the required structures.
- Python lists are allowed only as indexed backing storage for hash buckets, heap items, and returned key collections.
- Hash-map bucket collisions use the custom doubly linked list.
- Memory is `sum(len(key.encode("utf-8")) + len(value.encode("utf-8")))`.
- Commands use signed 64-bit integers; `maxmemory` additionally requires a non-negative value.
- Bonus features, networking, persistence, complex Redis types, and concurrency remain out of scope.
- Every implementation step follows red-green-refactor: observe the new test fail before adding production behavior.

## Review Focus

- Unicode and values containing quotes, backslashes, tabs, or newlines must have correct UTF-8 accounting and JSON-style output escaping; Task 6 pins this.
- Repeated expiration, overwrite, delete/recreate, and stale heap records must never expire the wrong entry; Task 5 pins this.
- OOM replacement must be atomic, while a fitting write may evict multiple old keys in exact LRU order; Task 4 pins this.
- Hash-map collision chains and the exact `0.75` versus greater-than-`0.75` resize boundary must preserve every key; Task 2 pins this.
- Empty input, malformed quotes, wrong arity, negative `maxmemory`, and signed 64-bit overflow must produce stable errors without mutating state; Task 6 pins this.

---

## File Map

- `mini_redis/__init__.py`: package exports.
- `mini_redis/doubly_linked_list.py`: `Node` and `DoublyLinkedList`.
- `mini_redis/hash_map.py`: `MapEntry` and `HashMap` with chaining and resizing.
- `mini_redis/min_heap.py`: array-backed `MinHeap`.
- `mini_redis/store.py`: `CacheEntry`, memory/LRU/TTL state, and storage operations.
- `mini_redis/command_processor.py`: parsing, validation, command dispatch, and response formatting.
- `mini_redis/cli.py`: interactive REPL.
- `main.py`: executable entry point.
- `tests/`: one focused module per component plus command integration tests.
- `README.md`: usage and explanation.

### Task 1: Doubly linked list foundation

**Files:**
- Create: `mini_redis/__init__.py`
- Create: `mini_redis/doubly_linked_list.py`
- Create: `tests/__init__.py`
- Create: `tests/test_doubly_linked_list.py`

**Interfaces:**
- Consumes: none.
- Produces: `Node(data: Any)` with `prev`, `next`, `data`; `DoublyLinkedList.insert_front`, `insert_back`, `remove_front`, `remove_back`, `remove_node`, `move_to_front`, `iter_nodes`, and `__len__`.

- [ ] **Step 1: Write failing construction and insertion tests**

Add tests asserting a new list has length zero, front/back removal returns `None`, `insert_front("a")` returns a node with `data == "a"`, and front/back insertion yields `a, b, c` in the expected order through `iter_nodes()`.

- [ ] **Step 2: Run the tests and observe failure**

Run: `python -m unittest tests.test_doubly_linked_list -v`

Expected: FAIL because `mini_redis.doubly_linked_list` does not exist.

- [ ] **Step 3: Implement nodes, sentinels, insertion, iteration, and length**

Implement Python 3.8-compatible signatures:

```python
class Node:
    def __init__(self, data: Any) -> None: ...

class DoublyLinkedList:
    def insert_front(self, data: Any) -> Node: ...
    def insert_back(self, data: Any) -> Node: ...
    def iter_nodes(self) -> Iterator[Node]: ...
    def __len__(self) -> int: ...
```

Use private head and tail sentinels and maintain a private length.

- [ ] **Step 4: Run the focused tests and observe pass**

Run: `python -m unittest tests.test_doubly_linked_list -v`

Expected: PASS for construction and insertion tests.

- [ ] **Step 5: Write failing removal and movement tests**

Add tests asserting front/back removal on one and many nodes, middle-node removal, `move_to_front` from middle/back/already-front, correct neighbor links, and length after every operation.

- [ ] **Step 6: Run the new tests and observe failure**

Run: `python -m unittest tests.test_doubly_linked_list -v`

Expected: FAIL because removal and movement are not implemented.

- [ ] **Step 7: Implement removal and movement**

Add:

```python
def remove_front(self) -> Optional[Any]: ...
def remove_back(self) -> Optional[Any]: ...
def remove_node(self, node: Node) -> Any: ...
def move_to_front(self, node: Node) -> None: ...
```

Each operation changes a constant number of links; `move_to_front` must not change length.

- [ ] **Step 8: Run the focused tests**

Run: `python -m unittest tests.test_doubly_linked_list -v`

Expected: all linked-list tests PASS.

- [ ] **Step 9: Commit the independently working list**

```bash
git add mini_redis/__init__.py mini_redis/doubly_linked_list.py tests/__init__.py tests/test_doubly_linked_list.py
git commit -m "feat: implement doubly linked list"
```

### Task 2: Chaining hash map

**Files:**
- Create: `mini_redis/hash_map.py`
- Create: `tests/test_hash_map.py`
- Modify: `mini_redis/__init__.py`

**Interfaces:**
- Consumes: Task 1 `DoublyLinkedList.insert_back`, `remove_node`, and `iter_nodes`.
- Produces: `HashMap(initial_capacity: int = 8)`, `put(key: str, value: Any) -> None`, `get(key: str, default: Any = None) -> Any`, `remove(key: str, default: Any = None) -> Any`, `contains(key: str) -> bool`, `keys() -> List[str]`, `size() -> int`, and read-only `capacity`.

- [ ] **Step 1: Write failing basic map tests**

Test empty `size/keys/contains/get/remove`, insertion, update without size growth, empty-string values, removal, and distinct keys.

- [ ] **Step 2: Run and observe failure**

Run: `python -m unittest tests.test_hash_map -v`

Expected: FAIL because `HashMap` does not exist.

- [ ] **Step 3: Implement entry, hashing, and basic operations**

Add:

```python
class MapEntry:
    def __init__(self, key: str, value: Any) -> None: ...

class HashMap:
    def __init__(self, initial_capacity: int = 8) -> None: ...
    def _hash(self, key: str) -> int: ...
    def put(self, key: str, value: Any) -> None: ...
    def get(self, key: str, default: Any = None) -> Any: ...
    def remove(self, key: str, default: Any = None) -> Any: ...
    def contains(self, key: str) -> bool: ...
    def keys(self) -> List[str]: ...
    def size(self) -> int: ...
    @property
    def capacity(self) -> int: ...
```

Use the polynomial UTF-8 hash `(value * 31 + byte) & 0xFFFFFFFFFFFFFFFF`; each occupied bucket owns its own `DoublyLinkedList` of `MapEntry` objects.

- [ ] **Step 4: Run basic map tests**

Run: `python -m unittest tests.test_hash_map -v`

Expected: basic tests PASS.

- [ ] **Step 5: Write failing collision and resize tests**

Use a small initial capacity and programmatically find colliding keys. Assert all collision-chain keys remain accessible after one is removed. Assert `size/capacity == 0.75` does not resize, the next new insertion doubles capacity, updates do not resize, and every value survives rehashing.

- [ ] **Step 6: Run and observe resize failure**

Run: `python -m unittest tests.test_hash_map -v`

Expected: FAIL on resize assertions.

- [ ] **Step 7: Implement load-factor resizing and rehashing**

Add `_resize(new_capacity: int) -> None`. Create a fresh bucket list, recompute each entry's index using the new capacity, and insert entries without recursively applying the public resize threshold.

- [ ] **Step 8: Run linked-list and map tests**

Run: `python -m unittest tests.test_doubly_linked_list tests.test_hash_map -v`

Expected: all tests PASS.

- [ ] **Step 9: Commit the custom hash map**

```bash
git add mini_redis/hash_map.py mini_redis/__init__.py tests/test_hash_map.py
git commit -m "feat: implement chaining hash map"
```

### Task 3: TTL min-heap

**Files:**
- Create: `mini_redis/min_heap.py`
- Create: `tests/test_min_heap.py`
- Modify: `mini_redis/__init__.py`

**Interfaces:**
- Consumes: Python-list indexed backing storage permitted by the spec.
- Produces: `MinHeap.push(item: Any) -> None`, `peek() -> Optional[Any]`, `pop() -> Optional[Any]`, `size() -> int`, `_heapify_up(index: int) -> None`, and `_heapify_down(index: int) -> None`.

- [ ] **Step 1: Write failing heap tests**

Test empty `peek/pop/size`, ascending pop order after unsorted pushes, one-element behavior, duplicate first tuple fields `(10.0, 1, "a")` and `(10.0, 2, "b")`, and sequences that require multiple upward and downward swaps.

- [ ] **Step 2: Run and observe failure**

Run: `python -m unittest tests.test_min_heap -v`

Expected: FAIL because `MinHeap` does not exist.

- [ ] **Step 3: Implement the heap**

Implement:

```python
class MinHeap:
    def push(self, item: Any) -> None: ...
    def pop(self) -> Optional[Any]: ...
    def peek(self) -> Optional[Any]: ...
    def size(self) -> int: ...
    def _heapify_up(self, index: int) -> None: ...
    def _heapify_down(self, index: int) -> None: ...
```

Compare items with normal tuple ordering. In `_heapify_down`, choose the smaller child before deciding whether to swap.

- [ ] **Step 4: Run heap and prior structure tests**

Run: `python -m unittest tests.test_min_heap tests.test_hash_map tests.test_doubly_linked_list -v`

Expected: all tests PASS.

- [ ] **Step 5: Commit the min-heap**

```bash
git add mini_redis/min_heap.py mini_redis/__init__.py tests/test_min_heap.py
git commit -m "feat: implement min heap"
```

### Task 4: Core store, memory accounting, and LRU eviction

**Files:**
- Create: `mini_redis/store.py`
- Create: `tests/test_store.py`
- Modify: `mini_redis/__init__.py`

**Interfaces:**
- Consumes: `HashMap`, `DoublyLinkedList`, and `MinHeap` from Tasks 1-3.
- Produces: `CacheEntry`; `MiniRedisStore(clock: Callable[[], float] = time.time)`; `set`, `get`, `delete`, `exists`, `dbsize`, `keys`, `configure_maxmemory`, and `info_memory`.

- [ ] **Step 1: Write failing basic store tests**

Assert:

```python
store.set("user:1", "Alice") is True
store.get("user:1") == "Alice"
store.get("missing") is None
store.exists("user:1") == 1
store.delete("user:1") == 1
store.delete("user:1") == 0
store.dbsize() == 0
```

Also assert `keys()` contains all current keys, successful `GET` moves an entry to the LRU front, and missing `GET/EXISTS` does not alter order.

- [ ] **Step 2: Run and observe failure**

Run: `python -m unittest tests.test_store -v`

Expected: FAIL because the store does not exist.

- [ ] **Step 3: Implement cache entries and basic store operations**

Implement:

```python
class CacheEntry:
    def __init__(self, key: str, value: str) -> None: ...

class MiniRedisStore:
    def __init__(self, clock: Callable[[], float] = time.time) -> None: ...
    def set(self, key: str, value: str) -> bool: ...
    def get(self, key: str) -> Optional[str]: ...
    def delete(self, key: str) -> int: ...
    def exists(self, key: str) -> int: ...
    def dbsize(self) -> int: ...
    def keys(self) -> List[str]: ...
    def configure_maxmemory(self, maxmemory: int) -> None: ...
    def info_memory(self) -> Tuple[int, int, int]: ...
```

`CacheEntry` fields are `key`, `value`, `lru_node`, `expire_at`, and `ttl_token`. Initialize store counters to zero and keep the LRU front as most recently used.

- [ ] **Step 4: Run basic store tests**

Run: `python -m unittest tests.test_store -v`

Expected: basic storage and LRU movement tests PASS.

- [ ] **Step 5: Write failing memory and eviction tests**

Test exact ASCII and Korean UTF-8 byte counts, unlimited memory, the assignment's 30-byte scenario, successful `GET` changing the next eviction target, multiple evictions, eviction count, overwrite size adjustment, and lowered configuration taking effect on the next `SET`.

Add atomic OOM tests asserting an oversized new key changes nothing and an oversized replacement preserves the old value, TTL placeholders, LRU order, `used_memory`, and `evicted_keys`.

- [ ] **Step 6: Run and observe memory-policy failure**

Run: `python -m unittest tests.test_store -v`

Expected: FAIL on accounting, eviction, and OOM cases.

- [ ] **Step 7: Implement memory helpers and eviction**

Add private helpers `_entry_size(key: str, value: str) -> int`, `_delete_entry(entry: CacheEntry, evicted: bool = False) -> None`, and `_evict_until_within_limit() -> None`.

`set` pre-validates single-entry size, updates or creates atomically, clears TTL metadata on overwrite, moves the set entry to the LRU front, then evicts from the back until within the nonzero limit.

- [ ] **Step 8: Run store and data-structure tests**

Run: `python -m unittest tests.test_store tests.test_hash_map tests.test_doubly_linked_list tests.test_min_heap -v`

Expected: all tests PASS.

- [ ] **Step 9: Commit the core store**

```bash
git add mini_redis/store.py mini_redis/__init__.py tests/test_store.py
git commit -m "feat: add memory limited LRU store"
```

### Task 5: Heap-based TTL expiration

**Files:**
- Modify: `mini_redis/store.py`
- Modify: `tests/test_store.py`

**Interfaces:**
- Consumes: Task 3 `MinHeap`; Task 4 `CacheEntry` and deletion helper.
- Produces: `MiniRedisStore.expire(key: str, seconds: int) -> int`, `ttl(key: str) -> int`, `_expire_key`, and `_purge_expired`.

- [ ] **Step 1: Add a fake clock and failing TTL tests**

Define a test-only callable clock with an `advance(seconds)` method. Test missing `EXPIRE`, missing/no-expiry TTL codes `-2/-1`, immediate expiration for zero and negative seconds, a 3-second TTL reporting `3`, boundary expiration, and expired `GET` returning `None` without LRU refresh or eviction count growth.

- [ ] **Step 2: Run and observe failure**

Run: `python -m unittest tests.test_store.MiniRedisTTLTests -v`

Expected: FAIL because `expire` and `ttl` do not exist.

- [ ] **Step 3: Implement current TTL operations**

Add:

```python
def expire(self, key: str, seconds: int) -> int: ...
def ttl(self, key: str) -> int: ...
def _expire_key(self, key: str, now: Optional[float] = None) -> bool: ...
def _purge_expired(self, now: Optional[float] = None) -> None: ...
```

Allocate globally increasing tokens and push `(expire_at, token, key)`. Use `math.ceil` for remaining seconds. Call key expiration before every key-based operation and purge before `dbsize`, `keys`, and `info_memory`.

- [ ] **Step 4: Run basic TTL tests**

Run: `python -m unittest tests.test_store.MiniRedisTTLTests -v`

Expected: basic TTL tests PASS.

- [ ] **Step 5: Write failing stale-record tests**

Test repeated `EXPIRE`, `SET` clearing TTL, explicit deletion before expiration, LRU eviction before expiration, and delete/recreate/expire of the same key. Advance past old deadlines and assert only a heap record whose timestamp and unique token match the current entry can delete it.

- [ ] **Step 6: Run and observe stale-record failure**

Run: `python -m unittest tests.test_store.MiniRedisTTLTests -v`

Expected: FAIL if stale heap records are treated as current.

- [ ] **Step 7: Complete lazy deletion validation**

When popping expired heap roots, ignore missing entries and records whose `ttl_token` or `expire_at` differs from the current entry. Valid expiration removes map/LRU/memory state without incrementing `evicted_keys`.

- [ ] **Step 8: Run the entire store suite**

Run: `python -m unittest tests.test_store -v`

Expected: all store tests PASS.

- [ ] **Step 9: Commit TTL support**

```bash
git add mini_redis/store.py tests/test_store.py
git commit -m "feat: add heap based TTL expiration"
```

### Task 6: Redis-style command processor

**Files:**
- Create: `mini_redis/command_processor.py`
- Create: `tests/test_commands.py`
- Modify: `mini_redis/__init__.py`

**Interfaces:**
- Consumes: every public `MiniRedisStore` operation from Tasks 4-5.
- Produces: `CommandProcessor(store: Optional[MiniRedisStore] = None)`, `execute(line: str) -> Optional[str]`, and `should_exit: bool`.

- [ ] **Step 1: Write failing happy-path command tests**

Cover exact results for all required commands:

```text
SET user:1 Alice                    -> OK
GET user:1                          -> "Alice"
EXISTS user:1                       -> (integer) 1
DBSIZE                              -> (integer) 1
EXPIRE user:1 3                    -> (integer) 1
TTL user:1                          -> (integer) 3
DEL user:1                          -> (integer) 1
KEYS on empty                       -> (empty array)
CONFIG SET maxmemory 30             -> OK
INFO memory                         -> three required fields
```

Use a fake-clock store and test case-insensitive command/subcommand names.

- [ ] **Step 2: Run and observe failure**

Run: `python -m unittest tests.test_commands -v`

Expected: FAIL because the processor does not exist.

- [ ] **Step 3: Implement parsing, dispatch, and formatting**

Implement:

```python
class CommandProcessor:
    def __init__(self, store: Optional[MiniRedisStore] = None) -> None: ...
    def execute(self, line: str) -> Optional[str]: ...
```

Use `shlex.split`, explicit conditionals, a `_quote(value: str) -> str` helper using `json.dumps(value, ensure_ascii=False)`, and exact arity checks. Set `should_exit` for case-insensitive `exit/quit`.

- [ ] **Step 4: Run happy-path command tests**

Run: `python -m unittest tests.test_commands -v`

Expected: happy-path tests PASS.

- [ ] **Step 5: Write failing validation and escaping tests**

Assert blank input returns `None`; quoted spaces round-trip; Unicode remains readable; quotes, backslashes, tabs, and newlines are escaped; `KEYS` uses numbered quoted lines; malformed quoting reports syntax error; unknown command and every wrong-arity form use required errors; invalid/overflowing integers and negative `maxmemory` use the integer error; non-positive valid `EXPIRE` deletes immediately; OOM formatting is exact; invalid commands do not mutate store state.

- [ ] **Step 6: Run and observe validation failures**

Run: `python -m unittest tests.test_commands -v`

Expected: FAIL on unimplemented validation cases.

- [ ] **Step 7: Complete validation**

Add signed 64-bit bounds `-(2**63)` through `2**63 - 1`, non-negative `maxmemory` validation, fixed subcommand validation for `CONFIG SET maxmemory` and `INFO memory`, and the specified error strings.

- [ ] **Step 8: Run command and store suites**

Run: `python -m unittest tests.test_commands tests.test_store -v`

Expected: all tests PASS.

- [ ] **Step 9: Commit the command layer**

```bash
git add mini_redis/command_processor.py mini_redis/__init__.py tests/test_commands.py
git commit -m "feat: add Redis style command processor"
```

### Task 7: CLI, documentation, and end-to-end verification

**Files:**
- Create: `mini_redis/cli.py`
- Create: `main.py`
- Create: `README.md`
- Modify: `tests/test_commands.py`

**Interfaces:**
- Consumes: Task 6 `CommandProcessor`.
- Produces: `run_repl(processor: Optional[CommandProcessor] = None, input_fn: Callable[[str], str] = input, output_fn: Callable[[str], None] = print) -> None` and executable `python main.py`.

- [ ] **Step 1: Write failing REPL-loop tests**

Use injected input/output functions to assert the prompt is exactly `mini-redis> `, normal responses are printed, blank input prints nothing, `quit/exit` terminates without extra output, and EOF/keyboard interrupt exits cleanly.

- [ ] **Step 2: Run and observe failure**

Run: `python -m unittest tests.test_commands -v`

Expected: FAIL because `run_repl` does not exist.

- [ ] **Step 3: Implement the CLI and entry point**

Implement `run_repl` as a thin loop around `CommandProcessor.execute`; `main.py` imports and runs it only under `if __name__ == "__main__":`.

- [ ] **Step 4: Run the complete automated suite**

Run: `python -m unittest discover -s tests -v`

Expected: all tests PASS with zero failures and errors.

- [ ] **Step 5: Write the README**

Document the Redis/cache story, architecture, file layout, commands and example output, run/test instructions, UTF-8 memory formula, LRU flow, TTL lazy deletion, complexity table, error behavior, constraints, and explicitly excluded bonus features.

- [ ] **Step 6: Run a manual CLI smoke test**

Run:

```bash
python main.py <<'EOF'
CONFIG SET maxmemory 30
SET user:1 Alice
SET user:2 Bob
GET user:1
EXPIRE user:1 3
TTL user:1
INFO memory
KEYS
quit
EOF
```

Expected: prompts plus `OK`, quoted `Alice`, integer responses, three memory fields, numbered keys, and clean termination without traceback.

- [ ] **Step 7: Inspect prohibited-collection usage**

Run:

```bash
rg -n "\b(dict|set|heapq|OrderedDict|defaultdict|deque)\b" mini_redis tests
```

Expected: no production use that replaces the custom hash map, LRU list, or heap; any textual documentation or test-only occurrence is manually justified.

- [ ] **Step 8: Verify Python syntax and imports**

Run: `python -m compileall -q mini_redis main.py tests`

Expected: exit status 0 with no syntax errors.

- [ ] **Step 9: Commit the completed CLI project**

```bash
git add mini_redis/cli.py main.py README.md tests/test_commands.py
git commit -m "feat: complete Mini Redis CLI"
```

## Final Verification

- [ ] Run `python -m unittest discover -s tests -v` and record the total passing test count.
- [ ] Run the manual CLI scenario and confirm required output forms.
- [ ] Run the prohibited-collection scan and inspect every match.
- [ ] Run `python -m compileall -q mini_redis main.py tests`.
- [ ] Compare implemented files and commands against `docs/superpowers/specs/2026-10-29-mini-redis-design.md`.
- [ ] Confirm `git status --short` contains no unintended files once Git access is available.
