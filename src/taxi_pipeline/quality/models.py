"""Small data-quality vocabularies and result objects."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class QualitySeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class QualityStatus(StrEnum):
    PASSED = "passed"
    VIOLATED = "violated"


@dataclass(frozen=True)
class QualityRule:
    name: str
    severity: QualitySeverity
    description: str


@dataclass(frozen=True)
class QualityMeasurement:
    rows_checked: int
    rows_failed: int
    details: dict[str, Any] | None = None


@dataclass(frozen=True)
class QualityRunSummary:
    partition_key: str
    run_id: int
    rows_checked: int
    check_count: int
    warnings_violated: int
    errors_violated: int
