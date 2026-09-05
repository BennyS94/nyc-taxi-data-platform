"""Value objects shared by raw loaders."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RawBatch:
    """One bounded batch with deterministic file-level row numbering."""

    start_row_number: int
    rows: tuple[tuple, ...]

    @property
    def row_count(self) -> int:
        return len(self.rows)


@dataclass(frozen=True)
class LoadCounts:
    """Counts observed while reading and copying one source file."""

    rows_read: int
    rows_loaded: int
