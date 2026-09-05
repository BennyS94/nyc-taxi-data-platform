import pytest

from taxi_pipeline.metadata.statuses import (
    IngestionDecision,
    MetadataStateError,
    SourceStatus,
    decision_for_source_status,
)


@pytest.mark.parametrize(
    ("status", "decision"),
    [
        (SourceStatus.READY, IngestionDecision.PROCEED),
        (SourceStatus.LOADED, IngestionDecision.ALREADY_LOADED),
        (SourceStatus.REVISION_DETECTED, IngestionDecision.SOURCE_REVISION_BLOCKED),
    ],
)
def test_source_status_decisions(status, decision):
    assert decision_for_source_status(status) is decision
    assert decision_for_source_status(status.value) is decision


def test_unknown_source_status_is_rejected():
    with pytest.raises(MetadataStateError, match="Unknown source status"):
        decision_for_source_status("unexpected")
