from __future__ import annotations

import math
from dataclasses import dataclass, field
from time import perf_counter
from typing import Callable

from data_pages import PagePreview, PagedDataSet


HashFunction = Callable[[str, int], int]

FNV1A_NAME = "FNV-1a"
POLYNOMIAL_NAME = "Polinomial"


@dataclass(frozen=True)
class IndexEntry:
    key: str
    page_number: int


@dataclass(frozen=True)
class BucketSnapshot:
    bucket_index: int
    primary_entries: tuple[IndexEntry, ...]
    overflow_pages: tuple[tuple[IndexEntry, ...], ...]
    total_entries: int


@dataclass(frozen=True)
class BuildStats:
    record_count: int
    page_count: int
    bucket_count: int
    bucket_capacity: int
    collision_count: int
    overflow_bucket_count: int
    overflow_page_count: int
    build_seconds: float

    @property
    def collision_rate(self) -> float:
        if self.record_count == 0:
            return 0.0
        return (self.collision_count / self.record_count) * 100.0

    @property
    def overflow_rate(self) -> float:
        if self.bucket_count == 0:
            return 0.0
        return (self.overflow_bucket_count / self.bucket_count) * 100.0


@dataclass(frozen=True)
class IndexSearchResult:
    query: str
    found: bool
    page_number: int | None
    bucket_index: int
    bucket_pages_read: int
    data_pages_read: int
    total_page_reads: int
    bucket_entries_examined: int
    elapsed_seconds: float
    bucket_snapshot: BucketSnapshot
    page_preview: PagePreview | None


@dataclass
class OverflowPage:
    entries: list[IndexEntry] = field(default_factory=list)
    next_page: OverflowPage | None = None


@dataclass
class Bucket:
    entries: list[IndexEntry] = field(default_factory=list)
    overflow_head: OverflowPage | None = None
    overflow_pages: int = 0

    def snapshot(self, bucket_index: int) -> BucketSnapshot:
        overflow_pages: list[tuple[IndexEntry, ...]] = []
        current = self.overflow_head
        total_entries = len(self.entries)

        while current is not None:
            overflow_pages.append(tuple(current.entries))
            total_entries += len(current.entries)
            current = current.next_page

        return BucketSnapshot(
            bucket_index=bucket_index,
            primary_entries=tuple(self.entries),
            overflow_pages=tuple(overflow_pages),
            total_entries=total_entries,
        )


def available_hash_algorithms() -> tuple[str, ...]:
    return (FNV1A_NAME, POLYNOMIAL_NAME)


def resolve_hash_function(name: str) -> HashFunction:
    if name == POLYNOMIAL_NAME:
        return polynomial_hash
    return fnv1a_hash


def fnv1a_hash(value: str, bucket_count: int) -> int:
    hash_value = 2166136261
    for byte in value.encode("utf-8"):
        hash_value ^= byte
        hash_value = (hash_value * 16777619) & 0xFFFFFFFF
    return hash_value % bucket_count


def polynomial_hash(value: str, bucket_count: int) -> int:
    accumulator = 0
    modulus = 2_147_483_647
    base = 53
    for char in value:
        accumulator = (accumulator * base + ord(char)) % modulus
    return accumulator % bucket_count


def calculate_bucket_count(record_count: int, bucket_capacity: int) -> int:
    if bucket_capacity <= 0:
        raise ValueError("FR deve ser maior que zero.")
    minimum = math.floor(record_count / bucket_capacity) + 1
    return next_prime(max(1, minimum))


def validate_bucket_count(bucket_count: int, record_count: int, bucket_capacity: int) -> bool:
    return bucket_count > (record_count / bucket_capacity) if bucket_capacity > 0 else False


def next_prime(value: int) -> int:
    candidate = max(2, value)
    while not is_prime(candidate):
        candidate += 1
    return candidate


def is_prime(value: int) -> bool:
    if value <= 1:
        return False
    if value <= 3:
        return True
    if value % 2 == 0:
        return False

    limit = math.isqrt(value)
    for factor in range(3, limit + 1, 2):
        if value % factor == 0:
            return False
    return True


class HashIndex:
    def __init__(self, bucket_capacity: int, bucket_count: int, hash_algorithm: str = FNV1A_NAME) -> None:
        if bucket_capacity <= 0:
            raise ValueError("FR deve ser maior que zero.")
        if bucket_count <= 0:
            raise ValueError("NB deve ser maior que zero.")

        self.bucket_capacity = bucket_capacity
        self.bucket_count = bucket_count
        self.hash_algorithm = hash_algorithm
        self._hash_function = resolve_hash_function(hash_algorithm)

        self.buckets: list[Bucket] = [Bucket() for _ in range(bucket_count)]
        self.collision_count = 0
        self.overflow_pages_created = 0
        self._overflow_buckets: set[int] = set()

    @property
    def overflow_bucket_count(self) -> int:
        return len(self._overflow_buckets)

    def build(self, dataset: PagedDataSet) -> BuildStats:
        self.buckets = [Bucket() for _ in range(self.bucket_count)]
        self.collision_count = 0
        self.overflow_pages_created = 0
        self._overflow_buckets.clear()

        started_at = perf_counter()
        for page_number, page in dataset.iter_pages():
            for word in page:
                self.insert(word, page_number)
        elapsed = perf_counter() - started_at

        return BuildStats(
            record_count=dataset.nr,
            page_count=dataset.page_count,
            bucket_count=self.bucket_count,
            bucket_capacity=self.bucket_capacity,
            collision_count=self.collision_count,
            overflow_bucket_count=self.overflow_bucket_count,
            overflow_page_count=self.overflow_pages_created,
            build_seconds=elapsed,
        )

    def insert(self, key: str, page_number: int) -> None:
        bucket_index = self._bucket_index_for(key)
        bucket = self.buckets[bucket_index]
        entry = IndexEntry(key=key, page_number=page_number)

        if len(bucket.entries) < self.bucket_capacity:
            bucket.entries.append(entry)
            return

        self.collision_count += 1
        self._overflow_buckets.add(bucket_index)

        if bucket.overflow_head is None:
            bucket.overflow_head = OverflowPage()
            bucket.overflow_pages += 1
            self.overflow_pages_created += 1

        current = bucket.overflow_head
        while current is not None:
            if len(current.entries) < self.bucket_capacity:
                current.entries.append(entry)
                return

            if current.next_page is None:
                current.next_page = OverflowPage()
                bucket.overflow_pages += 1
                self.overflow_pages_created += 1

            current = current.next_page

    def search(self, key: str, dataset: PagedDataSet) -> IndexSearchResult:
        bucket_index = self._bucket_index_for(key)
        bucket = self.buckets[bucket_index]

        started_at = perf_counter()
        bucket_pages_read = 1
        entries_examined = 0
        matched_page_number: int | None = None

        for entry in bucket.entries:
            entries_examined += 1
            if entry.key == key:
                matched_page_number = entry.page_number
                break

        overflow_page = bucket.overflow_head
        while matched_page_number is None and overflow_page is not None:
            bucket_pages_read += 1
            for entry in overflow_page.entries:
                entries_examined += 1
                if entry.key == key:
                    matched_page_number = entry.page_number
                    break
            if matched_page_number is not None:
                break
            overflow_page = overflow_page.next_page

        data_pages_read = 0
        found = False
        page_preview: PagePreview | None = None

        if matched_page_number is not None:
            data_pages_read = 1
            page = dataset.get_page(matched_page_number)
            if key in page:
                found = True
                page_preview = dataset.preview(matched_page_number)

        elapsed = perf_counter() - started_at

        return IndexSearchResult(
            query=key,
            found=found,
            page_number=matched_page_number if found else None,
            bucket_index=bucket_index,
            bucket_pages_read=bucket_pages_read,
            data_pages_read=data_pages_read,
            total_page_reads=bucket_pages_read + data_pages_read,
            bucket_entries_examined=entries_examined,
            elapsed_seconds=elapsed,
            bucket_snapshot=bucket.snapshot(bucket_index),
            page_preview=page_preview,
        )

    def bucket_snapshot(self, bucket_index: int) -> BucketSnapshot:
        return self.buckets[bucket_index].snapshot(bucket_index)

    def _bucket_index_for(self, key: str) -> int:
        return self._hash_function(key, self.bucket_count)
