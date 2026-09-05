from taxi_pipeline import cli
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
