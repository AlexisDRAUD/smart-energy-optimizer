from app.models.reading import Reading


def impute_missing_consumption(readings: list[Reading]) -> list[Reading]:
    """Forward-fill only the imputed value while leaving each raw NULL untouched."""
    latest_known_value: float | None = None
    for reading in readings:
        if reading.consumption_kwh_raw is not None:
            latest_known_value = reading.consumption_kwh_raw
        elif reading.consumption_kwh_imputed is None:
            reading.consumption_kwh_imputed = latest_known_value
    return readings