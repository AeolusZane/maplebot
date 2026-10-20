"""Resolve map-specific matching error limits without altering global defaults."""
import math


def map_threshold(data, map_name, default):
    value=(data.get('map_monster_thresholds',{}) or {}).get(map_name)
    if isinstance(value,bool):return float(default)
    try:
        value=float(value)
        if math.isfinite(value) and .001<=value<=1:return value
    except (TypeError,ValueError):pass
    return float(default)
