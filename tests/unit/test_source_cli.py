from taxi_pipeline import cli
from taxi_pipeline.ingestion import IngestionResult
from taxi_pipeline.metadata.statuses import (
    IngestionDecision,
    RunStatus,
    SkipReason,
    SourceRegistrationResult,
    SourceStatus,
)
from taxi_pipeline.quality import QualityRunSummary
from taxi_pipeline.sources.contracts import SourceContractError
from taxi_pipeline.sources.models import SourceFileMetadata


def metadata(**changes):
    values = {
        "dataset_name": "yellow_tripdata",
        "service_type": "yellow",
        "year": 2025,
        "month": 1,
        "partition_key": "yellow/2025/01",
        "source_url": "https://example.test/source.parquet",
        "landing_path": "data/landing/yellow/2025/01.parquet",
        "source_format": "parquet",
        "checksum_sha256": "a" * 64,
        "file_size_bytes": 10,
        "row_count": 3_475_226,
        "schema_fingerprint": "b" * 64,
        "schema_version": "yellow_v2",
    }
    values.update(changes)
    return SourceFileMetadata(**values)


def test_yellow_source_cli_fetches_and_prints_concise_metadata(monkeypatch, capsys):
    observed = {}
    monkeypatch.setattr(cli, "ensure_local", lambda source, root: observed.setdefault("source", source))
    monkeypatch.setattr(cli, "inspect_source", lambda source, root: metadata())

    result = cli.main(["source", "fetch", "--service", "yellow", "--year", "2025", "--month", "1"])

    assert result == 0
    assert observed["source"].partition_key == "yellow/2025/01"
    assert capsys.readouterr().out.splitlines() == [
        "Source: yellow/2025/01",
        "Status: ready",
        "Path: data/landing/yellow/2025/01.parquet",
        "Rows: 3,475,226",
        f"SHA-256: {'a' * 64}",
        "Schema: yellow_v2",
    ]


def test_taxi_zone_cli_reports_valid_structure(monkeypatch, capsys):
    monkeypatch.setattr(cli, "ensure_local", lambda source, root: None)
    monkeypatch.setattr(
        cli,
        "inspect_source",
        lambda source, root: metadata(
            dataset_name="taxi_zone_lookup",
            service_type=None,
            year=None,
            month=None,
            partition_key="reference/taxi_zones",
            landing_path="data/landing/reference/taxi_zone_lookup.csv",
            source_format="csv",
            row_count=265,
            schema_fingerprint=None,
            schema_version=None,
        ),
    )

    assert cli.main(["source", "fetch-zones"]) == 0
    assert "Structure: valid" in capsys.readouterr().out


def test_source_cli_returns_nonzero_on_contract_failure(monkeypatch, capsys):
    monkeypatch.setattr(cli, "ensure_local", lambda source, root: None)

    def fail(source, root):
        raise SourceContractError("unsupported schema")

    monkeypatch.setattr(cli, "inspect_source", fail)

    assert cli.main(["source", "fetch-zones"]) == 1
    assert "Source error: unsupported schema" in capsys.readouterr().err


def test_source_registration_cli_prints_registry_decision(monkeypatch, capsys):
    monkeypatch.setattr(cli, "ensure_local", lambda source, root: None)
    monkeypatch.setattr(cli, "inspect_source", lambda source, root: metadata())
    monkeypatch.setattr(
        cli,
        "_register_metadata",
        lambda source_metadata: SourceRegistrationResult(
            source_file_id=3,
            source_status=SourceStatus.READY,
            decision=IngestionDecision.PROCEED,
            is_new_registration=True,
        ),
    )

    result = cli.main(
        ["source", "register", "--service", "yellow", "--year", "2025", "--month", "1"]
    )

    assert result == 0
    assert capsys.readouterr().out.splitlines() == [
        "Source: yellow/2025/01",
        "Source file ID: 3",
        "Status: ready",
        "Decision: proceed",
    ]


def test_taxi_zone_registration_uses_reference_source(monkeypatch):
    observed = {}
    monkeypatch.setattr(cli, "ensure_local", lambda source, root: None)
    monkeypatch.setattr(
        cli,
        "inspect_source",
        lambda source, root: metadata(
            dataset_name="taxi_zone_lookup",
            service_type=None,
            year=None,
            month=None,
            partition_key="reference/taxi_zones",
            landing_path="data/landing/reference/taxi_zone_lookup.csv",
            source_format="csv",
            schema_fingerprint=None,
            schema_version=None,
        ),
    )

    def register(source_metadata):
        observed["metadata"] = source_metadata
        return SourceRegistrationResult(
            source_file_id=4,
            source_status=SourceStatus.READY,
            decision=IngestionDecision.PROCEED,
            is_new_registration=True,
        )

    monkeypatch.setattr(cli, "_register_metadata", register)

    assert cli.main(["source", "register-zones"]) == 0
    assert observed["metadata"].partition_key == "reference/taxi_zones"


def test_ingest_cli_prints_success(monkeypatch, capsys):
    monkeypatch.setattr(cli, "ensure_local", lambda source, root: None)
    monkeypatch.setattr(cli, "inspect_source", lambda source, root: metadata())
    monkeypatch.setattr(
        cli,
        "_ingest_metadata",
        lambda source_metadata: IngestionResult(
            partition_key=source_metadata.partition_key,
            source_file_id=3,
            run_id=9,
            status=RunStatus.SUCCEEDED,
            rows_read=3_475_226,
            rows_loaded=3_475_226,
        ),
    )

    result = cli.main(["ingest", "--service", "yellow", "--year", "2025", "--month", "1"])

    assert result == 0
    assert capsys.readouterr().out.splitlines() == [
        "Source: yellow/2025/01",
        "Run: 9",
        "Rows read: 3,475,226",
        "Rows loaded: 3,475,226",
        "Status: succeeded",
    ]


def test_ingest_zones_cli_prints_skip_reason(monkeypatch, capsys):
    monkeypatch.setattr(cli, "ensure_local", lambda source, root: None)
    monkeypatch.setattr(
        cli,
        "inspect_source",
        lambda source, root: metadata(
            dataset_name="taxi_zone_lookup",
            service_type=None,
            year=None,
            month=None,
            partition_key="reference/taxi_zones",
            landing_path="data/landing/reference/taxi_zone_lookup.csv",
            source_format="csv",
            schema_fingerprint=None,
            schema_version=None,
        ),
    )
    monkeypatch.setattr(
        cli,
        "_ingest_metadata",
        lambda source_metadata: IngestionResult(
            partition_key=source_metadata.partition_key,
            source_file_id=4,
            run_id=10,
            status=RunStatus.SKIPPED,
            rows_read=0,
            rows_loaded=0,
            status_reason=SkipReason.ALREADY_LOADED,
        ),
    )

    assert cli.main(["ingest-zones"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "Source: reference/taxi_zones",
        "Run: 10",
        "Rows loaded: 0",
        "Status: skipped",
        "Reason: already_loaded",
    ]


def test_quality_cli_prints_concise_summary(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "_run_quality_for_partition",
        lambda service, year, month: QualityRunSummary(
            partition_key=f"{service}/{year}/{month:02d}",
            run_id=12,
            rows_checked=3_475_226,
            check_count=27,
            warnings_violated=8,
            errors_violated=0,
        ),
    )

    result = cli.main(
        ["quality", "run", "--service", "yellow", "--year", "2025", "--month", "1"]
    )

    assert result == 0
    assert capsys.readouterr().out.splitlines() == [
        "Quality: yellow/2025/01",
        "Run: 12",
        "Rows: 3,475,226",
        "Checks: 27",
        "Warnings violated: 8",
        "Errors violated: 0",
        "Status: completed",
    ]


def test_quality_cli_returns_nonzero_when_target_is_missing(monkeypatch, capsys):
    def fail(service, year, month):
        raise ValueError("no successful run")

    monkeypatch.setattr(cli, "_run_quality_for_partition", fail)

    result = cli.main(
        ["quality", "run", "--service", "yellow", "--year", "2025", "--month", "2"]
    )

    assert result == 1
    assert "Quality error: no successful run" in capsys.readouterr().err
