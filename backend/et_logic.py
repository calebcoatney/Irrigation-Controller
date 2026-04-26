def update_deficit(current_deficit: float, et_mm: float, precip_mm: float, et_coefficient: float) -> float:
    new_deficit = current_deficit + (et_mm * et_coefficient) - precip_mm
    return max(new_deficit, 0.0)


def compute_duration_seconds(deficit_mm: float, application_rate_mm_per_min: float, max_duration_seconds: int) -> int:
    if application_rate_mm_per_min <= 0:
        return max_duration_seconds
    duration_seconds = int((deficit_mm / application_rate_mm_per_min) * 60)
    return min(duration_seconds, max_duration_seconds)
