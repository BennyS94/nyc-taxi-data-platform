"""Set-based PostgreSQL queries for raw Yellow quality measurements."""

from datetime import date

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, aliased

from taxi_pipeline.database.models import TaxiZone, YellowTrip
from taxi_pipeline.quality.models import QualityMeasurement
from taxi_pipeline.quality.rules import DOMAIN_VALUES


def scalar_measurements(
    session: Session,
    source_file_id: int,
    source_year: int,
    source_month: int,
) -> tuple[int, dict[str, QualityMeasurement]]:
    """Evaluate temporal, numeric, zero, and null checks in one raw-table scan."""
    trip = YellowTrip
    start = date(source_year, source_month, 1)
    end = date(source_year + (source_month == 12), source_month % 12 + 1, 1)
    conditions = {
        "pickup_outside_source_month": and_(
            trip.pickup_datetime.is_not(None),
            or_(trip.pickup_datetime < start, trip.pickup_datetime >= end),
        ),
        "dropoff_before_pickup": trip.dropoff_datetime < trip.pickup_datetime,
        "negative_trip_distance": trip.trip_distance < 0,
        "negative_fare_amount": trip.fare_amount < 0,
        "negative_total_amount": trip.total_amount < 0,
        "negative_extra": trip.extra < 0,
        "negative_mta_tax": trip.mta_tax < 0,
        "negative_tip_amount": trip.tip_amount < 0,
        "negative_tolls_amount": trip.tolls_amount < 0,
        "negative_improvement_surcharge": trip.improvement_surcharge < 0,
        "negative_congestion_surcharge": trip.congestion_surcharge < 0,
        "negative_airport_fee": trip.airport_fee < 0,
        "negative_cbd_congestion_fee": trip.cbd_congestion_fee < 0,
        "zero_trip_distance": trip.trip_distance == 0,
        "zero_passenger_count": trip.passenger_count == 0,
        "passenger_count_null_rate": trip.passenger_count.is_(None),
        "rate_code_null_rate": trip.rate_code_id.is_(None),
        "store_and_fwd_null_rate": trip.store_and_fwd_flag.is_(None),
        "congestion_surcharge_null_rate": trip.congestion_surcharge.is_(None),
        "airport_fee_null_rate": trip.airport_fee.is_(None),
    }
    statement = select(
        func.count().label("rows_checked"),
        *(func.count().filter(condition).label(name) for name, condition in conditions.items()),
    ).where(trip.source_file_id == source_file_id)
    row = session.execute(statement).mappings().one()
    total = int(row["rows_checked"])
    return total, {
        name: QualityMeasurement(rows_checked=total, rows_failed=int(row[name]))
        for name in conditions
    }


def domain_measurements(
    session: Session,
    source_file_id: int,
    rows_checked: int,
) -> dict[str, QualityMeasurement]:
    """Evaluate documented domains and retain compact unexpected-value counts."""
    measurements = {}
    for check_name, (attribute_name, allowed_values) in DOMAIN_VALUES.items():
        column = getattr(YellowTrip, attribute_name)
        rows = session.execute(
            select(column.label("value"), func.count().label("count"))
            .where(
                YellowTrip.source_file_id == source_file_id,
                column.is_not(None),
                column.not_in(allowed_values),
            )
            .group_by(column)
            .order_by(column)
        ).mappings()
        unexpected = [dict(row) for row in rows]
        measurements[check_name] = QualityMeasurement(
            rows_checked=rows_checked,
            rows_failed=sum(int(item["count"]) for item in unexpected),
            details={"unexpected_values": unexpected},
        )
    return measurements


def zone_measurements(
    session: Session,
    source_file_id: int,
    zone_source_file_id: int,
    rows_checked: int,
) -> dict[str, QualityMeasurement]:
    """Evaluate pickup and dropoff references against one loaded Taxi Zone version."""
    pickup_zone = aliased(TaxiZone)
    dropoff_zone = aliased(TaxiZone)
    row = session.execute(
        select(
            func.count()
            .filter(
                YellowTrip.pickup_location_id.is_not(None),
                pickup_zone.location_id.is_(None),
            )
            .label("unknown_pickup_zone"),
            func.count()
            .filter(
                YellowTrip.dropoff_location_id.is_not(None),
                dropoff_zone.location_id.is_(None),
            )
            .label("unknown_dropoff_zone"),
        )
        .select_from(YellowTrip)
        .outerjoin(
            pickup_zone,
            and_(
                pickup_zone.source_file_id == zone_source_file_id,
                pickup_zone.location_id == YellowTrip.pickup_location_id,
            ),
        )
        .outerjoin(
            dropoff_zone,
            and_(
                dropoff_zone.source_file_id == zone_source_file_id,
                dropoff_zone.location_id == YellowTrip.dropoff_location_id,
            ),
        )
        .where(YellowTrip.source_file_id == source_file_id)
    ).mappings().one()
    return {
        name: QualityMeasurement(rows_checked=rows_checked, rows_failed=int(row[name]))
        for name in ("unknown_pickup_zone", "unknown_dropoff_zone")
    }


def duplicate_measurement(
    session: Session,
    source_file_id: int,
    rows_checked: int,
) -> QualityMeasurement:
    """Count exact duplicate groups using equality across every source field."""
    source_columns = tuple(
        column
        for column in YellowTrip.__table__.columns
        if not column.name.startswith("_")
    )
    group_size = func.count().label("group_size")
    duplicate_groups = (
        select(group_size)
        .where(YellowTrip.source_file_id == source_file_id)
        .group_by(*source_columns)
        .having(func.count() > 1)
        .subquery()
    )
    row = session.execute(
        select(
            func.coalesce(func.sum(duplicate_groups.c.group_size), 0).label("participating_rows"),
            func.coalesce(func.sum(duplicate_groups.c.group_size - 1), 0).label("excess_rows"),
            func.count().label("duplicate_groups"),
        ).select_from(duplicate_groups)
    ).mappings().one()
    return QualityMeasurement(
        rows_checked=rows_checked,
        rows_failed=int(row["participating_rows"]),
        details={
            "duplicate_excess_rows": int(row["excess_rows"]),
            "duplicate_groups": int(row["duplicate_groups"]),
        },
    )
