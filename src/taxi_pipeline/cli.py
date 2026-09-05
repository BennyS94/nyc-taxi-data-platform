"""Command-line interface for directly executable pipeline components."""

import argparse
import sys
from pathlib import Path

from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from taxi_pipeline.database import get_engine
from taxi_pipeline.ingestion import IngestionResult, ingest_source
from taxi_pipeline.landing import ensure_local, inspect_source
from taxi_pipeline.metadata import SourceRegistrationResult, prepare_ingestion
from taxi_pipeline.sources import taxi_zone_source, yellow_trip_source
from taxi_pipeline.sources.models import SourceFileMetadata, SourcePartition

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    """Build the dependency-free project command parser."""
    parser = argparse.ArgumentParser(prog="python -m taxi_pipeline")
    commands = parser.add_subparsers(dest="command", required=True)
    source = commands.add_parser("source", help="manage official TLC source files")
    source_commands = source.add_subparsers(dest="source_command", required=True)

    fetch = source_commands.add_parser("fetch", help="fetch a monthly trip source")
    fetch.add_argument("--service", choices=("yellow",), required=True)
    fetch.add_argument("--year", type=int, required=True)
    fetch.add_argument("--month", type=int, required=True)

    source_commands.add_parser("fetch-zones", help="fetch the Taxi Zone Lookup")
    register = source_commands.add_parser("register", help="register a monthly source")
    register.add_argument("--service", choices=("yellow",), required=True)
    register.add_argument("--year", type=int, required=True)
    register.add_argument("--month", type=int, required=True)
    source_commands.add_parser("register-zones", help="register the Taxi Zone Lookup")

    ingest = commands.add_parser("ingest", help="ingest a monthly source into raw")
    ingest.add_argument("--service", choices=("yellow",), required=True)
    ingest.add_argument("--year", type=int, required=True)
    ingest.add_argument("--month", type=int, required=True)
    commands.add_parser("ingest-zones", help="ingest the Taxi Zone Lookup into raw")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Resolve, acquire, validate, and summarize a requested source."""
    args = build_parser().parse_args(argv)
    try:
        source = _source_from_args(args)
        ensure_local(source, REPOSITORY_ROOT)
        metadata = inspect_source(source, REPOSITORY_ROOT)
        if args.command in {"ingest", "ingest-zones"}:
            ingestion = _ingest_metadata(metadata)
            registration = None
        elif args.source_command in {"register", "register-zones"}:
            registration = _register_metadata(metadata)
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
    return yellow_trip_source(args.year, args.month)


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


def _register_with_engine(
    engine: Engine,
    metadata: SourceFileMetadata,
) -> SourceRegistrationResult:
    with Session(engine) as session, session.begin():
        return prepare_ingestion(session, metadata)


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
