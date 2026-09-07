"""Command-line interface for directly executable pipeline components."""

import argparse
import sys
from pathlib import Path

from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from taxi_pipeline.database import get_engine
from taxi_pipeline.ingestion import IngestionResult, ingest_source
from taxi_pipeline.metadata import SourceRegistrationResult, prepare_ingestion
from taxi_pipeline.quality import (
    QualityRunSummary,
    find_latest_successful_run,
    run_quality_checks,
)
from taxi_pipeline.sources import green_trip_source, taxi_zone_source, yellow_trip_source
from taxi_pipeline.sources.models import SourceFileMetadata, SourcePartition
from taxi_pipeline.storage import (
    S3LandingStorage,
    build_storage,
    find_source_file_id,
    materialize_source,
    persist_storage_metadata,
    prepare_source,
    sync_all_sources,
    sync_source,
    verify_source_storage,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    """Build the dependency-free project command parser."""
    parser = argparse.ArgumentParser(prog="python -m taxi_pipeline")
    commands = parser.add_subparsers(dest="command", required=True)
    source = commands.add_parser("source", help="manage official TLC source files")
    source_commands = source.add_subparsers(dest="source_command", required=True)

    fetch = source_commands.add_parser("fetch", help="fetch a monthly trip source")
    fetch.add_argument("--service", choices=("yellow", "green"), required=True)
    fetch.add_argument("--year", type=int, required=True)
    fetch.add_argument("--month", type=int, required=True)

    source_commands.add_parser("fetch-zones", help="fetch the Taxi Zone Lookup")
    register = source_commands.add_parser("register", help="register a monthly source")
    register.add_argument("--service", choices=("yellow", "green"), required=True)
    register.add_argument("--year", type=int, required=True)
    register.add_argument("--month", type=int, required=True)
    source_commands.add_parser("register-zones", help="register the Taxi Zone Lookup")

    ingest = commands.add_parser("ingest", help="ingest a monthly source into raw")
    ingest.add_argument("--service", choices=("yellow", "green"), required=True)
    ingest.add_argument("--year", type=int, required=True)
    ingest.add_argument("--month", type=int, required=True)
    commands.add_parser("ingest-zones", help="ingest the Taxi Zone Lookup into raw")

    quality = commands.add_parser("quality", help="evaluate raw data quality")
    quality_commands = quality.add_subparsers(dest="quality_command", required=True)
    quality_run = quality_commands.add_parser("run", help="run quality checks for a month")
    quality_run.add_argument("--service", choices=("yellow", "green"), required=True)
    quality_run.add_argument("--year", type=int, required=True)
    quality_run.add_argument("--month", type=int, required=True)

    storage = commands.add_parser("storage", help="manage durable source storage")
    storage_commands = storage.add_subparsers(dest="storage_command", required=True)
    sync = storage_commands.add_parser("sync", help="sync one registered source to S3")
    sync.add_argument("--service", choices=("yellow", "green", "zones"), required=True)
    sync.add_argument("--year", type=int)
    sync.add_argument("--month", type=int)
    storage_commands.add_parser("sync-all", help="sync every registered local source")
    verify = storage_commands.add_parser("verify", help="verify one S3 object")
    verify.add_argument("--source-file-id", type=int, required=True)
    materialize = storage_commands.add_parser("materialize", help="restore one local source")
    materialize.add_argument("--source-file-id", type=int, required=True)
    storage_commands.add_parser("check-bucket", help="verify private bucket safeguards")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Resolve, acquire, validate, and summarize a requested source."""
    args = build_parser().parse_args(argv)
    if args.command == "quality":
        return _quality_command(args)
    if args.command == "storage":
        return _storage_command(args)

    try:
        source = _source_from_args(args)
        prepared = prepare_source(source, REPOSITORY_ROOT)
        metadata = prepared.metadata
        if args.command in {"ingest", "ingest-zones"}:
            ingestion = _ingest_metadata(metadata)
            _persist_storage(ingestion.source_file_id, prepared.storage)
            registration = None
        elif args.source_command in {"register", "register-zones"}:
            registration = _register_metadata(metadata)
            _persist_storage(registration.source_file_id, prepared.storage)
            ingestion = None
        else:
            registration = None
            ingestion = None
    except (OSError, RuntimeError, SQLAlchemyError, ValueError) as error:
        print(f"Source error: {error}", file=sys.stderr)
        return 1

    if ingestion is not None:
        _print_ingestion(ingestion)
    elif registration is None:
        _print_metadata(metadata)
    else:
        _print_registration(metadata, registration)
    return 0


def _source_from_args(args: argparse.Namespace) -> SourcePartition:
    if args.command == "ingest-zones" or getattr(args, "source_command", None) in {
        "fetch-zones",
        "register-zones",
    }:
        return taxi_zone_source()
    resolver = green_trip_source if args.service == "green" else yellow_trip_source
    return resolver(args.year, args.month)


def _register_metadata(metadata: SourceFileMetadata) -> SourceRegistrationResult:
    engine = get_engine()
    try:
        return _register_with_engine(engine, metadata)
    finally:
        engine.dispose()


def _ingest_metadata(metadata: SourceFileMetadata) -> IngestionResult:
    engine = get_engine()
    try:
        return ingest_source(engine, metadata, REPOSITORY_ROOT)
    finally:
        engine.dispose()


def _quality_command(args: argparse.Namespace) -> int:
    try:
        summary = _run_quality_for_partition(args.service, args.year, args.month)
    except (RuntimeError, SQLAlchemyError, ValueError) as error:
        print(f"Quality error: {error}", file=sys.stderr)
        return 1
    _print_quality(summary)
    return 0


def _run_quality_for_partition(service: str, year: int, month: int) -> QualityRunSummary:
    engine = get_engine()
    try:
        with Session(engine) as session, session.begin():
            run_id = find_latest_successful_run(
                session,
                service_type=service,
                year=year,
                month=month,
            )
            return run_quality_checks(session, run_id)
    finally:
        engine.dispose()


def _storage_command(args: argparse.Namespace) -> int:
    try:
        if args.storage_command == "sync":
            source_file_id = find_source_file_id(args.service, args.year, args.month)
            result = sync_source(source_file_id, REPOSITORY_ROOT)
            print(f"Source file ID: {source_file_id}")
            print(f"Storage URI: {result.uri}")
        elif args.storage_command == "sync-all":
            results = sync_all_sources(REPOSITORY_ROOT)
            print(f"Sources synced: {len(results)}")
        elif args.storage_command == "verify":
            result = verify_source_storage(args.source_file_id)
            print(f"Storage verified: {result.uri}")
        elif args.storage_command == "materialize":
            path = materialize_source(args.source_file_id, REPOSITORY_ROOT)
            print(f"Materialized: {path.relative_to(REPOSITORY_ROOT)}")
        else:
            storage = build_storage()
            if not isinstance(storage, S3LandingStorage):
                raise ValueError("bucket check requires LANDING_BACKEND=s3")
            result = storage.verify_bucket()
            print(
                "Bucket: versioning={versioning}, public_access={public_access}, "
                "encryption={encryption}".format(**result)
            )
    except (OSError, RuntimeError, SQLAlchemyError, ValueError) as error:
        print(f"Storage error: {error}", file=sys.stderr)
        return 1
    return 0


def _register_with_engine(
    engine: Engine,
    metadata: SourceFileMetadata,
) -> SourceRegistrationResult:
    with Session(engine) as session, session.begin():
        return prepare_ingestion(session, metadata)


def _persist_storage(source_file_id: int, storage) -> None:
    engine = get_engine()
    try:
        persist_storage_metadata(engine, source_file_id, storage)
    finally:
        engine.dispose()


def _print_metadata(metadata: SourceFileMetadata) -> None:
    print(f"Source: {metadata.partition_key}")
    print("Status: ready")
    print(f"Path: {metadata.landing_path}")
    if metadata.row_count is not None:
        print(f"Rows: {metadata.row_count:,}")
    print(f"SHA-256: {metadata.checksum_sha256}")
    if metadata.schema_version is not None:
        print(f"Schema: {metadata.schema_version}")
    else:
        print("Structure: valid")


def _print_registration(
    metadata: SourceFileMetadata,
    registration: SourceRegistrationResult,
) -> None:
    print(f"Source: {metadata.partition_key}")
    print(f"Source file ID: {registration.source_file_id}")
    print(f"Status: {registration.source_status.value}")
    print(f"Decision: {registration.decision.value}")


def _print_ingestion(result: IngestionResult) -> None:
    print(f"Source: {result.partition_key}")
    print(f"Run: {result.run_id}")
    if result.status_reason is None:
        print(f"Rows read: {result.rows_read:,}")
    print(f"Rows loaded: {result.rows_loaded:,}")
    print(f"Status: {result.status.value}")
    if result.status_reason is not None:
        print(f"Reason: {result.status_reason.value}")


def _print_quality(summary: QualityRunSummary) -> None:
    print(f"Quality: {summary.partition_key}")
    print(f"Run: {summary.run_id}")
    print(f"Rows: {summary.rows_checked:,}")
    print(f"Checks: {summary.check_count}")
    print(f"Warnings violated: {summary.warnings_violated}")
    print(f"Errors violated: {summary.errors_violated}")
    print("Status: completed")
