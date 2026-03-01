from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from data_pages import PagePreview, PagedDataSet
from hash_index import IndexSearchResult


@dataclass(frozen=True)
class TableScanResult:
    query: str
    found: bool
    page_number: int | None
    pages_read: int
    records_read: int
    elapsed_seconds: float
    visited_pages_preview: tuple[int, ...]
    preview_truncated: bool
    page_preview: PagePreview | None


@dataclass(frozen=True)
class SearchComparison:
    same_query: bool
    query: str
    time_saved_seconds: float
    page_reads_saved: int


def format_seconds(seconds: float) -> str:
    return f"{seconds * 1000:.3f} ms"


def table_scan(dataset: PagedDataSet, query: str, preview_limit: int = 20) -> TableScanResult:
    started_at = perf_counter()
    pages_read = 0
    records_read = 0
    visited_pages: list[int] = []
    preview_truncated = False
    found = False
    page_number: int | None = None
    page_preview: PagePreview | None = None

    for current_page, page in dataset.iter_pages():
        pages_read += 1
        if len(visited_pages) < preview_limit:
            visited_pages.append(current_page)
        else:
            preview_truncated = True

        for word in page:
            records_read += 1
            if word == query:
                found = True
                page_number = current_page
                page_preview = dataset.preview(current_page)
                break

        if found:
            break

    elapsed = perf_counter() - started_at

    return TableScanResult(
        query=query,
        found=found,
        page_number=page_number,
        pages_read=pages_read,
        records_read=records_read,
        elapsed_seconds=elapsed,
        visited_pages_preview=tuple(visited_pages),
        preview_truncated=preview_truncated,
        page_preview=page_preview,
    )


def compare_searches(
    index_result: IndexSearchResult | None, scan_result: TableScanResult | None
) -> SearchComparison | None:
    if index_result is None or scan_result is None:
        return None

    if index_result.query != scan_result.query:
        return SearchComparison(
            same_query=False,
            query=index_result.query,
            time_saved_seconds=0.0,
            page_reads_saved=0,
        )

    return SearchComparison(
        same_query=True,
        query=index_result.query,
        time_saved_seconds=scan_result.elapsed_seconds - index_result.elapsed_seconds,
        page_reads_saved=scan_result.pages_read - index_result.total_page_reads,
    )
