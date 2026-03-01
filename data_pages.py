from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Sequence


@dataclass(frozen=True)
class PagePreview:
    page_number: int
    record_count: int
    first_records: tuple[str, ...]


def load_words_from_txt(file_path: str | Path) -> list[str]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Arquivo nao encontrado: {path}")

    records: list[str] = []
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            word = raw_line.strip()
            if word:
                records.append(word)
    return records


class PagedDataSet:
    def __init__(self, records: Sequence[str], page_size: int) -> None:
        if page_size <= 0:
            raise ValueError("O tamanho da pagina deve ser maior que zero.")

        self.records = records if isinstance(records, list) else list(records)
        self.page_size = page_size

    @property
    def nr(self) -> int:
        return len(self.records)

    @property
    def page_count(self) -> int:
        if self.nr == 0:
            return 0
        return ((self.nr - 1) // self.page_size) + 1

    def page_of_record(self, record_index: int) -> int:
        if record_index < 0 or record_index >= self.nr:
            raise IndexError("Indice de registro fora do intervalo.")
        return (record_index // self.page_size) + 1

    def get_page(self, page_number: int) -> list[str]:
        if self.page_count == 0:
            return []
        if page_number < 1 or page_number > self.page_count:
            raise IndexError("Numero de pagina fora do intervalo.")
        start = (page_number - 1) * self.page_size
        end = min(start + self.page_size, self.nr)
        return list(self.records[start:end])

    def preview(self, page_number: int, preview_limit: int = 5) -> PagePreview:
        page = self.get_page(page_number)
        return PagePreview(
            page_number=page_number,
            record_count=len(page),
            first_records=tuple(page[:preview_limit]),
        )

    def first_preview(self, preview_limit: int = 5) -> PagePreview | None:
        if self.page_count == 0:
            return None
        return self.preview(1, preview_limit)

    def last_preview(self, preview_limit: int = 5) -> PagePreview | None:
        if self.page_count == 0:
            return None
        return self.preview(self.page_count, preview_limit)

    def iter_pages(self) -> Iterator[tuple[int, list[str]]]:
        for start in range(0, self.nr, self.page_size):
            page_number = (start // self.page_size) + 1
            end = min(start + self.page_size, self.nr)
            yield page_number, list(self.records[start:end])
