"""Aggregated dbt warehouse analytics routes."""

from datetime import date

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from taxi_pipeline.api.dependencies import DatabaseSession
from taxi_pipeline.api.routes.sources import ServiceType
from taxi_pipeline.api.schemas.analytics import (
    AnalyticsSummaryResponse,
    MonthlyAnalyticsResponse,
    ZoneAnalyticsResponse,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _validate_dates(start_date: date | None, end_date: date | None) -> None:
    if start_date is not None and end_date is not None and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date")


def _filters(service_type: ServiceType | None, start_date: date | None, end_date: date | None):
    clauses: list[str] = []
    parameters: dict[str, object] = {}
    if service_type is not None:
        clauses.append("f.service_type = :service_type")
        parameters["service_type"] = service_type.value
    if start_date is not None:
        clauses.append("d.full_date >= :start_date")
        parameters["start_date"] = start_date
    if end_date is not None:
        clauses.append("d.full_date <= :end_date")
        parameters["end_date"] = end_date
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, parameters


@router.get("/summary", response_model=AnalyticsSummaryResponse, summary="Summarize trips")
def analytics_summary(
    session: DatabaseSession,
    service_type: ServiceType | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> AnalyticsSummaryResponse:
    _validate_dates(start_date, end_date)
    where, parameters = _filters(service_type, start_date, end_date)
    row = session.execute(
        text(
            f"""
            SELECT count(*) AS trip_count,
                   sum(f.total_amount) AS total_amount,
                   avg(f.trip_distance_miles) AS average_trip_distance_miles,
                   avg(f.fare_amount) AS average_fare_amount,
                   avg(f.tip_amount) AS average_tip_amount
            FROM marts.fct_trips AS f
            JOIN marts.dim_date AS d ON d.date_key = f.pickup_date_key
            {where}
            """
        ),
        parameters,
    ).mappings().one()
    return AnalyticsSummaryResponse(**row)


@router.get(
    "/monthly",
    response_model=list[MonthlyAnalyticsResponse],
    summary="Summarize trips by month and service",
)
def monthly_analytics(
    session: DatabaseSession,
    service_type: ServiceType | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[MonthlyAnalyticsResponse]:
    _validate_dates(start_date, end_date)
    where, parameters = _filters(service_type, start_date, end_date)
    rows = session.execute(
        text(
            f"""
            SELECT date_trunc('month', d.full_date)::date AS month,
                   f.service_type,
                   count(*) AS trip_count,
                   sum(f.total_amount) AS total_amount,
                   avg(f.trip_distance_miles) AS average_trip_distance_miles,
                   avg(f.fare_amount) AS average_fare_amount,
                   avg(f.tip_amount) AS average_tip_amount
            FROM marts.fct_trips AS f
            JOIN marts.dim_date AS d ON d.date_key = f.pickup_date_key
            {where}
            GROUP BY 1, f.service_type
            ORDER BY 1, f.service_type
            """
        ),
        parameters,
    ).mappings()
    return [MonthlyAnalyticsResponse(**row) for row in rows]


@router.get(
    "/zones",
    response_model=list[ZoneAnalyticsResponse],
    summary="Rank pickup zones by trip count",
)
def zone_analytics(
    session: DatabaseSession,
    service_type: ServiceType | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(default=10, ge=1, le=100),
) -> list[ZoneAnalyticsResponse]:
    _validate_dates(start_date, end_date)
    where, parameters = _filters(service_type, start_date, end_date)
    parameters["limit"] = limit
    rows = session.execute(
        text(
            f"""
            SELECT z.location_id, z.borough, z.zone_name,
                   count(*) AS trip_count, sum(f.total_amount) AS total_amount
            FROM marts.fct_trips AS f
            JOIN marts.dim_date AS d ON d.date_key = f.pickup_date_key
            JOIN marts.dim_zone AS z ON z.zone_key = f.pickup_zone_key
            {where}
            GROUP BY z.zone_key, z.location_id, z.borough, z.zone_name
            ORDER BY trip_count DESC, z.zone_key
            LIMIT :limit
            """
        ),
        parameters,
    ).mappings()
    return [ZoneAnalyticsResponse(**row) for row in rows]
