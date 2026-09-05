"""Explicit quality-rule catalog for raw Yellow Taxi data."""

from taxi_pipeline.quality.models import QualityRule, QualitySeverity


def _warning(name: str, description: str) -> QualityRule:
    return QualityRule(name, QualitySeverity.WARNING, description)


def _info(name: str, description: str) -> QualityRule:
    return QualityRule(name, QualitySeverity.INFO, description)


YELLOW_RULES = (
    _warning("pickup_outside_source_month", "Pickup is outside the registered source month."),
    _warning("dropoff_before_pickup", "Dropoff precedes pickup."),
    _warning("negative_trip_distance", "Trip distance is negative."),
    _warning("negative_fare_amount", "Fare amount is negative."),
    _warning("negative_total_amount", "Total amount is negative."),
    _warning("negative_extra", "Extra amount is negative."),
    _warning("negative_mta_tax", "MTA tax is negative."),
    _warning("negative_tip_amount", "Tip amount is negative."),
    _warning("negative_tolls_amount", "Tolls amount is negative."),
    _warning("negative_improvement_surcharge", "Improvement surcharge is negative."),
    _warning("negative_congestion_surcharge", "Congestion surcharge is negative."),
    _warning("negative_airport_fee", "Airport fee is negative."),
    _warning("negative_cbd_congestion_fee", "CBD congestion fee is negative."),
    _info("zero_trip_distance", "Trip distance is zero."),
    _info("zero_passenger_count", "Passenger count is zero."),
    _info("passenger_count_null_rate", "Passenger count is null."),
    _info("rate_code_null_rate", "Rate code is null."),
    _info("store_and_fwd_null_rate", "Store-and-forward flag is null."),
    _info("congestion_surcharge_null_rate", "Congestion surcharge is null."),
    _info("airport_fee_null_rate", "Airport fee is null."),
    _warning("unexpected_vendor_id", "Vendor ID is outside the documented domain."),
    _warning("unexpected_rate_code", "Rate code is outside the documented domain."),
    _warning(
        "unexpected_store_and_fwd_flag",
        "Store-and-forward flag is outside the documented domain.",
    ),
    _warning("unexpected_payment_type", "Payment type is outside the documented domain."),
    _warning("unknown_pickup_zone", "Pickup zone is absent from the loaded Taxi Zone source."),
    _warning("unknown_dropoff_zone", "Dropoff zone is absent from the loaded Taxi Zone source."),
    _warning(
        "exact_duplicate_source_rows",
        "Rows participate in an exact duplicate group across all Yellow source fields.",
    ),
)

RULES_BY_NAME = {rule.name: rule for rule in YELLOW_RULES}

DOMAIN_VALUES = {
    "unexpected_vendor_id": ("vendor_id", (1, 2, 6, 7)),
    "unexpected_rate_code": ("rate_code_id", (1, 2, 3, 4, 5, 6, 99)),
    "unexpected_store_and_fwd_flag": ("store_and_fwd_flag", ("N", "Y")),
    "unexpected_payment_type": ("payment_type", (0, 1, 2, 3, 4, 5)),
}
