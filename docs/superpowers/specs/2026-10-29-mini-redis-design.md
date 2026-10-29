# Mini Redis Design

## Intent

Build a command-line Mini Redis in Python 3.8+ that teaches how Redis-like lookup, LRU eviction, and TTL expiration work internally. The project must use hand-built core data structures rather than replacing them with Python's built-in key-value or heap implementations.

The result should be understandable enough that a learner can explain, from the code, why a hash map provides fast lookup, why a doubly linked list supports O(1) LRU movement, and why a min-heap is appropriate for expiration management.

## Scope

### Goals

- Implement an independent doubly linked list with O(1) insertion, removal, and movement when a node reference is known.
- Implement a custom hash map using a custom deterministic hash function, separate chaining, and doubling when load factor exceeds 0.75.
- Implement a min-heap with `push`, `pop`, `peek`, `size`, `_heapify_up`, and `_heapify_down`.
- Implement the required Redis-style string commands: `SET`, `GET`, `DEL`, `EXISTS`, `DBSIZE`, and `KEYS`.
- Implement memory commands: `CONFIG SET maxmemory bytes` and `INFO memory`.
- Track memory using UTF-8 byte lengths and evict least-recently-used keys after `SET` when necessary.
- Implement heap-based TTL commands: `EXPIRE` and `TTL`, including stale heap-entry handling.
- Provide a usable `mini-redis>` REPL with quoted-value parsing and Redis-style responses.
- Provide focused unit and integration tests plus a README explaining the architecture, commands, complexity, and execution.

### Non-goals

- All bonus requirements: dynamic array, stack/queue/deque study, binary tree traversals, BST, and Pub/Sub.
- Network communication or compatibility with Redis clients.
- Persistence to files or recovery after restart.
- Redis types other than strings.
- Concurrency, threads, locks, transactions, authentication, or production hardening.
- Exact byte-for-byte compatibility with every real Redis edge case beyond the assignment requirements.

### Anti-goals

- Hiding the required learning behind `dict`, `set`, `collections.OrderedDict`, `heapq`, or a third-party cache library.
- Combining all code into one large file.
- Sharing one physical linked-list node between hash-bucket chaining and LRU ordering; those are independent relationships and must not corrupt one another.
- Optimizing prematurely at the cost of readable, explainable data-structure code.

## Constraints

- Python 3.8 or newer.
- Standard library only.
- Source annotations use Python 3.8-compatible `typing` forms such as `Optional[T]`; newer `T | None` syntax is not used in implementation code.
- Python lists may be used as indexed backing storage for the bucket table and min-heap because the assignment permits limited array-like storage. They must not replace the custom hash map or LRU list.
- Each required data structure lives in its own module and has docstrings on core classes and methods.
- The project currently has no Git repository. The design document can be written in the requested Superpowers location, but it cannot be committed until a repository exists during the approved implementation setup.

## Approaches Considered

### 1. Learning-oriented modular architecture — selected

Keep the linked list, hash map, min-heap, store, command processor, and CLI separate. Test each data structure before integrating it.

This adds files and tests, but it matches the assignment, isolates bugs, and makes each concept easy to connect to its implementation.

### 2. Feature-oriented integrated architecture

Put most behavior in one or two Mini Redis modules. This is faster to scaffold but mixes data-structure mechanics with command behavior, makes testing less precise, and weakens the learning value.

### 3. Generic reusable data-structure library

Build highly abstract generic containers and adapters. This offers reuse but introduces type and interface design beyond the assignment, obscuring the Redis concepts for a beginner.

## Project Structure

```text
mini_redis/
  __init__.py
  doubly_linked_list.py
  hash_map.py
  min_heap.py
  store.py
  command_processor.py
  cli.py
main.py
tests/
  __init__.py
  test_doubly_linked_list.py
  test_hash_map.py
  test_min_heap.py
  test_store.py
  test_commands.py
README.md
docs/superpowers/specs/
```

`main.py` is the simple executable entry point. The package modules remain independently importable for testing and explanation.

## Core Data Model

### Cache entry

The custom hash map stores `key -> CacheEntry`.

Each `CacheEntry` contains:

- `key`: string key.
- `value`: string value.
- `lru_node`: the node representing this entry in the LRU list.
- `expire_at`: absolute expiration timestamp or `None`.
- `ttl_token`: unique expiration token or `None`.

The entry is the authoritative record. The LRU list and TTL heap point back to the key or entry without becoming independent value stores.

### Time source

The store accepts an injectable clock callable, defaulting to the standard wall clock. Tests use a fake clock so TTL tests are deterministic and do not sleep.

## Doubly Linked List

`Node` has the required `prev`, `next`, and `data` fields. `DoublyLinkedList` uses private head and tail sentinels so boundary operations do not need many special cases.

Required operations:

- `insert_front(data) -> Node`
- `insert_back(data) -> Node`
- `remove_front() -> data | None`
- `remove_back() -> data | None`
- `remove_node(node) -> data`
- `move_to_front(node) -> None`

The list tracks its length. All operations above change only a constant number of links and therefore run in O(1), assuming a valid node reference.

The same list class is reused in two independent places:

- Each hash bucket owns a list of hash-map entries for collision chaining.
- The store owns a separate LRU list whose front is most recently used and whose back is least recently used.

## Hash Map

### Storage and hashing

- The bucket table is an indexed Python list whose elements are either `None` or independent `DoublyLinkedList` instances.
- Initial capacity is 8.
- A deterministic polynomial rolling hash processes the UTF-8 bytes of a string key, multiplying the accumulated value by 31 and adding the next byte. Arithmetic is kept within a fixed 64-bit mask.
- Bucket index is `hash_value % capacity`.

### Operations

- `put(key, value)`: update an existing key without changing size, or append a new map entry and increment size.
- `get(key)`: return the stored value, with a private sentinel or explicit result convention distinguishing a missing key from a stored `None`. The store itself does not store `None` values.
- `remove(key)`: unlink the matching bucket node, decrement size, and return the removed value or the missing sentinel.
- `contains(key)`: find a key without depending on the truthiness of its value.
- `keys()`: return a new output list of all keys.
- `size()`: return the current key count.

After insertion of a new key, if `size / capacity > 0.75`, capacity doubles. Every existing map entry is rehashed using the new capacity and placed into a new bucket table. Updating an existing key does not trigger a size increase.

Average lookup, insertion, and removal are O(1); worst case is O(n) when many keys collide. Resizing is O(n) but occurs only at capacity thresholds.

## Min-Heap

The min-heap uses a Python list only as indexed array storage. It does not use `heapq`.

Heap items for TTL are tuples:

```text
(expire_at, ttl_token, key)
```

The unique numeric token provides deterministic ordering when timestamps match and identifies stale expiration records.

Operations:

- `push(item)`: append, then `_heapify_up`.
- `peek()`: return the root without removal, or `None` when empty.
- `pop()`: remove the root, move the last item to the root, then `_heapify_down`.
- `size()`: return item count.

`peek` is O(1); `push` and `pop` are O(log n).

## Store Behavior

`MiniRedisStore` owns:

- The custom hash map of cache entries.
- The LRU doubly linked list.
- The TTL min-heap.
- `used_memory`, `maxmemory`, and `evicted_keys` counters.
- A monotonically increasing TTL token counter.
- The injected clock.

### Common expiration behavior

Every key-based command checks that key's expiration before acting. `_expire_key(key, now)` removes an expired current entry and treats it as missing.

Commands that represent the whole database (`DBSIZE`, `KEYS`, and `INFO memory`) call `_purge_expired(now)`. This repeatedly removes expired heap roots until the root is in the future. A popped heap item is valid only if its token and timestamp match the current entry; otherwise it is a stale record and is ignored.

Stale heap records arise when a TTL is replaced, a key is overwritten, deleted, evicted, or deleted and later recreated. Globally unique TTL tokens prevent an old record from matching a recreated key.

### Memory accounting

Entry size is exactly:

```text
len(key.encode("utf-8")) + len(value.encode("utf-8"))
```

Container and object overhead is excluded.

One internal deletion helper removes an entry consistently from the custom hash map and LRU list and subtracts its byte size. It clears current TTL metadata; stale heap records remain for lazy deletion.

Deletion reasons affect statistics:

- Explicit `DEL`: do not increment `evicted_keys`.
- TTL expiration: do not increment `evicted_keys`.
- LRU memory eviction: increment `evicted_keys` once per removed key.

### `SET key value`

1. Expire the key first if needed.
2. Compute the new entry size.
3. If `maxmemory > 0` and the single new entry is larger than `maxmemory`, return OOM without changing existing data, TTL, LRU order, or counters.
4. For an existing key, subtract its old size, replace the value, clear its TTL/token, add the new size, and move its LRU node to the front.
5. For a new key, create the entry, insert it in the map, insert its LRU node at the front, and add its size.
6. If `maxmemory > 0`, remove LRU nodes from the back until `used_memory <= maxmemory`, incrementing `evicted_keys` for each removal.
7. Return `OK`.

Because the newly set key is most recently used and a single entry was pre-validated to fit, older keys are evicted first and the new key remains.

### `GET key`

- Expire the key first.
- Missing or expired: return `(nil)`.
- Present: move its LRU node to the front and return the quoted value.

Only a successful lookup changes LRU order.

### `DEL key`

- Expire the key first.
- Missing: return `(integer) 0`.
- Present: remove it from map, LRU, TTL metadata, and memory accounting; return `(integer) 1`.

### `EXISTS key`

- Expire the key first.
- Return `(integer) 1` if present, otherwise `(integer) 0`.
- Do not change LRU order because the assignment specifies LRU refresh for successful `GET` and `SET`, not existence checks.

### `DBSIZE`

- Purge expired heap roots.
- Return the custom hash-map size as `(integer) N`.

### `KEYS`

- Purge expired heap roots.
- Return each current key as a numbered quoted line; ordering is unspecified.
- Return `(empty array)` when no keys remain.

### `CONFIG SET maxmemory bytes`

- Accept an integer `bytes >= 0`; zero means unlimited.
- Change `maxmemory` and return `OK`.
- Follow the assignment's explicit eviction timing: changing the limit alone does not evict. The next successful `SET` enforces the new limit.

### `INFO memory`

- Purge expired entries first.
- Return at least these newline-separated fields:

```text
used_memory:<number>
maxmemory:<number>
evicted_keys:<number>
```

### `EXPIRE key seconds`

- Expire the key first.
- Missing: return `(integer) 0`.
- If `seconds <= 0`, immediately delete the key and return `(integer) 1`.
- Otherwise allocate a new unique TTL token, set `expire_at = now + seconds`, store the token on the entry, push `(expire_at, token, key)` into the min-heap, and return `(integer) 1`.
- Do not change LRU order.

### `TTL key`

- Expire the key first.
- Missing: return `(integer) -2`.
- Present without expiration: return `(integer) -1`.
- Present with expiration: return the remaining whole seconds using ceiling so a newly assigned 3-second TTL reports 3 rather than 2 due to fractional execution time.
- Do not change LRU order.

## Command Processing and CLI

`CommandProcessor.execute(line)` returns a response string or `None` for blank input. It uses `shlex.split` so unquoted single-token values and double-quoted values containing spaces work.

Returned keys and values use JSON-style double-quoted string escaping: embedded quotes, backslashes, tabs, newlines, and other control characters are escaped, while Unicode text remains readable. A small shared quoting helper provides identical formatting for `GET` and `KEYS`.

Dispatch uses explicit conditionals rather than a built-in dictionary. Commands and fixed subcommand names are case-insensitive; keys and values preserve case.

Arity is validated before calling the store:

- Unknown: `(error) ERR unknown command '<cmd>'`
- Wrong arity: `(error) ERR wrong number of arguments for '<CMD>' command`
- Invalid or out-of-range integer: `(error) ERR value is not an integer or out of range`
- Oversized entry: `(error) OOM command not allowed when used_memory > 'maxmemory'`
- Malformed shell quoting: `(error) ERR syntax error`

Integer parsing uses the signed 64-bit range `-2^63` through `2^63 - 1`, matching Redis-style integer expectations. `CONFIG SET maxmemory` additionally rejects negative values. `EXPIRE` accepts non-positive in-range values and treats them as immediate expiration.

The CLI repeatedly calls `input("mini-redis> ")`, prints non-empty responses, and exits cleanly on case-insensitive `exit` or `quit`, EOF, or keyboard interrupt.

## Error Handling and Invariants

Core invariants after every completed operation:

- Hash-map size equals LRU list length.
- Every current map entry has exactly one valid LRU node.
- `used_memory` equals the UTF-8 byte sum of all current map entries.
- Every valid current TTL has one matching heap record, though stale heap records may also exist.
- An entry with `expire_at is None` has `ttl_token is None`.
- Failed OOM writes do not partially change existing state.

Internal programming errors such as removing a detached linked-list node may raise normal Python exceptions. User input errors are converted to the specified Redis-style messages by the command processor.

## Testing Strategy

Use Python's built-in `unittest` so the project has no external dependencies.

### Data-structure tests

- Linked-list insertion/removal at both ends, middle-node removal, movement, empty behavior, and length.
- Hash-map insert/update/get/remove/contains/keys/size, deliberate collisions, exact 0.75 behavior, greater-than-0.75 resize, and correct rehashing.
- Min-heap empty behavior, ordering, duplicate expiration times, and both heapify directions.

### Store tests

- UTF-8 memory accounting, including Korean text.
- New and overwritten `SET`, including TTL reset.
- Successful/missing/expired `GET` and LRU movement.
- LRU eviction order, multiple evictions, counter updates, unlimited memory, and OOM atomicity.
- Explicit deletion consistency.
- Expiration, immediate expiration, TTL return codes, repeated `EXPIRE`, stale heap records, deletion/recreation of the same key, and fake-clock boundary behavior.
- `DBSIZE`, `KEYS`, and `INFO memory` after expirations.

### Command and CLI-facing tests

- Every required command's exact response format.
- Case-insensitive commands, quoted values with spaces, Unicode, blank lines, malformed quotes, unknown commands, wrong arity, invalid integers, negative `maxmemory`, and exit commands.
- A reference scenario matching the assignment example.

All tests run with:

```text
python -m unittest discover -s tests -v
```

## Documentation

`README.md` will include:

- The project purpose and Redis mental model.
- Architecture and data-flow explanation.
- File layout.
- Run and test instructions.
- Supported commands with examples.
- Complexity table for the custom structures.
- Explanation of LRU, TTL lazy deletion, memory accounting, and important edge cases.
- Explicit statement that bonus features, networking, persistence, and concurrency are outside scope.

## Builder Decisions Already Made

These are implementation-level calls that do not alter user-visible scope:

- Use sentinel nodes in the doubly linked list.
- Use initial hash-map capacity 8 and a deterministic polynomial hash over UTF-8 bytes.
- Use a globally unique TTL token for safe lazy deletion.
- Use an injected clock and ceiling for TTL display.
- Use `unittest` and standard-library `shlex`.
- Use JSON-style quoted output with readable Unicode, and signed 64-bit command integers.
- Preserve existing data atomically when a replacement value itself cannot fit `maxmemory`.
- Do not evict immediately when `CONFIG SET maxmemory` lowers the limit, because the assignment explicitly specifies eviction after `SET`.

## Completion Criteria

The project is complete when:

- All required commands operate through the custom structures with the specified output.
- No prohibited built-in collection replaces the custom map, LRU, or heap.
- Required edge cases and invariants are tested.
- The full test suite passes on Python 3.8+.
- A manual CLI smoke test demonstrates storage, lookup, LRU eviction, expiration, memory information, error handling, and clean exit.
- README documentation makes the implementation explainable to the learner.
