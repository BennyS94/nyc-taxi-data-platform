"""Warehouse analytics API response contracts."""

from datetime import date

from pydantic import BaseModel


class AnalyticsSummaryResponse(BaseModel):
    trip_count: int
    total_amount: float | None
    average_trip_distance_miles: float | None
    average_fare_amount: float | None
    average_tip_amount: float | None


class MonthlyAnalyticsResponse(BaseModel):
    month: date
    service_type: str
    trip_count: int
    total_amount: float | None
    average_trip_distance_miles: float | None
    average_fare_amount: float | None
    average_tip_amount: float | None


class ZoneAnalyticsResponse(BaseModel):
    location_id: int | None
    borough: str
    zone_name: str
    trip_count: int
    total_amount: float | None
