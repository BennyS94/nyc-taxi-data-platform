"""Small application-level status and decision vocabularies."""

from dataclasses import dataclass
from enum import StrEnum


class SourceStatus(StrEnum):
    READY = "ready"
    LOADED = "loaded"
    REVISION_DETECTED = "revision_detected"


class RunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class SkipReason(StrEnum):
    ALREADY_LOADED = "already_loaded"
    SOURCE_REVISION_DETECTED = "source_revision_detected"


class IngestionDecision(StrEnum):
    PROCEED = "proceed"
    ALREADY_LOADED = "already_loaded"
    SOURCE_REVISION_BLOCKED = "source_revision_blocked"


class MetadataStateError(ValueError):
    """An operational metadata status or transition is invalid."""


@dataclass(frozen=True)
class SourceRegistrationResult:
    """Decision returned when one immutable source version is registered."""

    source_file_id: int
    source_status: SourceStatus
    decision: IngestionDecision
    is_new_registration: bool


def decision_for_source_status(status: str | SourceStatus) -> IngestionDecision:
    """Map a persisted source status to its ingestion decision."""
    try:
        source_status = SourceStatus(status)
    except ValueError as error:
        raise MetadataStateError(f"Unknown source status: {status}") from error

    decisions = {
        SourceStatus.READY: IngestionDecision.PROCEED,
        SourceStatus.LOADED: IngestionDecision.ALREADY_LOADED,
        SourceStatus.REVISION_DETECTED: IngestionDecision.SOURCE_REVISION_BLOCKED,
    }
    return decisions[source_status]
