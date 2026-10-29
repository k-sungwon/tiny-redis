# Tiny Redis

Python의 `dict`, `OrderedDict`, `heapq`에 핵심 동작을 맡기지 않고 Redis의 기본 원리를 직접 구현한 학습용 인메모리 Key-Value 저장소입니다.

이 프로젝트는 다음 질문에 코드로 답하는 것을 목표로 합니다.

- 키를 어떻게 빠르게 찾는가?
- 최근 사용 순서를 어떻게 O(1)로 바꾸는가?
- 어떤 키가 가장 먼저 만료되는지 어떻게 빠르게 찾는가?
- 메모리가 부족할 때 어떤 키를 제거하는가?

## 동작 구조

```text
CLI 명령
   |
CommandProcessor  -- 파싱, 검증, Redis 스타일 출력
   |
MiniRedisStore    -- 데이터와 세 자료구조의 일관성 관리
   |-- HashMap    -- key -> CacheEntry 조회
   |-- LRU List   -- 앞: 최근 사용 / 뒤: 오래된 사용
   `-- MinHeap    -- 가장 빠른 TTL 만료가 루트
```

하나의 `CacheEntry`는 문자열 키와 값, LRU 노드 참조, 현재 만료 시각과 고유 TTL 토큰을 가집니다. 해시맵이 엔트리를 찾고, 이중 연결 리스트가 사용 순서를 바꾸며, 최소 힙이 만료 순서를 관리합니다.

## 파일 구성

```text
mini_redis/
  doubly_linked_list.py  이중 연결 리스트
  hash_map.py            체이닝 해시맵과 리사이징
  min_heap.py            배열 기반 최소 힙
  store.py               String 저장, LRU, 메모리, TTL
  command_processor.py   명령어 파싱과 출력
  cli.py                 REPL
main.py                  실행 진입점
tests/                   단위·통합 테스트
```

## 실행

Python 3.8 이상이 필요하며 외부 패키지는 사용하지 않습니다.

```bash
python3 main.py
```

```text
mini-redis> SET user:1 "Alice"
OK
mini-redis> GET user:1
"Alice"
mini-redis> EXPIRE user:1 10
(integer) 1
mini-redis> TTL user:1
(integer) 10
mini-redis> quit
```

따옴표가 없는 단일 토큰 값과 큰따옴표로 감싼 공백 포함 값을 지원합니다.

```text
SET greeting hello
SET greeting "hello world"
```

## 명령어

| 명령 | 설명 | 대표 결과 |
|---|---|---|
| `SET key value` | 문자열 저장 또는 덮어쓰기 | `OK` |
| `GET key` | 문자열 조회와 LRU 갱신 | `"value"`, `(nil)` |
| `DEL key` | 키 삭제 | `(integer) 0/1` |
| `EXISTS key` | 존재 확인 | `(integer) 0/1` |
| `DBSIZE` | 유효한 키 개수 | `(integer) N` |
| `KEYS` | 전체 유효 키 | 번호가 있는 문자열 배열 |
| `CONFIG SET maxmemory bytes` | 최대 메모리 설정, 0은 무제한 | `OK` |
| `INFO memory` | 메모리와 제거 통계 | 3개 필드 |
| `EXPIRE key seconds` | 만료 시간 설정 | `(integer) 0/1` |
| `TTL key` | 남은 수명 | `-2`, `-1`, 또는 남은 초 |
| `exit`, `quit` | REPL 종료 | 출력 없음 |

명령어와 고정 하위 명령은 대소문자를 구분하지 않지만 키와 값은 구분합니다.

## 직접 구현한 자료구조

### 이중 연결 리스트

각 노드는 `prev`, `next`, `data`를 가집니다. LRU에서는 맨 앞이 최근 사용 키이고 맨 뒤가 가장 오래된 키입니다. 해시맵이 보관한 `CacheEntry`의 `lru_node` 참조를 이용하므로 성공한 `GET`은 해당 노드를 검색하지 않고 맨 앞으로 옮길 수 있습니다.

같은 연결 리스트 클래스가 해시 충돌 체이닝에도 사용되지만 LRU 노드와 버킷 노드는 서로 독립적입니다.

### 해시맵

UTF-8 바이트를 순서대로 처리하는 결정적 다항 해시를 사용합니다.

```text
hash = (hash * 31 + byte) & 0xFFFFFFFFFFFFFFFF
bucket = hash % capacity
```

충돌한 키는 버킷별 이중 연결 리스트에 연결합니다. 로드 팩터가 `0.75`를 초과하면 버킷을 두 배로 늘리고 모든 키를 다시 해싱합니다.

### 최소 힙

TTL 기록은 다음 튜플로 저장합니다.

```text
(expire_at, ttl_token, key)
```

`ttl_token`은 같은 키의 과거 TTL 기록과 현재 TTL 기록을 구분합니다. TTL 재설정, `SET` 덮어쓰기, `DEL`, LRU 제거 후에도 과거 기록은 힙에 남을 수 있으며, 루트에서 꺼낼 때 현재 엔트리의 시각과 토큰이 일치하지 않으면 무시합니다. 이것이 lazy deletion입니다.

## 메모리와 LRU

공식 메모리 계산은 다음과 같습니다.

```text
used_memory = Σ(
    len(key.encode("utf-8"))
    + len(value.encode("utf-8"))
)
```

Python 객체, 노드, 포인터, 버킷 오버헤드는 계산하지 않습니다. 한글은 UTF-8에서 보통 한 글자에 3바이트이므로 문자 개수와 메모리 값이 다를 수 있습니다.

`SET` 이후 제한을 초과하면 LRU 리스트의 뒤쪽부터 제거합니다. LRU 때문에 제거된 키만 `evicted_keys`를 증가시키며, `DEL`이나 TTL 만료는 증가시키지 않습니다.

새 키와 값 하나의 크기가 `maxmemory`보다 크면 기존 상태를 바꾸지 않고 다음 오류를 반환합니다.

```text
(error) OOM command not allowed when used_memory > 'maxmemory'
```

`CONFIG SET maxmemory`로 제한을 낮춰도 즉시 제거하지 않고 다음 성공한 `SET`에서 제한을 적용합니다.

## TTL 반환값

- 키가 없거나 이미 만료됨: `(integer) -2`
- 키는 있지만 TTL 없음: `(integer) -1`
- TTL 있음: 올림 처리한 남은 초
- `EXPIRE key 0` 또는 음수: 즉시 만료

키 기반 명령은 먼저 해당 키의 만료 여부를 확인합니다. `DBSIZE`, `KEYS`, `INFO memory`는 힙 루트의 만료 기록을 먼저 정리합니다.

## 시간 복잡도

| 연산 | 평균 시간 |
|---|---:|
| 연결 리스트 노드 삽입·삭제·앞으로 이동 | O(1) |
| 해시맵 `put/get/remove/contains` | O(1), 최악 O(n) |
| 해시맵 리사이징 | O(n) |
| 최소 힙 `peek` | O(1) |
| 최소 힙 `push/pop` | O(log n) |
| 성공한 `GET`과 LRU 갱신 | 평균 O(1) |
| TTL 추가 | 평균 O(1) 조회 + O(log n) 힙 추가 |

## 오류 형식

```text
(error) ERR unknown command '<cmd>'
(error) ERR wrong number of arguments for '<CMD>' command
(error) ERR value is not an integer or out of range
(error) ERR syntax error
(error) OOM command not allowed when used_memory > 'maxmemory'
```

명령 정수는 부호 있는 64비트 범위를 사용하며 `maxmemory`는 음수를 허용하지 않습니다. 반환 문자열은 JSON 방식으로 큰따옴표, 역슬래시와 제어 문자를 이스케이프하고 한글은 그대로 표시합니다.

## 테스트

```bash
python3 -m unittest discover -s tests -v
```

테스트는 다음을 포함합니다.

- 연결 리스트 삽입·삭제·이동
- 해시 충돌, 체이닝, 0.75 경계와 리해싱
- 최소 힙 정렬과 동일 만료 시각
- UTF-8 메모리 계산과 LRU 제거
- OOM 쓰기의 원자성
- TTL 경계와 오래된 힙 기록
- 전체 명령어, 오류, 따옴표 입력과 CLI 종료

## 구현하지 않는 범위

과제의 필수 범위에 집중하기 위해 다음 보너스 및 실제 Redis 기능은 구현하지 않습니다.

- 동적 배열 보너스
- 스택·큐·덱 문서
- 이진 트리와 BST
- Pub/Sub
- 네트워크 통신
- 파일 영속성
- List, Set, Sorted Set 같은 복합 타입
- 멀티스레딩과 락
