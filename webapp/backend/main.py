import base64
import glob
import json
import math
import os
import re
from functools import lru_cache
from io import BytesIO
from typing import Any

import pandas as pd
import numpy as np
import polars as pl
import plotly.express as px
import plotly.graph_objects as go
from timezonefinder import TimezoneFinder
from plotly.utils import PlotlyJSONEncoder
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))

_TILE_CANDIDATES = [
    os.path.join(ROOT_DIR, "tiles"),
    os.path.join(ROOT_DIR, "map tiles"),
]
TILE_DIR = next((p for p in _TILE_CANDIDATES if os.path.isdir(p)), _TILE_CANDIDATES[0])
ZOOM_LEVEL = 9
COORD_FILE = os.path.join(ROOT_DIR, "aerodrome_lat_long.csv")
DATA_FILE = os.path.join(ROOT_DIR, "TAF3.parquet")
SPLIT_DATA_DIR = os.path.join(ROOT_DIR, "data", "by_icao")
CLIMATE_FILE = os.path.join(ROOT_DIR, "climatedrivers.csv")
LIGHTNING_SPLIT_DIR = os.path.join(ROOT_DIR, "data", "lightning_by_icao")
LIGHTNING_RADIUS_KM = 8.0
LIGHTNING_WINDOW_MINUTES = 10
LIGHTNING_COVERAGE_START_UTC = pd.Timestamp("2008-02-25T00:00:00Z")
LIGHTNING_STATS_MIN_YEAR = 2009  # Only full-year lightning data from 2009 onwards

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTH_TO_NUM = {m: i + 1 for i, m in enumerate(MONTH_NAMES)}
SEASON_TO_MONTHS = {
    "all": tuple(range(1, 13)),
    "summer": (12, 1, 2),
    "autumn": (3, 4, 5),
    "winter": (6, 7, 8),
    "spring": (9, 10, 11),
    "tropical_wet": (10, 11, 12, 1, 2, 3, 4),
    "tropical_dry": (5, 6, 7, 8, 9),
}

DRIVER_COLUMNS = ["enso", "iod", "sam", "mjo"]
GALE_WEATHER_CATEGORIES = ["No wx", "SHRA", "TS"]
THUNDERSTORM_LEGEND_LABEL = "Thunderstorm (>2008)"
TS_LEGEND_LABEL = "TS (>2008)"

BASE_CHART_COLUMNS = {"year", "month", "hour", "TM_FULL"}
SECTION_REQUIRED_COLUMNS: dict[str, set[str]] = {
    "overview": {
        "WND_DIR", "WND_SPD", "PRCP_FM_09", "PRCP_10",
        "PRST_WX_DSC_1", "PRST_WX_PHENOM_1", "PRST_WX_DSC_2", "PRST_WX_PHENOM_2",
        "AIR_TEMP", "DWPT", "VSBY", "AWS_VSBY",
        "CEIL_CLD_AMT_1", "CEIL_CLD_AMT_2", "CEIL_CLD_HT_1", "CEIL_CLD_HT_2",
    },
    "wind": {
        "WND_DIR", "WND_SPD", "MAX_WND_GUST_10", "PRCP_10",
        "PRST_WX_DSC_1", "PRST_WX_PHENOM_1", "PRST_WX_DSC_2", "PRST_WX_PHENOM_2",
    },
    "precipitation": {
        "WND_DIR", "VSBY", "AWS_VSBY", "PRCP_10", "PRCP_FM_09",
        "PRST_WX_DSC_1", "PRST_WX_PHENOM_1", "PRST_WX_DSC_2", "PRST_WX_PHENOM_2",
    },
    "fog_low_cloud": {
        "AIR_TEMP", "DWPT", "VSBY", "AWS_VSBY", "PRCP_10", "PRCP_FM_09",
        "WND_DIR", "WND_SPD",
        "PRST_WX_DSC_1", "PRST_WX_PHENOM_1", "PRST_WX_DSC_2", "PRST_WX_PHENOM_2",
        "CEIL_CLD_AMT_1", "CEIL_CLD_AMT_2", "CEIL_CLD_HT_1", "CEIL_CLD_HT_2",
    },
    "smoke_dust": {
        "PRST_WX_PHENOM_1", "PRST_WX_PHENOM_2", "WND_SPD", "DWPT", "WND_DIR",
    },
}

SECTION_CEILING_KEYS: dict[str, tuple[str, ...]] = {
    "overview": (
        "rain_thunder",
        "temp_dewpoint_y1_min",
        "temp_dewpoint_y1_max",
        "temp_dewpoint_y2",
        "fog_low_cloud",
    ),
    "wind": (
        "gale_weather_split",
    ),
    "precipitation": (
        "monthly_precip",
    ),
    "fog_low_cloud": (
        "monthly_fog",
        "fog_share",
        "fog_cloud_joint_min",
        "fog_cloud_joint_max",
    ),
    "smoke_dust": (
        "monthly_smoke",
        "hourly_smoke",
        "scatter_wind_dewpt",
    ),
}

CEILING_COLUMNS_BY_GROUP: dict[str, tuple[str, ...]] = {
    "rain": (
        "year", "month", "TM_FULL", "PRCP_FM_09",
        "PRST_WX_DSC_1", "PRST_WX_PHENOM_1", "PRST_WX_DSC_2", "PRST_WX_PHENOM_2",
    ),
    "gale": (
        "year", "month", "TM_FULL", "WND_SPD", "MAX_WND_GUST_10",
        "PRST_WX_DSC_1", "PRST_WX_PHENOM_1", "PRST_WX_DSC_2", "PRST_WX_PHENOM_2", "PRCP_10",
    ),
    "temp": (
        "TM_FULL", "AIR_TEMP", "DWPT", "PRCP_FM_09",
    ),
    "fog": (
        "year", "month", "hour", "TM_FULL", "AIR_TEMP", "DWPT", "VSBY", "AWS_VSBY",
        "PRCP_10", "PRCP_FM_09", "PRST_WX_PHENOM_1", "PRST_WX_PHENOM_2",
        "PRST_WX_DSC_1", "PRST_WX_DSC_2", "CEIL_CLD_AMT_1", "CEIL_CLD_AMT_2",
        "CEIL_CLD_HT_1", "CEIL_CLD_HT_2",
    ),
    "smoke": (
        "year", "month", "hour", "WND_SPD", "PRST_WX_PHENOM_1", "PRST_WX_PHENOM_2",
    ),
}


def columns_for_section(section: str) -> tuple[str, ...]:
    cols = set(BASE_CHART_COLUMNS)
    cols.update(SECTION_REQUIRED_COLUMNS.get(section, SECTION_REQUIRED_COLUMNS["overview"]))
    return tuple(sorted(cols))


def ceiling_keys_for_section(section: str) -> tuple[str, ...]:
    return SECTION_CEILING_KEYS.get(section, SECTION_CEILING_KEYS["overview"])


def columns_for_ceiling_keys(keys: set[str]) -> tuple[str, ...]:
    cols: set[str] = set()
    if keys & {"rain_thunder", "monthly_precip"}:
        cols.update(CEILING_COLUMNS_BY_GROUP["rain"])
    if "gale_weather_split" in keys:
        cols.update(CEILING_COLUMNS_BY_GROUP["gale"])
    if keys & {"temp_dewpoint_y1_min", "temp_dewpoint_y1_max", "temp_dewpoint_y2"}:
        cols.update(CEILING_COLUMNS_BY_GROUP["temp"])
    if keys & {"fog_low_cloud", "monthly_fog", "fog_share", "fog_cloud_joint_min", "fog_cloud_joint_max"}:
        cols.update(CEILING_COLUMNS_BY_GROUP["fog"])
    if keys & {"monthly_smoke", "hourly_smoke", "scatter_wind_dewpt"}:
        cols.update(CEILING_COLUMNS_BY_GROUP["smoke"])
    return tuple(sorted(cols))

COORDS_DF = pd.read_csv(COORD_FILE).set_index("ICAO")
TZ_FINDER = TimezoneFinder(in_memory=True)


def split_dataset_available() -> bool:
    if not os.path.isdir(SPLIT_DATA_DIR):
        return False
    return any(name.startswith("TARGET_ICAO=") for name in os.listdir(SPLIT_DATA_DIR))


def split_partition_glob(icao: str) -> str:
    return os.path.join(SPLIT_DATA_DIR, f"TARGET_ICAO={icao}", "*.parquet")


@lru_cache(maxsize=1)
def available_airports() -> tuple[str, ...]:
    if split_dataset_available():
        airports = sorted(
            name.split("=", 1)[1]
            for name in os.listdir(SPLIT_DATA_DIR)
            if name.startswith("TARGET_ICAO=") and os.path.isdir(os.path.join(SPLIT_DATA_DIR, name))
        )
        return tuple(airports)

    if os.path.exists(DATA_FILE):
        airports = (
            pl.scan_parquet(DATA_FILE)
            .select(pl.col("TARGET_ICAO").unique())
            .collect()
            .to_series()
            .drop_nulls()
            .to_list()
        )
        return tuple(sorted(str(a) for a in airports))

    return tuple()


@lru_cache(maxsize=1)
def load_airport_df(icao: str, columns: tuple[str, ...] | None = None) -> pl.DataFrame:
    requested = set(columns) if columns else set()
    if requested:
        # Keep precipitation aliases available when one of them is requested.
        requested.update({"PRCP_FM_09", "PRCP_10"})

    if split_dataset_available():
        partition_glob = split_partition_glob(icao)
        if not glob.glob(partition_glob):
            return pl.DataFrame()
        if requested:
            scan = pl.scan_parquet(partition_glob)
            existing = set(scan.collect_schema().names())
            selected = [c for c in requested if c in existing]
            if not selected:
                return pl.DataFrame()
            df = scan.select(selected).collect()
        else:
            df = pl.read_parquet(partition_glob)
    elif os.path.exists(DATA_FILE):
        scan = pl.scan_parquet(DATA_FILE).filter(pl.col("TARGET_ICAO") == icao)
        if requested:
            existing = set(scan.collect_schema().names())
            selected = [c for c in requested if c in existing]
            if not selected:
                return pl.DataFrame()
            df = scan.select(selected).collect()
        else:
            df = scan.collect()
    else:
        return pl.DataFrame()

    if "PRCP_FM_09" not in df.columns and "PRCP_10" in df.columns:
        df = df.with_columns(pl.col("PRCP_10").alias("PRCP_FM_09"))
    if "PRCP_10" not in df.columns and "PRCP_FM_09" in df.columns:
        df = df.with_columns(pl.col("PRCP_FM_09").alias("PRCP_10"))
    if "PRCP_FM_09" not in df.columns:
        df = df.with_columns(pl.lit(None, dtype=pl.Float64).alias("PRCP_FM_09"))
    if "PRCP_10" not in df.columns:
        df = df.with_columns(pl.lit(None, dtype=pl.Float64).alias("PRCP_10"))

    optional_columns = [
        "TARGET_ICAO",
        "STN_NUM",
        "AWS_VSBY",
        "RE_WX_DSC_1",
        "RE_WX_PHENOM_1",
        "RE_WX_DSC_2",
        "RE_WX_PHENOM_2",
        "RE_WX_DSC_3",
        "RE_WX_PHENOM_3",
    ]
    if requested:
        optional_columns = [c for c in optional_columns if c in requested]
    for column in optional_columns:
        if column not in df.columns:
            df = df.with_columns(pl.lit(None).alias(column))

    return df


def lightning_dataset_available() -> bool:
    if not os.path.isdir(LIGHTNING_SPLIT_DIR):
        return False
    return any(name.startswith("TARGET_ICAO=") for name in os.listdir(LIGHTNING_SPLIT_DIR))


def lightning_partition_glob(icao: str) -> str:
    return os.path.join(LIGHTNING_SPLIT_DIR, f"TARGET_ICAO={icao}", "*.parquet")


@lru_cache(maxsize=1)
def load_lightning_df(icao: str) -> pl.DataFrame:
    schema = {
        "TARGET_ICAO": pl.Utf8,
        "LTGN_TM": pl.Datetime(time_zone="UTC"),
        "LAT": pl.Float64,
        "LONG": pl.Float64,
    }

    if not lightning_dataset_available():
        return pl.DataFrame(schema=schema)

    partition_glob = lightning_partition_glob(icao)
    if not glob.glob(partition_glob):
        return pl.DataFrame(schema=schema)

    return pl.read_parquet(partition_glob)


def airport_lat_lon(icao: str) -> tuple[float, float] | None:
    if icao not in COORDS_DF.index:
        return None
    return float(COORDS_DF.loc[icao, "LAT"]), float(COORDS_DF.loc[icao, "LONG"])


def haversine_distance_km(lat1: float, lon1: float, lat2: np.ndarray, lon2: np.ndarray) -> np.ndarray:
    r_earth_km = 6371.0
    lat1_rad = np.deg2rad(lat1)
    lon1_rad = np.deg2rad(lon1)
    lat2_rad = np.deg2rad(lat2)
    lon2_rad = np.deg2rad(lon2)

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon / 2.0) ** 2
    return 2.0 * r_earth_km * np.arcsin(np.sqrt(a))


def lightning_proximity_mask(
    obs_df: pd.DataFrame,
    icao: str,
    time_field: str = "TM_FULL",
    radius_km: float = LIGHTNING_RADIUS_KM,
    window_minutes: int = LIGHTNING_WINDOW_MINUTES,
) -> pd.Series:
    matched = pd.Series(False, index=obs_df.index)
    if obs_df.empty or time_field not in obs_df.columns:
        return matched

    coords = airport_lat_lon(icao)
    if coords is None:
        return matched
    airport_lat, airport_lon = coords

    obs_time = pd.to_datetime(obs_df[time_field], utc=True, errors="coerce")
    valid_obs = obs_time.notna()
    if not valid_obs.any():
        return matched

    lightning_df = load_lightning_df(icao)
    if lightning_df.is_empty():
        return matched

    strikes = lightning_df.select(["LTGN_TM", "LAT", "LONG"]).drop_nulls().to_pandas()
    if strikes.empty:
        return matched

    strikes["LTGN_TM"] = pd.to_datetime(strikes["LTGN_TM"], utc=True, errors="coerce")
    strikes = strikes.dropna(subset=["LTGN_TM", "LAT", "LONG"])
    if strikes.empty:
        return matched

    lat_pad = radius_km / 111.0
    lon_scale = max(0.1, math.cos(math.radians(airport_lat)))
    lon_pad = radius_km / (111.0 * lon_scale)
    strikes = strikes[
        strikes["LAT"].between(airport_lat - lat_pad, airport_lat + lat_pad)
        & strikes["LONG"].between(airport_lon - lon_pad, airport_lon + lon_pad)
    ]
    if strikes.empty:
        return matched

    distances = haversine_distance_km(
        airport_lat,
        airport_lon,
        strikes["LAT"].to_numpy(dtype=float),
        strikes["LONG"].to_numpy(dtype=float),
    )
    nearby = strikes.loc[distances <= radius_km]
    if nearby.empty:
        return matched

    strike_ns = np.sort(nearby["LTGN_TM"].astype("int64").to_numpy())
    if strike_ns.size == 0:
        return matched

    obs_ns = obs_time.loc[valid_obs].astype("int64").to_numpy()
    window_ns = int(window_minutes * 60 * 1_000_000_000)
    left = np.searchsorted(strike_ns, obs_ns - window_ns, side="left")
    right = np.searchsorted(strike_ns, obs_ns + window_ns, side="right")
    matched.loc[obs_time.loc[valid_obs].index] = (right > left)
    return matched


def lightning_day_within_radius_mask(
    obs_df: pd.DataFrame,
    icao: str,
    day_field: str = "bom_day",
    radius_km: float = LIGHTNING_RADIUS_KM,
) -> pd.Series:
    """
    Flag observation rows whose BoM day has at least one lightning strike within
    radius_km of the airport reference point.
    """
    matched = pd.Series(False, index=obs_df.index)
    if obs_df.empty or day_field not in obs_df.columns:
        return matched

    coords = airport_lat_lon(icao)
    if coords is None:
        return matched
    airport_lat, airport_lon = coords

    lightning_df = load_lightning_df(icao)
    if lightning_df.is_empty():
        return matched

    strikes = lightning_df.select(["LTGN_TM", "LAT", "LONG"]).drop_nulls().to_pandas()
    if strikes.empty:
        return matched

    strikes["LTGN_TM"] = pd.to_datetime(strikes["LTGN_TM"], utc=True, errors="coerce")
    strikes = strikes.dropna(subset=["LTGN_TM", "LAT", "LONG"])
    if strikes.empty:
        return matched

    lat_pad = radius_km / 111.0
    lon_scale = max(0.1, math.cos(math.radians(airport_lat)))
    lon_pad = radius_km / (111.0 * lon_scale)
    strikes = strikes[
        strikes["LAT"].between(airport_lat - lat_pad, airport_lat + lat_pad)
        & strikes["LONG"].between(airport_lon - lon_pad, airport_lon + lon_pad)
    ]
    if strikes.empty:
        return matched

    distances = haversine_distance_km(
        airport_lat,
        airport_lon,
        strikes["LAT"].to_numpy(dtype=float),
        strikes["LONG"].to_numpy(dtype=float),
    )
    nearby = strikes.loc[distances <= radius_km]
    if nearby.empty:
        return matched

    tz_name = airport_timezone(icao)
    nearby_local = nearby["LTGN_TM"].dt.tz_convert(tz_name)
    strike_days = set((nearby_local - pd.Timedelta(hours=9)).dt.date.tolist())
    if not strike_days:
        return matched

    matched = obs_df[day_field].isin(strike_days)
    return matched.fillna(False)


def filter_lightning_coverage_window(df: pd.DataFrame, time_field: str = "TM_FULL") -> pd.DataFrame:
    if df.empty or time_field not in df.columns:
        return df
    ts = pd.to_datetime(df[time_field], utc=True, errors="coerce")
    mask = ts.notna() & (ts >= LIGHTNING_COVERAGE_START_UTC)
    return df.loc[mask].copy()


def normalize_driver_value(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", str(value).strip().lower()).strip()
    return re.sub(r"\s+", " ", cleaned)


def normalize_driver_selection(value: str) -> str:
    normalized = normalize_driver_value(value)
    if normalized == "all":
        return "all"

    # Backward-compatible aliases if old select values are still in use.
    aliases = {
        "el nino": "el nino",
        "la nina": "la nina",
        "neutral": "neutral",
        "positive": "positive iod",
        "negative": "negative sam",
        "positive sam": "positive sam",
        "negative sam": "negative sam",
        "positive iod": "positive iod",
        "negative iod": "negative iod",
        "phase 1": "1",
        "phase 2": "2",
        "phase 3": "3",
        "phase 4": "4",
        "phase 5": "5",
        "phase 6": "6",
        "phase 7": "7",
        "phase 8": "8",
        "inactive": "inactive",
    }
    return aliases.get(normalized, normalized)


def load_climate_driver_df() -> pl.DataFrame:
    if not os.path.exists(CLIMATE_FILE):
        return pl.DataFrame(
            schema={
                "year": pl.Int32,
                "month": pl.Int32,
                "day": pl.Int32,
                "enso": pl.Utf8,
                "iod": pl.Utf8,
                "sam": pl.Utf8,
                "mjo": pl.Utf8,
                "enso_norm": pl.Utf8,
                "iod_norm": pl.Utf8,
                "sam_norm": pl.Utf8,
                "mjo_norm": pl.Utf8,
            }
        )

    raw = pl.read_csv(CLIMATE_FILE, ignore_errors=True)
    required_columns = {"Year", "Month", "Day", "ENSO", "IOD", "SAM", "MJO"}
    if not required_columns.issubset(set(raw.columns)):
        return pl.DataFrame(
            schema={
                "year": pl.Int32,
                "month": pl.Int32,
                "day": pl.Int32,
                "enso": pl.Utf8,
                "iod": pl.Utf8,
                "sam": pl.Utf8,
                "mjo": pl.Utf8,
                "enso_norm": pl.Utf8,
                "iod_norm": pl.Utf8,
                "sam_norm": pl.Utf8,
                "mjo_norm": pl.Utf8,
            }
        )

    df = (
        raw.rename(
            {
                "Year": "year",
                "Month": "month",
                "Day": "day",
                "ENSO": "enso",
                "IOD": "iod",
                "SAM": "sam",
                "MJO": "mjo",
            }
        )
        .with_columns([
            pl.col("year").cast(pl.Int32, strict=False),
            pl.col("month").cast(pl.Int32, strict=False),
            pl.col("day").cast(pl.Int32, strict=False),
            pl.col("enso").cast(pl.Utf8, strict=False),
            pl.col("iod").cast(pl.Utf8, strict=False),
            pl.col("sam").cast(pl.Utf8, strict=False),
            pl.col("mjo").cast(pl.Utf8, strict=False),
        ])
        .drop_nulls(["year", "month", "day"])
        .filter(
            pl.col("month").is_between(1, 12)
            & pl.col("day").is_between(1, 31)
        )
    )

    normalized_exprs = []
    for col_name in DRIVER_COLUMNS:
        normalized_exprs.append(
            pl.col(col_name)
            .fill_null("")
            .str.to_lowercase()
            .str.replace_all(r"[^a-z0-9]+", " ")
            .str.strip_chars()
            .str.replace_all(r"\s+", " ")
            .alias(f"{col_name}_norm")
        )

    return df.with_columns(normalized_exprs)


CLIMATE_DF = load_climate_driver_df()

PLOT_HEIGHT = 300
DEFAULT_LEGEND_ENTRY_WIDTH = 220
WIDE_LEGEND_ENTRY_WIDTH = 300
LEGEND_MARGIN_PADDING = 56
LEGEND_SYMBOL_WIDTH = 40
FOG_LOW_CLOUD_LEGEND_ORDER = [
    "Fog",
    "2000ft - 1500ft cloud",
    "1500ft - 1000ft cloud",
    "1000ft - 500ft cloud",
    "< 500ft cloud",
]
FOG_LOW_CLOUD_THRESHOLD_LABELS = {
    "below 2000ft": "2000ft - 1500ft cloud",
    "below 1500ft": "1500ft - 1000ft cloud",
    "below 1000ft": "1000ft - 500ft cloud",
    "below 500ft": "< 500ft cloud",
}
NO_DATA_MESSAGE = "No data available"

app = FastAPI(title="Aviation climatology API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


def categorize_speed(speed_mps: float) -> str:
    # ADAM wind speeds are stored in m/s; wind rose bands are in knots.
    speed = speed_mps * 1.943844
    if speed < 1:
        return "0-1 kt"
    if speed < 5:
        return "1-5 kt"
    if speed < 10:
        return "5-10 kt"
    if speed < 15:
        return "10-15 kt"
    if speed < 22:
        return "15-22 kt"
    return "22+ kt"


def contains_any_token(row_values: list[Any], tokens: list[str]) -> bool:
    joined = " ".join(str(v) for v in row_values).upper()
    return any(token in joined for token in tokens)


def token_mask_from_fields(df: pd.DataFrame, fields: list[str], tokens: list[str]) -> pd.Series:
    available_fields = [field for field in fields if field in df.columns]
    if not available_fields:
        return pd.Series(False, index=df.index)

    pattern = "|".join(re.escape(t) for t in tokens)
    merged = df[available_fields[0]].fillna("").astype(str).str.upper()
    for field in available_fields[1:]:
        merged = merged + " " + df[field].fillna("").astype(str).str.upper()
    return merged.str.contains(pattern, regex=True, na=False)


def token_mask_from_columns(df: pd.DataFrame, tokens: list[str]) -> pd.Series:
    return token_mask_from_fields(df, ["PRST_WX_PHENOM_1", "PRST_WX_PHENOM_2"], tokens)


def compute_daily_weather_flags(df: pd.DataFrame, icao: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    if df.empty:
        empty = df.copy()
        return empty, pd.DataFrame(columns=["bom_day", "bom_year", "bom_month", "Rain", "Thunderstorm"])

    work = df.copy()
    work["TM_FULL"] = pd.to_datetime(work["TM_FULL"], utc=True, errors="coerce")
    work = work.dropna(subset=["TM_FULL"])
    if work.empty:
        return work, pd.DataFrame(columns=["bom_day", "bom_year", "bom_month", "Rain", "Thunderstorm"])

    tz_name = airport_timezone(icao)
    local_ts = work["TM_FULL"].dt.tz_convert(tz_name)
    work["bom_day"] = (local_ts - pd.Timedelta(hours=9)).dt.date
    work["bom_month"] = pd.to_datetime(work["bom_day"]).dt.month
    work["bom_year"] = pd.to_datetime(work["bom_day"]).dt.year

    rain_fields = ["PRST_WX_DSC_1", "PRST_WX_PHENOM_1", "PRST_WX_DSC_2", "PRST_WX_PHENOM_2"]
    work["is_rain_token_obs"] = token_mask_from_fields(work, rain_fields, ["RA", "DZ", "SH", "TS"])
    if "PRCP_FM_09" in work.columns:
        work["is_rain_amount_obs"] = pd.to_numeric(work["PRCP_FM_09"], errors="coerce").fillna(0.0) > 0.2
    else:
        work["is_rain_amount_obs"] = False
    work["is_rain_day_obs"] = work["is_rain_token_obs"] | work["is_rain_amount_obs"]
    # Thunderstorm day = at least one strike within 8 km of ICAO on that BoM day.
    work["is_ts_day_obs"] = lightning_day_within_radius_mask(work, icao, day_field="bom_day")

    daily_flags = (
        work.groupby(["bom_day", "bom_year", "bom_month"], as_index=False)
        .agg(
            Rain=("is_rain_day_obs", "any"),
            Thunderstorm=("is_ts_day_obs", "any"),
        )
    )
    return work, daily_flags


def fog_observation_mask(df: pd.DataFrame) -> pd.Series:
    explicit_fog = token_mask_from_fields(df, ["PRST_WX_PHENOM_1", "PRST_WX_PHENOM_2"], ["FG"])

    air_temp = pd.to_numeric(df.get("AIR_TEMP"), errors="coerce")
    dewpoint = pd.to_numeric(df.get("DWPT"), errors="coerce")
    prcp_10 = pd.to_numeric(df.get("PRCP_10"), errors="coerce")
    vsby = pd.to_numeric(df.get("VSBY"), errors="coerce")
    aws_vsby = pd.to_numeric(df.get("AWS_VSBY"), errors="coerce")

    tight_temp_spread = (air_temp - dewpoint) < 2.0
    light_precip = prcp_10 < 0.2
    low_visibility = vsby.lt(1.0) | aws_vsby.lt(1.0)

    inferred_fog = tight_temp_spread & light_precip & low_visibility
    return explicit_fog | inferred_fog.fillna(False)


def fog_low_cloud_mask(df: pd.DataFrame) -> pd.Series:
    fog = fog_observation_mask(df)
    cld1 = df["CEIL_CLD_AMT_1"].fillna("").astype(str).str.startswith(("BKN", "OVC"))
    cld2 = df["CEIL_CLD_AMT_2"].fillna("").astype(str).str.startswith(("BKN", "OVC"))
    return fog | cld1 | cld2


def lowest_low_cloud_ceiling(df: pd.DataFrame) -> pd.Series:
    cld1 = df["CEIL_CLD_AMT_1"].fillna("").astype(str).str.upper().str.startswith(("BKN", "OVC"))
    cld2 = df["CEIL_CLD_AMT_2"].fillna("").astype(str).str.upper().str.startswith(("BKN", "OVC"))
    h1 = pd.to_numeric(df.get("CEIL_CLD_HT_1"), errors="coerce").where(cld1)
    h2 = pd.to_numeric(df.get("CEIL_CLD_HT_2"), errors="coerce").where(cld2)
    return pd.concat([h1, h2], axis=1).min(axis=1, skipna=True)


def extract_low_cloud_heights(df: pd.DataFrame, bucket_col: str) -> pd.DataFrame:
    low_cloud_df = df.copy()
    low_cloud_df["is_low_cloud"] = token_mask_from_fields(low_cloud_df, ["CEIL_CLD_AMT_1", "CEIL_CLD_AMT_2"], ["BKN", "OVC"])
    low_cloud_df = low_cloud_df[low_cloud_df["is_low_cloud"]].copy()
    if low_cloud_df.empty:
        return pd.DataFrame(columns=[bucket_col, "height", "Threshold"])

    height_frames = [
        low_cloud_df[[bucket_col, "CEIL_CLD_HT_1"]].rename(columns={"CEIL_CLD_HT_1": "height"}),
        low_cloud_df[[bucket_col, "CEIL_CLD_HT_2"]].rename(columns={"CEIL_CLD_HT_2": "height"}),
    ]
    height_df = pd.concat(height_frames, ignore_index=True)
    height_df["height"] = pd.to_numeric(height_df["height"], errors="coerce")
    height_df = height_df.dropna(subset=["height"])
    if height_df.empty:
        return pd.DataFrame(columns=[bucket_col, "height", "Threshold"])

    height_df["Threshold"] = "below 2000ft"
    height_df.loc[height_df["height"] < 1500, "Threshold"] = "below 1500ft"
    height_df.loc[height_df["height"] < 1000, "Threshold"] = "below 1000ft"
    height_df.loc[height_df["height"] < 500, "Threshold"] = "below 500ft"
    return height_df


def monthly_flag_frequency(
    df: pd.DataFrame,
    tokens: list[str],
    target_col: str,
    fields: list[str] | None = None,
) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["year", "month", target_col, "date"])
    source_fields = fields or ["PRST_WX_PHENOM_1", "PRST_WX_PHENOM_2"]
    df[target_col] = token_mask_from_fields(df, source_fields, tokens).astype(int)
    monthly = df.groupby(["year", "month"])[target_col].sum().reset_index()
    monthly["date"] = pd.to_datetime(dict(year=monthly["year"], month=monthly["month"], day=1))
    return monthly


def selected_month_numbers(month_start: int, month_end: int, invert: bool = False) -> list[int]:
    selected: set[int] = set()
    for month in range(1, 13):
        if invert:
            # Keep boundary months when inverted to mirror build_range_mask behavior.
            keep = (month <= month_start) or (month >= month_end)
        elif month_start <= month_end:
            keep = month_start <= month <= month_end
        else:
            keep = month >= month_start or month <= month_end
        if keep:
            selected.add(month)

    if not selected:
        return []

    anchor = month_end if invert else month_start
    ordered: list[int] = []
    for offset in range(12):
        month = ((anchor - 1 + offset) % 12) + 1
        if month in selected:
            ordered.append(month)
    return ordered


def month_labels_for_numbers(month_numbers: list[int]) -> list[str]:
    return [MONTH_NAMES[m - 1] for m in month_numbers]


def paired_monthly_frequency(df: pd.DataFrame, categories: dict[str, list[str]]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["month", "Type", "Count", "Month"])

    monthly_frames: list[pd.DataFrame] = []
    for label, spec in categories.items():
        tokens = spec["tokens"]
        fields = spec["fields"]
        monthly = monthly_flag_frequency(df.copy(), tokens, label, fields=fields)
        if monthly.empty:
            continue
        monthly = monthly.groupby("month")[label].mean().reset_index()
        monthly["Type"] = label
        monthly.rename(columns={label: "Count"}, inplace=True)
        monthly_frames.append(monthly)

    if not monthly_frames:
        return pd.DataFrame(columns=["month", "Type", "Count", "Month"])

    paired = pd.concat(monthly_frames, ignore_index=True)
    paired["Month"] = paired["month"].apply(lambda m: MONTH_NAMES[m - 1])
    paired["Month"] = pd.Categorical(paired["Month"], categories=MONTH_NAMES, ordered=True)
    paired = paired.sort_values(["Month", "Type"])
    return paired


def average_monthly_gale_weather_counts(
    df: pd.DataFrame,
    icao: str,
    month_numbers: list[int],
) -> pd.DataFrame:
    """
    Return average monthly gale counts split by weather category.
    Missing month/category/year combinations are zero-filled before averaging so
    stacked category means reconcile with total monthly means.
    """
    full_index = pd.MultiIndex.from_product(
        [month_numbers, GALE_WEATHER_CATEGORIES],
        names=["month", "Category"],
    )
    empty = pd.DataFrame(index=full_index).reset_index()
    empty["Count"] = 0.0

    if df.empty:
        return empty

    years = (
        pd.to_numeric(df.get("year"), errors="coerce")
        .dropna()
        .astype(int)
        .unique()
        .tolist()
    )
    if not years:
        return empty

    # Gale definition: WND_SPD > 34 knots OR MAX_WND_GUST_10 > 41 knots.
    # ADAM stores speeds in m/s, so convert thresholds to 17.49 / 21.09 m/s.
    gale_mask = (df["WND_SPD"].fillna(-9999) > 17.49) | (df["MAX_WND_GUST_10"].fillna(-9999) > 21.09)
    gale_obs = df[gale_mask].copy()

    if not gale_obs.empty:
        dsc = (gale_obs["PRST_WX_DSC_1"].fillna("").astype(str) + " " + gale_obs["PRST_WX_DSC_2"].fillna("").astype(str)).str.upper()
        phenom = (gale_obs["PRST_WX_PHENOM_1"].fillna("").astype(str) + " " + gale_obs["PRST_WX_PHENOM_2"].fillna("").astype(str)).str.upper()
        prcp_10 = pd.to_numeric(gale_obs["PRCP_10"], errors="coerce").fillna(0.0)

        is_ts = lightning_proximity_mask(gale_obs, icao, time_field="TM_FULL")
        is_shra = (dsc.str.contains("SH", regex=False) & phenom.str.contains("RA", regex=False)) | (prcp_10 > 0.2)

        gale_obs["Category"] = "No wx"
        gale_obs.loc[is_shra, "Category"] = "SHRA"
        gale_obs.loc[is_ts, "Category"] = "TS"

        monthly_counts = gale_obs.groupby(["year", "month", "Category"]).size().reset_index(name="Gales")
    else:
        monthly_counts = pd.DataFrame(columns=["year", "month", "Category", "Gales"])

    # Non-TS categories use all selected years as the denominator.
    non_ts_cats = ["No wx", "SHRA"]
    full_year_month_non_ts = pd.MultiIndex.from_product(
        [sorted(years), month_numbers, non_ts_cats],
        names=["year", "month", "Category"],
    )
    non_ts_counts = (
        monthly_counts[monthly_counts["Category"].isin(non_ts_cats)]
        .set_index(["year", "month", "Category"])
        .reindex(full_year_month_non_ts, fill_value=0)
        .reset_index()
    )

    # TS uses only years >= LIGHTNING_STATS_MIN_YEAR as the denominator.
    ts_years = sorted([y for y in years if y >= LIGHTNING_STATS_MIN_YEAR])
    if ts_years:
        full_year_month_ts = pd.MultiIndex.from_product(
            [ts_years, month_numbers, ["TS"]],
            names=["year", "month", "Category"],
        )
        ts_counts = (
            monthly_counts[monthly_counts["Category"] == "TS"]
            .set_index(["year", "month", "Category"])
            .reindex(full_year_month_ts, fill_value=0)
            .reset_index()
        )
        combined_counts = pd.concat([non_ts_counts, ts_counts], ignore_index=True)
    else:
        combined_counts = non_ts_counts

    monthly_avg = (
        combined_counts.groupby(["month", "Category"], as_index=False)["Gales"]
        .mean()
        .rename(columns={"Gales": "Count"})
    )

    monthly_avg = empty.drop(columns=["Count"]).merge(monthly_avg, on=["month", "Category"], how="left")
    monthly_avg["Count"] = monthly_avg["Count"].fillna(0.0)
    return monthly_avg


def build_fog_low_cloud_frequency_figure(
    fog_df: pd.DataFrame,
    title: str,
    icao: str,
    month_numbers: list[int],
) -> go.Figure:
    month_labels = month_labels_for_numbers(month_numbers)
    month_positions = list(range(1, len(month_numbers) + 1))
    combined = average_monthly_fog_low_cloud_days(fog_df, icao)

    threshold_order = ["below 500ft", "below 1000ft", "below 1500ft", "below 2000ft"]
    combined_sorted = combined.copy()
    combined_sorted["Threshold"] = combined_sorted["Threshold"].fillna("N/A")

    threshold_colors = {
        "below 500ft": "#8b0000",
        "below 1000ft": "#c62828",
        "below 1500ft": "#e57373",
        "below 2000ft": "#ef9a9a",
    }

    low_cloud_stack = (
        combined_sorted[combined_sorted["Type"] == "Low cloud"]
        .pivot_table(index="Month", columns="Threshold", values="Count", aggfunc="sum")
        .reindex(month_labels)
        .fillna(0.0)
    )
    fog_by_month = (
        combined_sorted[combined_sorted["Type"] == "Fog"]
        .groupby("Month")["Count"]
        .sum()
        .reindex(month_labels)
        .fillna(0.0)
    )

    total_low_cloud = float(low_cloud_stack.to_numpy().sum()) if not low_cloud_stack.empty else 0.0
    total_fog = float(fog_by_month.sum()) if not fog_by_month.empty else 0.0
    if (total_low_cloud + total_fog) <= 0.0:
        return build_placeholder_figure(title)

    low_cloud_x = [month - 0.22 for month in month_positions]
    fog_x = [month + 0.22 for month in month_positions]
    bar_width = 0.38

    fig = go.Figure()
    fig.add_bar(
        x=low_cloud_x,
        y=[0.0] * len(month_labels),
        showlegend=False,
        hoverinfo="skip",
        marker_color="rgba(0,0,0,0)",
        width=bar_width,
    )
    fig.add_bar(
        x=fog_x,
        y=[0.0] * len(month_labels),
        showlegend=False,
        hoverinfo="skip",
        marker_color="rgba(0,0,0,0)",
        width=bar_width,
    )

    for threshold in threshold_order:
        y_values = low_cloud_stack[threshold].astype(float).tolist() if threshold in low_cloud_stack.columns else [0.0] * len(month_labels)
        display_label = FOG_LOW_CLOUD_THRESHOLD_LABELS[threshold]
        fig.add_bar(
            x=low_cloud_x,
            y=y_values,
            name=display_label,
            marker_color=threshold_colors[threshold],
            customdata=month_labels,
            width=bar_width,
            hovertemplate=(
                "Month: %{customdata}<br>"
                f"{display_label}: %{{y:.2f}}<extra></extra>"
            ),
        )

    fig.add_bar(
        x=fog_x,
        y=fog_by_month.astype(float).tolist(),
        name="Fog",
        marker_color="#d4af37",
        customdata=month_labels,
        width=bar_width,
        hovertemplate="Month: %{customdata}<br>Fog: %{y:.2f}<extra></extra>",
    )

    fig.update_layout(
        title=title,
        barmode="stack",
        legend_title_text="Category",
    )
    fig.update_xaxes(
        title_text="",
        tickmode="array",
        tickvals=month_positions,
        ticktext=month_labels,
        showgrid=False,
        range=[0.2, len(month_positions) + 0.8],
    )
    fig.update_yaxes(title_text="Avg Days/Month")
    apply_side_legend(
        fig,
        width_px=WIDE_LEGEND_ENTRY_WIDTH,
        font_size=10,
        top_margin=36,
        title_text="Category",
        bgcolor="rgba(255,255,255,0.92)",
    )
    return fig


def build_placeholder_figure(title: str, _subtitle: str = NO_DATA_MESSAGE) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        text=NO_DATA_MESSAGE,
        showarrow=False,
        font=dict(size=14, color="#435a84"),
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig.update_layout(
        title=dict(text=title, font=dict(size=14)),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    return fig


def split_fog_day_type_datasets(fog_df: pd.DataFrame, icao: str) -> dict[str, tuple[pd.DataFrame, str]]:
    if fog_df.empty:
        empty = fog_df.copy()
        return {
            "all": (empty, "All Days"),
            "rain": (empty, "Rain Days"),
            "non_rain": (empty, "Non-rain Days"),
        }

    work, daily_flags = compute_daily_weather_flags(fog_df, icao)

    if work.empty:
        return {
            "all": (work, "All Days"),
            "rain": (work, "Rain Days"),
            "non_rain": (work, "Non-rain Days"),
        }

    rain_by_day = daily_flags[["bom_day", "Rain"]].rename(columns={"Rain": "is_rain_day"})
    work = work.merge(rain_by_day, on="bom_day", how="left")
    work["is_rain_day"] = work["is_rain_day"].fillna(False)

    return {
        "all": (work, "All Days"),
        "rain": (work[work["is_rain_day"]].copy(), "Rain Days"),
        "non_rain": (work[~work["is_rain_day"]].copy(), "Non-rain Days"),
    }


def compute_fog_low_cloud_day_flags(
    fog_df: pd.DataFrame,
    icao: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if fog_df.empty:
        empty_work = fog_df.copy()
        empty_daily = pd.DataFrame(
            columns=[
                "bom_day",
                "bom_year",
                "bom_month",
                "Fog",
                "below 2000ft",
                "below 1500ft",
                "below 1000ft",
                "below 500ft",
            ]
        )
        empty_hourly = pd.DataFrame(
            columns=[
                "bom_day",
                "bom_year",
                "hour",
                "Fog",
                "below 2000ft",
                "below 1500ft",
                "below 1000ft",
                "below 500ft",
            ]
        )
        return empty_work, empty_daily, empty_hourly

    work = fog_df.copy()
    work["TM_FULL"] = pd.to_datetime(work["TM_FULL"], utc=True, errors="coerce")
    work = work.dropna(subset=["TM_FULL"])
    if work.empty:
        return compute_fog_low_cloud_day_flags(pd.DataFrame(), icao)

    tz_name = airport_timezone(icao)
    local_ts = work["TM_FULL"].dt.tz_convert(tz_name)
    work["bom_day"] = (local_ts - pd.Timedelta(hours=9)).dt.date
    work["bom_year"] = pd.to_datetime(work["bom_day"]).dt.year
    work["bom_month"] = pd.to_datetime(work["bom_day"]).dt.month
    if "hour" not in work.columns:
        work["hour"] = work["TM_FULL"].dt.hour

    work["Fog"] = fog_observation_mask(work)

    work["lowest_low_cloud_ceiling"] = lowest_low_cloud_ceiling(work)

    daily_flags = work.groupby(["bom_day", "bom_year", "bom_month"], as_index=False).agg(
        Fog=("Fog", "any"),
        lowest_low_cloud_ceiling=("lowest_low_cloud_ceiling", "min"),
    )
    hourly_flags = work.groupby(["bom_day", "bom_year", "hour"], as_index=False).agg(
        Fog=("Fog", "any"),
        lowest_low_cloud_ceiling=("lowest_low_cloud_ceiling", "min"),
    )

    for flags_df in (daily_flags, hourly_flags):
        lowest_ceiling = pd.to_numeric(flags_df["lowest_low_cloud_ceiling"], errors="coerce")
        flags_df["below 2000ft"] = lowest_ceiling.lt(2000) & lowest_ceiling.ge(1500)
        flags_df["below 1500ft"] = lowest_ceiling.lt(1500) & lowest_ceiling.ge(1000)
        flags_df["below 1000ft"] = lowest_ceiling.lt(1000) & lowest_ceiling.ge(500)
        flags_df["below 500ft"] = lowest_ceiling.lt(500)

    return work, daily_flags, hourly_flags


def average_monthly_fog_low_cloud_days(fog_df: pd.DataFrame, icao: str) -> pd.DataFrame:
    _, daily_flags, _ = compute_fog_low_cloud_day_flags(fog_df, icao)
    if daily_flags.empty:
        return pd.DataFrame(columns=["Month", "Count", "Type", "Threshold"])

    monthly_counts = (
        daily_flags.groupby(["bom_year", "bom_month"], as_index=False)
        .agg(
            Fog=("Fog", "sum"),
            **{
                "below 2000ft": ("below 2000ft", "sum"),
                "below 1500ft": ("below 1500ft", "sum"),
                "below 1000ft": ("below 1000ft", "sum"),
                "below 500ft": ("below 500ft", "sum"),
            },
        )
    )
    monthly_avg = (
        monthly_counts.groupby("bom_month", as_index=False)[["Fog", "below 2000ft", "below 1500ft", "below 1000ft", "below 500ft"]]
        .mean()
        .rename(columns={"bom_month": "month"})
    )
    monthly_avg["Month"] = monthly_avg["month"].apply(lambda m: MONTH_NAMES[m - 1])

    fog_monthly = monthly_avg[["Month", "Fog"]].rename(columns={"Fog": "Count"})
    fog_monthly["Type"] = "Fog"
    fog_monthly["Threshold"] = None

    low_cloud_monthly = monthly_avg.melt(
        id_vars=["month", "Month"],
        value_vars=["below 2000ft", "below 1500ft", "below 1000ft", "below 500ft"],
        var_name="Threshold",
        value_name="Count",
    )
    low_cloud_monthly["Type"] = "Low cloud"

    return pd.concat(
        [
            fog_monthly[["Month", "Count", "Type", "Threshold"]],
            low_cloud_monthly[["Month", "Count", "Type", "Threshold"]],
        ],
        ignore_index=True,
    )


def average_hourly_fog_low_cloud_days(fog_df: pd.DataFrame, icao: str) -> pd.DataFrame:
    _, _, hourly_flags = compute_fog_low_cloud_day_flags(fog_df, icao)
    if hourly_flags.empty:
        return pd.DataFrame(columns=["Hour", "Count", "Type", "Threshold"])

    hourly_counts = (
        hourly_flags.groupby(["bom_year", "hour"], as_index=False)
        .agg(
            Fog=("Fog", "sum"),
            **{
                "below 2000ft": ("below 2000ft", "sum"),
                "below 1500ft": ("below 1500ft", "sum"),
                "below 1000ft": ("below 1000ft", "sum"),
                "below 500ft": ("below 500ft", "sum"),
            },
        )
    )
    hourly_avg = hourly_counts.groupby("hour", as_index=False)[["Fog", "below 2000ft", "below 1500ft", "below 1000ft", "below 500ft"]].mean()
    hourly_avg["Hour"] = hourly_avg["hour"].astype(int).astype(str)

    fog_hourly = hourly_avg[["Hour", "Fog"]].rename(columns={"Fog": "Count"})
    fog_hourly["Type"] = "Fog"
    fog_hourly["Threshold"] = None

    low_cloud_hourly = hourly_avg.melt(
        id_vars=["hour", "Hour"],
        value_vars=["below 2000ft", "below 1500ft", "below 1000ft", "below 500ft"],
        var_name="Threshold",
        value_name="Count",
    )
    low_cloud_hourly["Type"] = "Low cloud"

    return pd.concat(
        [
            fog_hourly[["Hour", "Count", "Type", "Threshold"]],
            low_cloud_hourly[["Hour", "Count", "Type", "Threshold"]],
        ],
        ignore_index=True,
    )


def monthly_fog_low_cloud_dewpoint_by_category(fog_df: pd.DataFrame) -> pd.DataFrame:
    if fog_df.empty:
        return pd.DataFrame(columns=["month", "Category", "AvgDWPT"])

    dewpoint_df = fog_df.copy()
    dewpoint_df["DWPT"] = pd.to_numeric(dewpoint_df["DWPT"], errors="coerce")
    dewpoint_df = dewpoint_df.dropna(subset=["DWPT"])
    if dewpoint_df.empty:
        return pd.DataFrame(columns=["month", "Category", "AvgDWPT"])

    dewpoint_df["is_fog"] = fog_observation_mask(dewpoint_df)
    lowest_ceiling = lowest_low_cloud_ceiling(dewpoint_df)

    category_masks = [
        ("Fog", dewpoint_df["is_fog"]),
        ("2000ft - 1500ft cloud", lowest_ceiling.lt(2000) & lowest_ceiling.ge(1500)),
        ("1500ft - 1000ft cloud", lowest_ceiling.lt(1500) & lowest_ceiling.ge(1000)),
        ("1000ft - 500ft cloud", lowest_ceiling.lt(1000) & lowest_ceiling.ge(500)),
        ("< 500ft cloud", lowest_ceiling.lt(500)),
    ]

    frames: list[pd.DataFrame] = []
    for label, mask in category_masks:
        masked = dewpoint_df[mask].copy()
        if masked.empty:
            continue

        monthly_avg = masked.groupby("month", as_index=False)["DWPT"].mean()
        monthly_avg = monthly_avg.rename(columns={"DWPT": "AvgDWPT"})
        monthly_avg["Category"] = label
        frames.append(monthly_avg)

    if not frames:
        return pd.DataFrame(columns=["month", "Category", "AvgDWPT"])

    return pd.concat(frames, ignore_index=True)


@lru_cache(maxsize=512)
def airport_timezone(icao: str) -> str:
    if icao in COORDS_DF.index:
        lat = float(COORDS_DF.loc[icao, "LAT"])
        lon = float(COORDS_DF.loc[icao, "LONG"])
        tz_name = TZ_FINDER.timezone_at(lat=lat, lng=lon)
        if tz_name:
            return tz_name
    return "UTC"


def monthly_avg_daily_extremes(temp_df: pd.DataFrame, icao: str) -> pd.DataFrame:
    if temp_df.empty:
        return pd.DataFrame()

    work = temp_df.copy()
    work["TM_FULL"] = pd.to_datetime(work["TM_FULL"], utc=True, errors="coerce")
    work = work.dropna(subset=["TM_FULL"])
    if work.empty:
        return pd.DataFrame()

    tz_name = airport_timezone(icao)
    local_ts = work["TM_FULL"].dt.tz_convert(tz_name)

    # BOM max/min are tied to a local 9am clock-time observation window.
    work["bom_day"] = (local_ts - pd.Timedelta(hours=9)).dt.date

    daily = (
        work.groupby("bom_day", as_index=False)
        .agg(
            daily_max_t=("AIR_TEMP", "max"),
            daily_min_t=("AIR_TEMP", "min"),
            daily_max_td=("DWPT", "max"),
            daily_min_td=("DWPT", "min"),
        )
    )
    if daily.empty:
        return pd.DataFrame()

    daily["month"] = pd.to_datetime(daily["bom_day"]).dt.month
    monthly = (
        daily.groupby("month", as_index=False)
        .agg(
            avg_daily_max_t=("daily_max_t", "mean"),
            avg_daily_min_t=("daily_min_t", "mean"),
            avg_daily_max_td=("daily_max_td", "mean"),
            avg_daily_min_td=("daily_min_td", "mean"),
        )
    )

    monthly["Month"] = monthly["month"].apply(lambda m: MONTH_NAMES[m - 1])
    monthly["Month"] = pd.Categorical(monthly["Month"], categories=MONTH_NAMES, ordered=True)
    monthly = monthly.sort_values("Month")
    monthly = monthly.rename(
        columns={
            "avg_daily_max_t": "Avg Daily Max T",
            "avg_daily_min_t": "Avg Daily Min T",
            "avg_daily_max_td": "Avg Daily Max Td",
            "avg_daily_min_td": "Avg Daily Min Td",
        }
    )
    return monthly


def monthly_avg_precipitation_mm(precip_df: pd.DataFrame, icao: str) -> pd.DataFrame:
    if precip_df.empty or "PRCP_FM_09" not in precip_df.columns:
        return pd.DataFrame()

    work = precip_df.copy()
    work["TM_FULL"] = pd.to_datetime(work["TM_FULL"], utc=True, errors="coerce")
    work["PRCP_FM_09"] = pd.to_numeric(work["PRCP_FM_09"], errors="coerce")
    work = work.dropna(subset=["TM_FULL"])
    if work.empty:
        return pd.DataFrame()

    tz_name = airport_timezone(icao)
    local_ts = work["TM_FULL"].dt.tz_convert(tz_name)

    # BOM precipitation totals align to the local 9am observation day.
    work["bom_day"] = (local_ts - pd.Timedelta(hours=9)).dt.date
    work["bom_year"] = pd.to_datetime(work["bom_day"]).dt.year
    work["bom_month"] = pd.to_datetime(work["bom_day"]).dt.month

    daily = (
        work.groupby(["bom_day", "bom_year", "bom_month"], as_index=False)
        .agg(daily_precip_mm=("PRCP_FM_09", "max"))
        .dropna(subset=["daily_precip_mm"])
    )
    if daily.empty:
        return pd.DataFrame()

    monthly = (
        daily.groupby(["bom_year", "bom_month"], as_index=False)
        .agg(monthly_precip_mm=("daily_precip_mm", "sum"))
    )
    if monthly.empty:
        return pd.DataFrame()

    monthly = (
        monthly.groupby("bom_month", as_index=False)["monthly_precip_mm"]
        .mean()
        .rename(columns={"bom_month": "month", "monthly_precip_mm": "Avg Monthly Precip"})
    )
    monthly["Month"] = monthly["month"].apply(lambda m: MONTH_NAMES[m - 1])
    monthly["Month"] = pd.Categorical(monthly["Month"], categories=MONTH_NAMES, ordered=True)
    monthly = monthly.sort_values("Month")
    return monthly


def build_range_mask(col_name: str, selected_range: tuple[int, int], invert: bool = False) -> pl.Expr:
    start, end = selected_range
    if invert:
        return (pl.col(col_name) <= start) | (pl.col(col_name) >= end)
    return pl.col(col_name).is_between(start, end)


def build_season_mask(season: str) -> pl.Expr:
    months = SEASON_TO_MONTHS.get(season, SEASON_TO_MONTHS["all"])
    return pl.col("month").is_in(months)


def apply_climate_driver_filters(
    df: pl.DataFrame,
    *,
    enso: str,
    iod: str,
    sam: str,
    mjo: str,
) -> pl.DataFrame:
    selected = {
        "enso": normalize_driver_selection(enso),
        "iod": normalize_driver_selection(iod),
        "sam": normalize_driver_selection(sam),
        "mjo": normalize_driver_selection(mjo),
    }
    selected = {k: v for k, v in selected.items() if v != "all"}

    if not selected:
        return df

    if CLIMATE_DF.is_empty():
        return df.head(0)

    joined = (
        df.with_columns(pl.col("TM_FULL").dt.day().cast(pl.Int32).alias("day"))
        .join(CLIMATE_DF, on=["year", "month", "day"], how="inner")
    )

    for driver, value in selected.items():
        joined = joined.filter(pl.col(f"{driver}_norm") == value)

    return joined.drop(["day"]) if "day" in joined.columns else joined


@lru_cache(maxsize=8)
def get_centered_background(lat: float, lon: float, zoom: int = 9, crop_size: int = 512) -> str:
    n = 2.0 ** zoom

    x_frac = (lon + 180.0) / 360.0 * n
    lat_rad = math.radians(lat)
    y_frac = (1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n

    xtile_center = int(x_frac)
    ytile_center = int(y_frac)

    x_offset = int((x_frac - xtile_center) * 256)
    y_offset = int((y_frac - ytile_center) * 256)

    canvas = Image.new("RGB", (768, 768), (230, 230, 230))
    loaded_center = False

    for i, dx in enumerate([-1, 0, 1]):
        for j, dy in enumerate([-1, 0, 1]):
            x_clamped = xtile_center + dx
            y_clamped = ytile_center + dy
            tile_path = os.path.join(TILE_DIR, str(x_clamped), f"{y_clamped}.jpg")

            if os.path.exists(tile_path):
                try:
                    tile = Image.open(tile_path)
                    canvas.paste(tile, (i * 256, j * 256))
                    if i == 1 and j == 1:
                        loaded_center = True
                except Exception:
                    tile = Image.new("RGB", (256, 256), (220, 220, 220))
                    canvas.paste(tile, (i * 256, j * 256))
            else:
                tile = Image.new("RGB", (256, 256), (220, 220, 220))
                canvas.paste(tile, (i * 256, j * 256))

    if not loaded_center:
        raise RuntimeError(f"Center tile missing near X={xtile_center}, Y={ytile_center} in {TILE_DIR}")

    left = (256 + x_offset) - (crop_size // 2)
    top = (256 + y_offset) - (crop_size // 2)
    right = left + crop_size
    bottom = top + crop_size

    cropped_canvas = canvas.crop((left, top, right, bottom))

    buffer = BytesIO()
    cropped_canvas.save(buffer, format="PNG")
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.getvalue()).decode()

    return f"data:image/png;base64,{img_base64}"


def apply_polar_background(fig: go.Figure, img_base64: str, *, opacity: float = 0.7, scale: float = 1.1) -> None:
    polar_layout = fig.layout.polar.to_plotly_json() if fig.layout.polar else {}
    domain = polar_layout.get("domain", {})
    domain_x = domain.get("x", [0.0, 1.0])
    domain_y = domain.get("y", [0.0, 1.0])

    x0, x1 = float(domain_x[0]), float(domain_x[1])
    y0, y1 = float(domain_y[0]), float(domain_y[1])
    center_x = (x0 + x1) / 2.0
    center_y = (y0 + y1) / 2.0
    size_x = (x1 - x0) * scale
    size_y = (y1 - y0) * scale

    fig.update_layout(
        images=[
            dict(
                source=img_base64,
                xref="paper",
                yref="paper",
                x=center_x,
                y=center_y,
                sizex=size_x,
                sizey=size_y,
                xanchor="center",
                yanchor="middle",
                sizing="contain",
                layer="below",
                opacity=opacity,
            )
        ]
    )


def apply_side_legend(
    fig: go.Figure,
    *,
    width_px: int,
    font_size: int,
    top_margin: int,
    title_text: str | None = None,
    groupclick: str | None = None,
    bgcolor: str = "rgba(255,255,255,0.88)",
    bordercolor: str = "#c7d4ef",
    borderwidth: int = 1,
    left_margin: int = 36,
    bottom_margin: int = 22,
) -> None:
    current_legend = fig.layout.legend.to_plotly_json() if fig.layout.legend else {}
    current_margin = fig.layout.margin.to_plotly_json() if fig.layout.margin else {}

    legend_config: dict[str, Any] = {
        **current_legend,
        "x": 1.0,
        "xanchor": "left",
        "y": 0.5,
        "yanchor": "middle",
        "font": {"size": font_size},
        "bgcolor": bgcolor,
        "bordercolor": bordercolor,
        "borderwidth": borderwidth,
        "entrywidthmode": "pixels",
        "entrywidth": width_px,
        "itemwidth": LEGEND_SYMBOL_WIDTH,
    }
    if title_text is not None:
        legend_config["title_text"] = title_text
    if groupclick is not None:
        legend_config["groupclick"] = groupclick

    margin_config = {
        **current_margin,
        "l": left_margin,
        "r": max(int(current_margin.get("r", 0) or 0), width_px + LEGEND_MARGIN_PADDING),
        "t": top_margin,
        "b": bottom_margin,
    }

    fig.update_layout(legend=legend_config, margin=margin_config)

    for trace in fig.data:
        if hasattr(trace, "_valid_props") and "legendwidth" in trace._valid_props:
            trace.legendwidth = width_px


def apply_common_layout(fig: Any, height: int = PLOT_HEIGHT) -> None:
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#333333", family="Source Sans 3, Open Sans, Arial, sans-serif"),
        title=dict(x=0.01, xanchor="left", y=0.98, yanchor="top", font=dict(size=14)),
        margin=dict(l=36, r=DEFAULT_LEGEND_ENTRY_WIDTH + LEGEND_MARGIN_PADDING, t=36, b=22),
        height=height,
    )
    apply_side_legend(fig, width_px=DEFAULT_LEGEND_ENTRY_WIDTH, font_size=11, top_margin=36)


def apply_frequency_panel_layout(fig: Any, *, extra_height: int = 34, bottom_margin: int = 12) -> None:
    current_margin = fig.layout.margin.to_plotly_json() if fig.layout.margin else {}
    current_height = getattr(fig.layout, "height", None)

    update_kwargs: dict[str, Any] = {
        "margin": {
            **current_margin,
            "b": bottom_margin,
        }
    }

    if current_height is not None:
        update_kwargs["height"] = int(current_height) + extra_height

    fig.update_layout(**update_kwargs)
    fig.update_xaxes(title=None, automargin=False, ticklabelstandoff=2)
    fig.update_yaxes(automargin=True)


def apply_wind_rose_style(fig: Any) -> None:
    def rgba_with_alpha(color: Any, alpha: float) -> str | None:
        if not isinstance(color, str):
            return None

        color_str = color.strip()
        if color_str.startswith("#") and len(color_str) in (4, 7):
            if len(color_str) == 4:
                r = int(color_str[1] * 2, 16)
                g = int(color_str[2] * 2, 16)
                b = int(color_str[3] * 2, 16)
            else:
                r = int(color_str[1:3], 16)
                g = int(color_str[3:5], 16)
                b = int(color_str[5:7], 16)
            return f"rgba({r},{g},{b},{alpha})"

        rgb_match = re.match(r"rgba?\(([^)]+)\)", color_str)
        if rgb_match:
            parts = [p.strip() for p in rgb_match.group(1).split(",")]
            if len(parts) >= 3:
                return f"rgba({parts[0]},{parts[1]},{parts[2]},{alpha})"

        return None

    for trace in fig.data:
        base_color = getattr(trace.marker, "color", None)
        if base_color is not None:
            fill_color = rgba_with_alpha(base_color, 0.15)
            if fill_color is not None:
                trace.marker.color = fill_color
            trace.marker.line.color = base_color
        trace.marker.line.width = 2.0
        trace.opacity = 1


def fig_payload(fig_id: str, fig: Any) -> dict[str, Any]:
    fig_dict = json.loads(json.dumps(fig.to_plotly_json(), cls=PlotlyJSONEncoder, separators=(",", ":")))
    return {"id": fig_id, "figure": fig_dict}


def _ceil_headroom(value: float, pct: float = 0.08) -> float:
    """Round a maximum value up with a small headroom margin."""
    if value <= 0:
        return 1.0
    headroom = value * (1.0 + pct)
    magnitude = 10 ** max(0, math.floor(math.log10(headroom)) - 1)
    return math.ceil(headroom / magnitude) * magnitude


def _floor_with_padding(value: float, span: float, pct: float = 0.08) -> float:
    padded = value - (span * pct)
    if padded == 0:
        return 0.0
    magnitude = 10 ** (math.floor(math.log10(abs(padded))) - 1)
    return math.floor(padded / magnitude) * magnitude


@lru_cache(maxsize=8)
def compute_airport_y_ceilings(icao: str, needed_keys: tuple[str, ...] | None = None) -> dict[str, float]:
    """
    Compute y-axis ceilings from the full, unfiltered airport dataset so that
    non-polar charts maintain a stable scale regardless of active filters.
    Returns a dict keyed by chart figure id.
    """
    needed = set(needed_keys or ())
    if not needed:
        needed = {
            "rain_thunder", "monthly_precip", "gale_weather_split",
            "temp_dewpoint_y1_min", "temp_dewpoint_y1_max", "temp_dewpoint_y2",
            "fog_low_cloud", "monthly_fog", "fog_cloud_joint_min", "fog_cloud_joint_max",
            "fog_share", "monthly_smoke", "hourly_smoke", "scatter_wind_dewpt",
        }

    full_df = load_airport_df(icao, columns_for_ceiling_keys(needed))
    if full_df.is_empty():
        return {}

    ceilings: dict[str, float] = {}

    # ---------- rain_thunder / monthly_precip --------------------------------
    if needed & {"rain_thunder", "monthly_precip"}:
        try:
            rain_pd = full_df.select([
                "year", "month", "TM_FULL", "PRCP_FM_09",
                "PRST_WX_DSC_1", "PRST_WX_PHENOM_1",
                "PRST_WX_DSC_2", "PRST_WX_PHENOM_2",
            ]).to_pandas()
            rain_pd = filter_lightning_coverage_window(rain_pd, time_field="TM_FULL")
            if not rain_pd.empty:
                _, daily_flags = compute_daily_weather_flags(rain_pd, icao)
                if not daily_flags.empty:
                    mc = (
                        daily_flags.groupby(["bom_year", "bom_month"], as_index=False)
                        .agg(Rain=("Rain", "sum"), Thunderstorm=("Thunderstorm", "sum"))
                    )
                    avg = mc.groupby("bom_month")[["Rain", "Thunderstorm"]].mean()
                    max_val = float(avg.max().max()) if not avg.empty else 0.0
                    ceiling = _ceil_headroom(max_val)
                    if "rain_thunder" in needed:
                        ceilings["rain_thunder"] = ceiling
                    if "monthly_precip" in needed:
                        ceilings["monthly_precip"] = ceiling
        except Exception:
            pass

    # ---------- gale_weather_split -------------------------------------------
    if "gale_weather_split" in needed:
        try:
            gale_pd = full_df.select([
                "year", "month", "TM_FULL", "WND_SPD", "MAX_WND_GUST_10",
                "PRST_WX_DSC_1", "PRST_WX_PHENOM_1",
                "PRST_WX_DSC_2", "PRST_WX_PHENOM_2",
                "PRCP_10",
            ]).to_pandas()
            gale_pd = filter_lightning_coverage_window(gale_pd, time_field="TM_FULL")
            monthly_avg = average_monthly_gale_weather_counts(gale_pd, icao, list(range(1, 13)))
            if not monthly_avg.empty:
                monthly_totals = monthly_avg.groupby("month", as_index=False)["Count"].sum()
                max_stack = float(monthly_totals["Count"].max()) if not monthly_totals.empty else 0.0
                ceilings["gale_weather_split"] = _ceil_headroom(max_stack)
        except Exception:
            pass

    # ---------- temp_dewpoint ------------------------------------------------
    if needed & {"temp_dewpoint_y1_min", "temp_dewpoint_y1_max", "temp_dewpoint_y2"}:
        try:
            temp_pd = full_df.select(["TM_FULL", "AIR_TEMP", "DWPT", "PRCP_FM_09"]).to_pandas()
            if not temp_pd.empty:
                t_avg = monthly_avg_daily_extremes(temp_pd, icao)
                if not t_avg.empty:
                    t_max = float(t_avg[["Avg Daily Max T", "Avg Daily Min T", "Avg Daily Max Td", "Avg Daily Min Td"]].max().max())
                    t_min = float(t_avg[["Avg Daily Max T", "Avg Daily Min T", "Avg Daily Max Td", "Avg Daily Min Td"]].min().min())
                    t_span = max(1.0, t_max - t_min)
                    if "temp_dewpoint_y1_max" in needed:
                        ceilings["temp_dewpoint_y1_max"] = _ceil_headroom(t_max)
                    if "temp_dewpoint_y1_min" in needed:
                        ceilings["temp_dewpoint_y1_min"] = _floor_with_padding(t_min, t_span)
                if "temp_dewpoint_y2" in needed:
                    prec_avg = monthly_avg_precipitation_mm(temp_pd, icao)
                    if not prec_avg.empty:
                        ceilings["temp_dewpoint_y2"] = _ceil_headroom(float(prec_avg["Avg Monthly Precip"].max()))
        except Exception:
            pass

    # ---------- fog / low cloud stacked bars (monthly & overview) ------------
    if needed & {"fog_low_cloud", "monthly_fog", "fog_cloud_joint_min", "fog_cloud_joint_max"}:
        try:
            fog_cols = [
                "year", "month", "TM_FULL", "AIR_TEMP", "DWPT", "VSBY", "AWS_VSBY",
                "PRCP_10", "PRCP_FM_09", "PRST_WX_PHENOM_1", "PRST_WX_PHENOM_2",
                "PRST_WX_DSC_1", "PRST_WX_DSC_2",
                "CEIL_CLD_AMT_1", "CEIL_CLD_AMT_2", "CEIL_CLD_HT_1", "CEIL_CLD_HT_2",
            ]
            fog_pd = full_df.select(fog_cols).to_pandas()
            if not fog_pd.empty:
                combined = average_monthly_fog_low_cloud_days(fog_pd, icao)
                if not combined.empty:
                    # For monthly stacked bars: max of fog + all cloud thresholds stacked
                    monthly_totals = (
                        combined.groupby("Month")["Count"].sum()
                    )
                    fog_ceiling = _ceil_headroom(float(monthly_totals.max()))
                    if "fog_low_cloud" in needed:
                        ceilings["fog_low_cloud"] = fog_ceiling
                    if "monthly_fog" in needed:
                        ceilings["monthly_fog"] = fog_ceiling

                if needed & {"fog_cloud_joint_min", "fog_cloud_joint_max"}:
                    dew_series = monthly_fog_low_cloud_dewpoint_by_category(fog_pd)
                    if not dew_series.empty:
                        dew_min = float(dew_series["AvgDWPT"].min())
                        dew_max = float(dew_series["AvgDWPT"].max())
                        dew_span = max(1.0, dew_max - dew_min)
                        if "fog_cloud_joint_min" in needed:
                            ceilings["fog_cloud_joint_min"] = _floor_with_padding(dew_min, dew_span)
                        if "fog_cloud_joint_max" in needed:
                            ceilings["fog_cloud_joint_max"] = _ceil_headroom(dew_max)
        except Exception:
            pass

    # ---------- fog_share (hourly stacked bars) ------------------------------
    if "fog_share" in needed:
        try:
            fog_cols_hourly = [
                "year", "month", "hour", "TM_FULL", "AIR_TEMP", "DWPT", "VSBY", "AWS_VSBY",
                "PRCP_10", "PRCP_FM_09", "PRST_WX_PHENOM_1", "PRST_WX_PHENOM_2",
                "PRST_WX_DSC_1", "PRST_WX_DSC_2",
                "CEIL_CLD_AMT_1", "CEIL_CLD_AMT_2", "CEIL_CLD_HT_1", "CEIL_CLD_HT_2",
            ]
            fog_h_pd = full_df.select(fog_cols_hourly).to_pandas()
            if not fog_h_pd.empty:
                combined_h = average_hourly_fog_low_cloud_days(fog_h_pd, icao)
                if not combined_h.empty:
                    hourly_totals = combined_h.groupby("Hour")["Count"].sum()
                    ceilings["fog_share"] = _ceil_headroom(float(hourly_totals.max()))
        except Exception:
            pass

    # ---------- monthly_smoke ------------------------------------------------
    if needed & {"monthly_smoke", "scatter_wind_dewpt"}:
        try:
            smoke_pd = full_df.select([
                "year", "month", "WND_SPD", "PRST_WX_PHENOM_1", "PRST_WX_PHENOM_2",
            ]).to_pandas()
            if not smoke_pd.empty:
                smoke_tokens = ["FU", "DU", "SA", "VA"]
                mask = token_mask_from_fields(smoke_pd, ["PRST_WX_PHENOM_1", "PRST_WX_PHENOM_2"], smoke_tokens)
                dust_pd = smoke_pd[mask]
                if not dust_pd.empty:
                    def get_phenom(row: pd.Series) -> str:
                        p1 = str(row.get("PRST_WX_PHENOM_1", "")).upper()
                        p2 = str(row.get("PRST_WX_PHENOM_2", "")).upper()
                        for code in smoke_tokens:
                            if code in p1 or code in p2:
                                return code
                        return "Other"

                    dust_pd = dust_pd.copy()
                    dust_pd["Phenomenon"] = dust_pd.apply(get_phenom, axis=1)
                    monthly_avg = (
                        dust_pd.groupby(["year", "month", "Phenomenon"], as_index=False)
                        .size()
                        .rename(columns={"size": "Count"})
                        .groupby(["month", "Phenomenon"], as_index=False)["Count"]
                        .mean()
                    )
                    avg_max = float(monthly_avg["Count"].max()) if not monthly_avg.empty else 0.0
                else:
                    avg_max = 0.0
                if "monthly_smoke" in needed:
                    ceilings["monthly_smoke"] = _ceil_headroom(avg_max)

                if "scatter_wind_dewpt" in needed:
                    spd_vals = pd.to_numeric(dust_pd.get("WND_SPD"), errors="coerce").dropna()
                    if not spd_vals.empty:
                        ceilings["scatter_wind_dewpt"] = _ceil_headroom(float(spd_vals.max()))
        except Exception:
            pass

    # ---------- hourly_smoke -------------------------------------------------
    if "hourly_smoke" in needed:
        try:
            smoke_h_pd = full_df.select([
                "year", "month", "hour", "PRST_WX_PHENOM_1", "PRST_WX_PHENOM_2",
            ]).to_pandas()
            if not smoke_h_pd.empty:
                smoke_tokens = ["FU", "DU", "SA", "VA"]
                mask = token_mask_from_fields(smoke_h_pd, ["PRST_WX_PHENOM_1", "PRST_WX_PHENOM_2"], smoke_tokens)
                dust_h_pd = smoke_h_pd[mask]
                if not dust_h_pd.empty:
                    def get_phenom(row: pd.Series) -> str:
                        p1 = str(row.get("PRST_WX_PHENOM_1", "")).upper()
                        p2 = str(row.get("PRST_WX_PHENOM_2", "")).upper()
                        for code in smoke_tokens:
                            if code in p1 or code in p2:
                                return code
                        return "Other"

                    dust_h_pd = dust_h_pd.copy()
                    dust_h_pd["Phenomenon"] = dust_h_pd.apply(get_phenom, axis=1)
                    mc_h = dust_h_pd.groupby(["hour", "Phenomenon"], as_index=False).size().rename(columns={"size": "Count"})
                    h_max = float(mc_h["Count"].max()) if not mc_h.empty else 0.0
                else:
                    h_max = 0.0
                ceilings["hourly_smoke"] = _ceil_headroom(h_max)
        except Exception:
            pass

    return ceilings


@app.get("/")
def root() -> FileResponse:
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/favicon.svg")
def favicon() -> FileResponse:
    return FileResponse(os.path.join(ROOT_DIR, "favicon.svg"))


@app.get("/api/options")
def options() -> dict[str, Any]:
    airports = list(available_airports())
    return {
        "airports": airports,
        "defaultAirport": "YMML" if "YMML" in airports else (airports[0] if airports else None),
        "months": MONTH_NAMES,
        "default": {
            "yearStart": 2000,
            "yearEnd": 2025,
            "monthStart": "Jan",
            "monthEnd": "Dec",
            "hourStart": 0,
            "hourEnd": 23,
            "invertMonth": False,
            "invertHour": False,
            "section": "overview",
        },
    }


@app.get("/api/charts")
def charts(
    section: str = Query("overview"),
    icao: str = Query(...),
    season: str = Query("all"),
    enso: str = Query("all"),
    iod: str = Query("all"),
    sam: str = Query("all"),
    mjo: str = Query("all"),
    fogMonthlyMode: str = Query("all"),
    fogHourlyMode: str = Query("all"),
    fogWindMode: str = Query("all"),
    fogDewpointMode: str = Query("all"),
    yearStart: int = Query(2000),
    yearEnd: int = Query(2025),
    monthStart: str = Query("Jan"),
    monthEnd: str = Query("Dec"),
    hourStart: int = Query(0),
    hourEnd: int = Query(23),
    invertMonth: bool = Query(False),
    invertHour: bool = Query(False),
) -> dict[str, Any]:
    if monthStart not in MONTH_TO_NUM or monthEnd not in MONTH_TO_NUM:
        return {"error": "Invalid month range."}
    if season not in SEASON_TO_MONTHS:
        return {"error": "Invalid season."}

    month_range = (MONTH_TO_NUM[monthStart], MONTH_TO_NUM[monthEnd])
    month_number_order = selected_month_numbers(month_range[0], month_range[1], invertMonth)
    month_name_order = month_labels_for_numbers(month_number_order)
    airport_df = load_airport_df(icao, columns_for_section(section))

    if airport_df.is_empty():
        return {"section": section, "figures": [], "warning": f"No data found for {icao}."}

    y_ceilings = compute_airport_y_ceilings(icao, ceiling_keys_for_section(section))

    filtered_df = airport_df.filter(
        (build_range_mask("year", (yearStart, yearEnd)))
        & (build_range_mask("month", month_range, invertMonth))
        & (build_season_mask(season))
        & (build_range_mask("hour", (hourStart, hourEnd), invertHour))
    )

    filtered_df = apply_climate_driver_filters(
        filtered_df,
        enso=enso,
        iod=iod,
        sam=sam,
        mjo=mjo,
    )

    if filtered_df.is_empty():
        return {"section": section, "figures": [], "warning": f"No data found for {icao} with these filters."}

    figures: list[dict[str, Any]] = []

    if section == "overview":
        bg_img_base64 = None
        wr_df = filtered_df.select(["WND_DIR", "WND_SPD"]).drop_nulls()
        wr_df = wr_df.with_columns(((pl.col("WND_DIR") + 11.25) % 360 // 22.5 * 22.5).alias("dir_bin"))
        rose_data = (
            wr_df.with_columns(pl.col("WND_SPD").map_elements(categorize_speed, return_dtype=pl.Utf8).alias("Speed Range"))
            .group_by(["dir_bin", "Speed Range"])
            .agg(pl.len().alias("Frequency"))
            .to_pandas()
        )
        total_obs = float(rose_data["Frequency"].sum()) if not rose_data.empty else 0.0
        rose_data["Frequency"] = (rose_data["Frequency"] / total_obs * 100.0) if total_obs > 0 else 0.0
        fig_rose = px.bar_polar(
            rose_data,
            r="Frequency",
            theta="dir_bin",
            color="Speed Range",
            color_discrete_sequence=px.colors.sequential.Turbo,
            title="Wind Rose",
            category_orders={"Speed Range": ["0-1 kt", "1-5 kt", "5-10 kt", "10-15 kt", "15-22 kt", "22+ kt"]},
        )
        fig_rose.update_traces(hovertemplate="Direction: %{theta}<br>Speed: %{fullData.name}<br>Frequency: %{r:.2f}%<extra></extra>")
        try:
            airport_lat = COORDS_DF.loc[icao, "LAT"]
            airport_lon = COORDS_DF.loc[icao, "LONG"]
            bg_img_base64 = get_centered_background(float(airport_lat), float(airport_lon), zoom=ZOOM_LEVEL)
        except Exception:
            pass
        fig_rose.update_layout(
            legend=dict(bgcolor="rgba(255,255,255,0.88)", bordercolor="#c7d4ef", borderwidth=1),
            polar=dict(bgcolor="rgba(0,0,0,0)", angularaxis=dict(direction="clockwise", period=360)),
        )
        apply_wind_rose_style(fig_rose)
        apply_common_layout(fig_rose)
        if bg_img_base64:
            apply_polar_background(fig_rose, bg_img_base64)
        figures.append(fig_payload("wind_rose", fig_rose))

        rain_df = filtered_df.select([
            "year",
            "month",
            "TM_FULL",
            "PRCP_FM_09",
            "PRST_WX_DSC_1",
            "PRST_WX_PHENOM_1",
            "PRST_WX_DSC_2",
            "PRST_WX_PHENOM_2",
        ]).to_pandas()
        if not rain_df.empty:
            rain_days, daily_flags = compute_daily_weather_flags(rain_df, icao)
            if not rain_days.empty:
                monthly_counts = (
                    daily_flags.groupby(["bom_year", "bom_month"], as_index=False)
                    .agg(
                        Rain=("Rain", "sum"),
                        Thunderstorm=("Thunderstorm", "sum"),
                    )
                )
                # Rain: average over all selected years.
                rain_avg_m = (
                    monthly_counts.groupby("bom_month", as_index=False)["Rain"]
                    .mean()
                    .rename(columns={"bom_month": "month"})
                )
                # Thunderstorm: average only over years >= LIGHTNING_STATS_MIN_YEAR.
                ts_avg_m = (
                    monthly_counts[monthly_counts["bom_year"] >= LIGHTNING_STATS_MIN_YEAR]
                    .groupby("bom_month", as_index=False)["Thunderstorm"]
                    .mean()
                    .rename(columns={"bom_month": "month"})
                )
                monthly_avg = rain_avg_m.merge(ts_avg_m, on="month", how="left")
                monthly_avg["Thunderstorm"] = monthly_avg["Thunderstorm"].fillna(0.0)
                monthly_avg = monthly_avg[monthly_avg["month"].isin(month_number_order)].copy()
                monthly_avg["Month"] = monthly_avg["month"].apply(lambda m: MONTH_NAMES[m - 1])
                monthly_avg["Month"] = pd.Categorical(monthly_avg["Month"], categories=month_name_order, ordered=True)
                monthly_avg = monthly_avg.sort_values("Month")
                rain_avg = monthly_avg.melt(
                    id_vars=["month", "Month"],
                    value_vars=["Rain", "Thunderstorm"],
                    var_name="Type",
                    value_name="Count",
                )
                rain_avg["Type"] = rain_avg["Type"].replace({"Thunderstorm": THUNDERSTORM_LEGEND_LABEL})
                fig_rain = px.bar(
                    rain_avg,
                    x="Month",
                    y="Count",
                    color="Type",
                    barmode="group",
                    color_discrete_map={"Rain": "#2159d1", THUNDERSTORM_LEGEND_LABEL: "#c62828"},
                    labels={"Count": "Avg Days/Month", "Type": "Category"},
                    title="Rain/Thunderstorm Days",
                    category_orders={"Month": month_name_order, "Type": ["Rain", THUNDERSTORM_LEGEND_LABEL]},
                )
                fig_rain.update_xaxes(title_text="")
                apply_common_layout(fig_rain)
                apply_frequency_panel_layout(fig_rain)
                if "rain_thunder" in y_ceilings:
                    fig_rain.update_yaxes(range=[0, y_ceilings["rain_thunder"]], autorange=False)
                figures.append(fig_payload("rain_thunder", fig_rain))

        temp_df = filtered_df.select(["TM_FULL", "AIR_TEMP", "DWPT", "PRCP_FM_09"]).to_pandas()
        if not temp_df.empty:
            temp_avg = monthly_avg_daily_extremes(temp_df, icao)
            monthly_precip_avg = monthly_avg_precipitation_mm(temp_df, icao)
        else:
            temp_avg = pd.DataFrame()
            monthly_precip_avg = pd.DataFrame()

        if not temp_avg.empty:
            temp_avg = temp_avg[temp_avg["month"].isin(month_number_order)].copy()
            temp_avg["Month"] = temp_avg["month"].apply(lambda m: MONTH_NAMES[m - 1])
            temp_avg["Month"] = pd.Categorical(temp_avg["Month"], categories=month_name_order, ordered=True)
            temp_avg = temp_avg.sort_values("Month")
            fig_temp = go.Figure()
            if not monthly_precip_avg.empty:
                monthly_precip_avg = monthly_precip_avg[monthly_precip_avg["month"].isin(month_number_order)].copy()
                monthly_precip_avg["Month"] = monthly_precip_avg["month"].apply(lambda m: MONTH_NAMES[m - 1])
                precip_by_month = (
                    monthly_precip_avg.set_index("Month")["Avg Monthly Precip"]
                    .reindex(month_name_order)
                    .fillna(0.0)
                )
                fig_temp.add_bar(
                    x=month_name_order,
                    y=precip_by_month.astype(float).tolist(),
                    name="Avg Monthly Precip",
                    yaxis="y2",
                    marker_color="#1565c0",
                    marker_line_color="#0d47a1",
                    marker_line_width=1,
                    opacity=0.6,
                    zorder=0,
                    hovertemplate="Month: %{x}<br>Avg Monthly Precip: %{y:.1f} mm<extra></extra>",
                )

            temp_trace_styles = {
                "Avg Daily Max T": {"color": "#d32f2f", "visible": True},
                "Avg Daily Min T": {"color": "#ef9a9a", "visible": True},
                "Avg Daily Max Td": {"color": "#0b3d91", "visible": "legendonly"},
                "Avg Daily Min Td": {"color": "#90caf9", "visible": "legendonly"},
            }
            for trace_name, style in temp_trace_styles.items():
                fig_temp.add_trace(go.Scatter(
                    x=temp_avg["Month"],
                    y=temp_avg[trace_name],
                    mode="lines+markers",
                    name=trace_name,
                    line=dict(color=style["color"], width=2.5),
                    marker=dict(color=style["color"], size=7),
                    visible=style["visible"],
                    zorder=2,
                    hovertemplate=f"Month: %{{x}}<br>{trace_name}: %{{y:.1f}} °C<extra></extra>",
                ))

            fig_temp.update_xaxes(title_text="")
            fig_temp.update_yaxes(title_text="Temperature / Dewpoint (°C)")
            fig_temp.update_layout(
                title="Temperature, Dewpoint & Precipitation",
                yaxis2=dict(
                    title="Avg Monthly Precipitation (mm)",
                    overlaying="y",
                    side="right",
                    rangemode="tozero",
                    showgrid=False,
                ),
                bargap=0.22,
            )
            apply_common_layout(fig_temp)
            apply_frequency_panel_layout(fig_temp)
            y1_min = y_ceilings.get("temp_dewpoint_y1_min")
            y1_max = y_ceilings.get("temp_dewpoint_y1_max")
            y2_max = y_ceilings.get("temp_dewpoint_y2")
            if y1_min is not None and y1_max is not None:
                fig_temp.update_yaxes(range=[y1_min, y1_max], autorange=False)
            if y2_max is not None:
                fig_temp.update_layout(yaxis2={**fig_temp.layout.yaxis2.to_plotly_json(), "range": [0, y2_max], "autorange": False})
            figures.append(fig_payload("temp_dewpoint", fig_temp))

        fog_df = filtered_df.select([
            "year",
            "month",
            "TM_FULL",
            "AIR_TEMP",
            "DWPT",
            "VSBY",
            "AWS_VSBY",
            "PRCP_10",
            "PRCP_FM_09",
            "PRST_WX_PHENOM_1",
            "PRST_WX_PHENOM_2",
            "PRST_WX_DSC_1",
            "PRST_WX_DSC_2",
            "CEIL_CLD_AMT_1",
            "CEIL_CLD_AMT_2",
            "CEIL_CLD_HT_1",
            "CEIL_CLD_HT_2",
        ]).to_pandas()
        if not fog_df.empty:
            fog_mode_map = split_fog_day_type_datasets(fog_df, icao)
            selected_monthly_df, selected_monthly_label = fog_mode_map.get(fogMonthlyMode, fog_mode_map["all"])
            if not selected_monthly_df.empty:
                fig_fog = build_fog_low_cloud_frequency_figure(
                    selected_monthly_df,
                    f"Fog/Low Cloud Frequency ({selected_monthly_label})",
                    icao,
                    month_number_order,
                )
            else:
                fig_fog = build_placeholder_figure(
                    f"Fog/Low Cloud Frequency ({selected_monthly_label})",
                    "No records for selected day filter",
                )
            apply_common_layout(fig_fog)
            apply_frequency_panel_layout(fig_fog)
            if "fog_low_cloud" in y_ceilings:
                fig_fog.update_yaxes(range=[0, y_ceilings["fog_low_cloud"]], autorange=False)
            figures.append(fig_payload("fog_low_cloud", fig_fog))

    elif section == "wind":
        bg_img_base64 = None
        wr_df = filtered_df.select(["WND_DIR", "WND_SPD"]).drop_nulls()
        wr_df = wr_df.with_columns(((pl.col("WND_DIR") + 11.25) % 360 // 22.5 * 22.5).alias("dir_bin"))
        rose_data = (
            wr_df.with_columns(pl.col("WND_SPD").map_elements(categorize_speed, return_dtype=pl.Utf8).alias("Speed Range"))
            .group_by(["dir_bin", "Speed Range"])
            .agg(pl.len().alias("Frequency"))
            .to_pandas()
        )
        total_obs = float(rose_data["Frequency"].sum()) if not rose_data.empty else 0.0
        rose_data["Frequency"] = (rose_data["Frequency"] / total_obs * 100.0) if total_obs > 0 else 0.0
        fig_rose = px.bar_polar(
            rose_data,
            r="Frequency",
            theta="dir_bin",
            color="Speed Range",
            color_discrete_sequence=px.colors.sequential.Turbo,
            title="Wind Rose",
            category_orders={"Speed Range": ["0-1 kt", "1-5 kt", "5-10 kt", "10-15 kt", "15-22 kt", "22+ kt"]},
        )
        fig_rose.update_traces(hovertemplate="Direction: %{theta}<br>Speed: %{fullData.name}<br>Frequency: %{r:.2f}%<extra></extra>")
        try:
            airport_lat = COORDS_DF.loc[icao, "LAT"]
            airport_lon = COORDS_DF.loc[icao, "LONG"]
            bg_img_base64 = get_centered_background(float(airport_lat), float(airport_lon), zoom=ZOOM_LEVEL)
        except Exception:
            pass
        fig_rose.update_layout(
            legend=dict(bgcolor="rgba(255,255,255,0.88)", bordercolor="#c7d4ef", borderwidth=1),
            polar=dict(bgcolor="rgba(0,0,0,0)", angularaxis=dict(direction="clockwise", period=360)),
        )
        apply_wind_rose_style(fig_rose)
        apply_common_layout(fig_rose)
        # Wind-tab specific spacing: shift plot right and reserve more title clearance.
        fig_rose.update_layout(
            margin=dict(l=62, r=DEFAULT_LEGEND_ENTRY_WIDTH + LEGEND_MARGIN_PADDING, t=48, b=22),
            polar=dict(
                domain=dict(x=[0.14, 0.92], y=[0.0, 0.93]),
                bgcolor="rgba(0,0,0,0)",
                angularaxis=dict(direction="clockwise", period=360),
            ),
        )
        if bg_img_base64:
            apply_polar_background(fig_rose, bg_img_base64)
        figures.append(fig_payload("wind_rose", fig_rose))

        gale_df = filtered_df.select([
            "year",
            "month",
            "TM_FULL",
            "WND_SPD",
            "MAX_WND_GUST_10",
            "PRCP_10",
            "PRST_WX_DSC_1",
            "PRST_WX_PHENOM_1",
            "PRST_WX_DSC_2",
            "PRST_WX_PHENOM_2",
        ]).to_pandas()

        monthly_avg = average_monthly_gale_weather_counts(gale_df, icao, month_number_order)

        monthly_avg["Month"] = monthly_avg["month"].apply(lambda m: MONTH_NAMES[m - 1])
        monthly_avg["Month"] = pd.Categorical(monthly_avg["Month"], categories=month_name_order, ordered=True)
        monthly_avg = monthly_avg.sort_values(["Month", "Category"])
        
        # Convert to native Python types to avoid Plotly binary encoding
        monthly_avg["Count"] = monthly_avg["Count"].apply(float)
        monthly_avg["Month"] = monthly_avg["Month"].astype(str)
        monthly_avg["Category"] = monthly_avg["Category"].replace({"TS": TS_LEGEND_LABEL})

        fig_gales = px.bar(
            monthly_avg,
            x="Month",
            y="Count",
            color="Category",
            barmode="stack",
            labels={"Count": "Avg Gale Obs/Month"},
            title="Monthly Gale Frequency by Weather Type",
            category_orders={"Month": month_name_order, "Category": ["No wx", "SHRA", TS_LEGEND_LABEL]},
            color_discrete_map={"No wx": "#7a7a7a", "SHRA": "#3b82c4", TS_LEGEND_LABEL: "#c62828"},
        )
        fig_gales.update_xaxes(title_text="")
        apply_common_layout(fig_gales, height=380)
        apply_frequency_panel_layout(fig_gales)
        if "gale_weather_split" in y_ceilings:
            fig_gales.update_yaxes(range=[0, y_ceilings["gale_weather_split"]], autorange=False)
        figures.append(fig_payload("gale_weather_split", fig_gales))

    elif section == "precipitation":
        monthly_precip_added = False
        precip_split_added = False
        precip_df = filtered_df.select([
            "year",
            "month",
            "TM_FULL",
            "WND_DIR",
            "VSBY",
            "AWS_VSBY",
            "PRCP_10",
            "PRCP_FM_09",
            "PRST_WX_DSC_1",
            "PRST_WX_PHENOM_1",
            "PRST_WX_DSC_2",
            "PRST_WX_PHENOM_2",
        ]).to_pandas()
        if not precip_df.empty:
            precip_days, daily_flags = compute_daily_weather_flags(precip_df, icao)

            if not precip_days.empty:
                monthly_counts = (
                    daily_flags.groupby(["bom_year", "bom_month"], as_index=False)
                    .agg(
                        Rain=("Rain", "sum"),
                        Thunderstorm=("Thunderstorm", "sum"),
                    )
                )

                # Rain: average over all selected years.
                rain_avg_m = (
                    monthly_counts.groupby("bom_month", as_index=False)["Rain"]
                    .mean()
                    .rename(columns={"bom_month": "month"})
                )
                # Thunderstorm: average only over years >= LIGHTNING_STATS_MIN_YEAR.
                ts_avg_m = (
                    monthly_counts[monthly_counts["bom_year"] >= LIGHTNING_STATS_MIN_YEAR]
                    .groupby("bom_month", as_index=False)["Thunderstorm"]
                    .mean()
                    .rename(columns={"bom_month": "month"})
                )
                monthly_avg = rain_avg_m.merge(ts_avg_m, on="month", how="left")
                monthly_avg["Thunderstorm"] = monthly_avg["Thunderstorm"].fillna(0.0)
                monthly_avg = monthly_avg[monthly_avg["month"].isin(month_number_order)].copy()
                monthly_avg["Month"] = monthly_avg["month"].apply(lambda m: MONTH_NAMES[m - 1])
                monthly_avg["Month"] = pd.Categorical(monthly_avg["Month"], categories=month_name_order, ordered=True)
                monthly_avg = monthly_avg.sort_values("Month")
                monthly_precip = monthly_avg.melt(
                    id_vars=["month", "Month"],
                    value_vars=["Rain", "Thunderstorm"],
                    var_name="Type",
                    value_name="Count",
                )
                monthly_precip["Type"] = monthly_precip["Type"].replace({"Thunderstorm": THUNDERSTORM_LEGEND_LABEL})

                fig_precip = px.bar(
                    monthly_precip,
                    x="Month",
                    y="Count",
                    color="Type",
                    barmode="group",
                    color_discrete_map={"Rain": "#2159d1", THUNDERSTORM_LEGEND_LABEL: "#c62828"},
                    labels={"Count": "Avg Days/Month", "Type": "Category"},
                    title="Monthly Rain/Thunderstorm Days",
                    category_orders={"Month": month_name_order, "Type": ["Rain", THUNDERSTORM_LEGEND_LABEL]},
                )
                fig_precip.update_xaxes(title_text="")
                apply_common_layout(fig_precip)
                apply_frequency_panel_layout(fig_precip)
                if "monthly_precip" in y_ceilings:
                    fig_precip.update_yaxes(range=[0, y_ceilings["monthly_precip"]], autorange=False)
                figures.append(fig_payload("monthly_precip", fig_precip))
                monthly_precip_added = True

        if not precip_df.empty:
            vis_df = precip_df.copy()
            vis_df["chart_vsby"] = vis_df[["VSBY", "AWS_VSBY"]].apply(pd.to_numeric, errors="coerce").min(axis=1)
            vis_df = vis_df.dropna(subset=["WND_DIR", "chart_vsby"]).copy()
            vis_df["dir_bin"] = ((vis_df["WND_DIR"] + 11.25) % 360 // 22.5 * 22.5)

            precip_tokens = ["RA", "DZ", "SN", "GS", "GR", "PL", "SH", "TS"]
            precip_fields = ["PRST_WX_DSC_1", "PRST_WX_PHENOM_1", "PRST_WX_DSC_2", "PRST_WX_PHENOM_2"]
            is_precip = token_mask_from_fields(vis_df, precip_fields, precip_tokens)
            if "PRCP_10" in vis_df.columns:
                is_precip = is_precip | (pd.to_numeric(vis_df["PRCP_10"], errors="coerce").fillna(0.0) > 0.2)
            precip_obs = vis_df[is_precip].copy()

            if not precip_obs.empty:
                bg_img_base64 = None
                # 10-degree bins for smooth filled contour lines
                dir_bins_10 = list(range(0, 360, 10))
                precip_obs = precip_obs.copy()
                precip_obs["dir_bin_10"] = (((precip_obs["WND_DIR"] + 5) % 360) // 10 * 10).astype(int)
                denom_counts = precip_obs.groupby("dir_bin_10").size().to_dict()

                # Inner → outer order so fill="tonext" fills each band between
                # consecutive contours only (not back to origin).
                thresholds = [3.0, 5.0, 7.0, 9.0]
                labels = ["<3 km", "<5 km", "<7 km", "<9 km"]
                line_colors = ["#30123b", "#4145ab", "#4675ed", "#39a2fc"]
                fill_colors = [
                    "rgba(48,18,59,0.15)",     # <3 km  – fills to origin
                    "rgba(65,69,171,0.15)",    # <5 km  – fills to <3 km line
                    "rgba(70,117,237,0.15)",   # <7 km  – fills to <5 km line
                    "rgba(57,162,252,0.15)",   # <9 km  – fills to <7 km line
                ]

                # Pre-compute probability arrays so we can reference them in order
                prob_arrays: list[list[float]] = []
                for threshold in thresholds:
                    sub = precip_obs[precip_obs["chart_vsby"] < threshold]
                    num_counts = sub.groupby("dir_bin_10").size().to_dict()
                    prob_arrays.append([
                        (float(num_counts.get(d, 0)) / float(denom_counts.get(d, 1)) * 100.0)
                        if denom_counts.get(d, 0) > 0 else 0.0
                        for d in dir_bins_10
                    ])

                fig_split = go.Figure()
                for i, (label, lc, fc, probs) in enumerate(
                    zip(labels, line_colors, fill_colors, prob_arrays)
                ):
                    r_vals = probs + [probs[0]]
                    theta_vals = [float(d) for d in dir_bins_10] + [0.0]
                    fig_split.add_trace(go.Scatterpolar(
                        r=r_vals,
                        theta=theta_vals,
                        mode="lines",
                        # First (innermost) fills to origin; each outer trace fills
                        # to the trace added immediately before it.
                        fill="toself" if i == 0 else "tonext",
                        fillcolor=fc,
                        line=dict(color=lc, width=2),
                        name=label,
                        legendrank=len(thresholds) - i,  # legend: <9 km first
                        hoveron="points+fills",
                        hovertemplate=(
                            f"<b>{label}</b><br>"
                            "Direction: %{theta}<br>"
                            "P(VSBY &lt; threshold | precip): %{r:.1f}%"
                            "<extra></extra>"
                        ),
                    ))

                try:
                    airport_lat = COORDS_DF.loc[icao, "LAT"]
                    airport_lon = COORDS_DF.loc[icao, "LONG"]
                    bg_img_base64 = get_centered_background(float(airport_lat), float(airport_lon), zoom=ZOOM_LEVEL)
                except Exception:
                    pass
                fig_split.update_layout(
                    title="Conditional P(VSBY < threshold | Precipitation) by Direction",
                    polar=dict(
                        bgcolor="rgba(0,0,0,0)",
                        angularaxis=dict(direction="clockwise", rotation=90),
                        radialaxis=dict(ticksuffix="%"),
                    ),
                )
                apply_common_layout(fig_split)
                fig_split.update_layout(
                    margin=dict(l=62, r=DEFAULT_LEGEND_ENTRY_WIDTH + LEGEND_MARGIN_PADDING, t=48, b=22),
                    polar=dict(
                        domain=dict(x=[0.14, 0.92], y=[0.0, 0.93]),
                        bgcolor="rgba(0,0,0,0)",
                        angularaxis=dict(direction="clockwise", rotation=90),
                        radialaxis=dict(ticksuffix="%"),
                    ),
                )
                if bg_img_base64:
                    apply_polar_background(fig_split, bg_img_base64)
                figures.append(fig_payload("precip_split", fig_split))
                precip_split_added = True

        if not monthly_precip_added:
            fig = build_placeholder_figure("Monthly Rain/Thunderstorm Days")
            apply_common_layout(fig)
            figures.append(fig_payload("monthly_precip", fig))

        if not precip_split_added:
            fig = build_placeholder_figure("Conditional P(VSBY < threshold | Precipitation) by Direction")
            apply_common_layout(fig)
            figures.append(fig_payload("precip_split", fig))

    elif section == "fog_low_cloud":
        fog_df = filtered_df.select([
            "year",
            "month",
            "hour",
            "TM_FULL",
            "AIR_TEMP",
            "DWPT",
            "VSBY",
            "AWS_VSBY",
            "PRCP_10",
            "WND_DIR",
            "WND_SPD",
            "PRCP_FM_09",
            "PRST_WX_PHENOM_1",
            "PRST_WX_PHENOM_2",
            "PRST_WX_DSC_1",
            "PRST_WX_DSC_2",
            "CEIL_CLD_AMT_1",
            "CEIL_CLD_AMT_2",
            "CEIL_CLD_HT_1",
            "CEIL_CLD_HT_2",
        ]).to_pandas()

        fog_figures: list[dict[str, Any]] = []

        def add_placeholder(fig_id: str, title: str, _subtitle: str) -> None:
            fig = build_placeholder_figure(title)
            apply_common_layout(fig)
            fog_figures.append(fig_payload(fig_id, fig))

        def apply_fog_side_legend(fig: go.Figure, *, groupclick: str | None = None, top_margin: int = 36) -> None:
            apply_side_legend(
                fig,
                width_px=WIDE_LEGEND_ENTRY_WIDTH,
                font_size=10,
                top_margin=top_margin,
                title_text="Category",
                groupclick=groupclick,
                bgcolor="rgba(255,255,255,0.92)",
            )

        def build_fog_low_cloud_frequency_chart(dataset: pd.DataFrame, title: str) -> go.Figure | None:
            if dataset.empty:
                return None
            return build_fog_low_cloud_frequency_figure(dataset, title, icao, month_number_order)

        def build_fog_low_cloud_dewpoint_chart(dataset: pd.DataFrame, title: str) -> go.Figure | None:
            if dataset.empty:
                return None

            series_df = monthly_fog_low_cloud_dewpoint_by_category(dataset)
            if series_df.empty:
                return None

            category_colors = {
                "Fog": "#d4af37",
                "2000ft - 1500ft cloud": "#ef9a9a",
                "1500ft - 1000ft cloud": "#e57373",
                "1000ft - 500ft cloud": "#c62828",
                "< 500ft cloud": "#8b0000",
            }

            fig = go.Figure()
            traces_added = 0

            for label, color in category_colors.items():
                masked = series_df[series_df["Category"] == label].copy()
                if masked.empty:
                    continue

                monthly_avg = (
                    masked.set_index("month")["AvgDWPT"]
                    .reindex(month_number_order)
                    .reset_index()
                )
                monthly_avg["Month"] = monthly_avg["month"].apply(lambda m: MONTH_NAMES[m - 1])

                fig.add_trace(go.Scatter(
                    x=monthly_avg["Month"],
                    y=monthly_avg["AvgDWPT"],
                    mode="lines+markers",
                    name=label,
                    line=dict(color=color, width=2.5),
                    marker=dict(size=7, color=color),
                    connectgaps=False,
                    hovertemplate="Month: %{x}<br>Avg Dewpoint: %{y:.1f} °C<extra>" + label + "</extra>",
                ))
                traces_added += 1

            if traces_added == 0:
                return None

            fig.update_layout(
                title=title,
                legend_title_text="Category",
            )
            fig.update_xaxes(title_text="", categoryorder="array", categoryarray=month_name_order)
            fig.update_yaxes(title_text="Avg Dewpoint (°C)")
            apply_side_legend(
                fig,
                width_px=WIDE_LEGEND_ENTRY_WIDTH,
                font_size=10,
                top_margin=36,
                title_text="Category",
                bgcolor="rgba(255,255,255,0.92)",
            )
            return fig

        def build_fog_low_cloud_hourly_chart(dataset: pd.DataFrame, title: str) -> go.Figure | None:
            if dataset.empty:
                return None

            hour_numbers = list(range(24))
            hour_labels = [str(hour) for hour in hour_numbers]
            hour_hover_labels = [f"{hour:02d}Z" for hour in range(24)]
            combined = average_hourly_fog_low_cloud_days(dataset, icao)

            threshold_order = ["below 500ft", "below 1000ft", "below 1500ft", "below 2000ft"]
            combined_sorted = combined.copy()
            combined_sorted["Threshold"] = combined_sorted["Threshold"].fillna("N/A")

            threshold_colors = {
                "below 500ft": "#8b0000",
                "below 1000ft": "#c62828",
                "below 1500ft": "#e57373",
                "below 2000ft": "#ef9a9a",
            }

            low_cloud_stack = (
                combined_sorted[combined_sorted["Type"] == "Low cloud"]
                .pivot_table(index="Hour", columns="Threshold", values="Count", aggfunc="sum")
                .reindex(hour_labels)
                .fillna(0.0)
            )
            fog_by_hour = (
                combined_sorted[combined_sorted["Type"] == "Fog"]
                .groupby("Hour")["Count"]
                .sum()
                .reindex(hour_labels)
                .fillna(0.0)
            )

            total_low_cloud = float(low_cloud_stack.to_numpy().sum()) if not low_cloud_stack.empty else 0.0
            total_fog = float(fog_by_hour.sum()) if not fog_by_hour.empty else 0.0
            if (total_low_cloud + total_fog) <= 0.0:
                return None

            low_cloud_x = [hour - 0.22 for hour in hour_numbers]
            fog_x = [hour + 0.22 for hour in hour_numbers]
            bar_width = 0.38

            fig = go.Figure()
            fig.add_bar(
                x=low_cloud_x,
                y=[0.0] * len(hour_labels),
                showlegend=False,
                hoverinfo="skip",
                marker_color="rgba(0,0,0,0)",
                width=bar_width,
            )
            fig.add_bar(
                x=fog_x,
                y=[0.0] * len(hour_labels),
                showlegend=False,
                hoverinfo="skip",
                marker_color="rgba(0,0,0,0)",
                width=bar_width,
            )

            for threshold in threshold_order:
                y_values = low_cloud_stack[threshold].astype(float).tolist() if threshold in low_cloud_stack.columns else [0.0] * len(hour_labels)
                display_label = FOG_LOW_CLOUD_THRESHOLD_LABELS[threshold]
                fig.add_bar(
                    x=low_cloud_x,
                    y=y_values,
                    name=display_label,
                    marker_color=threshold_colors[threshold],
                    customdata=hour_hover_labels,
                    width=bar_width,
                    hovertemplate=(
                        "Hour: %{customdata}<br>"
                        f"{display_label}: %{{y:.2f}}<extra></extra>"
                    ),
                )

            fig.add_bar(
                x=fog_x,
                y=fog_by_hour.astype(float).tolist(),
                name="Fog",
                marker_color="#d4af37",
                customdata=hour_hover_labels,
                width=bar_width,
                hovertemplate="Hour: %{customdata}<br>Fog: %{y:.2f}<extra></extra>",
            )

            fig.update_layout(
                title=title,
                barmode="stack",
                legend_title_text="Category",
            )
            fig.update_xaxes(
                title_text="",
                tickmode="array",
                tickvals=[0, 5, 10, 15, 20],
                ticktext=["00Z", "05Z", "10Z", "15Z", "20Z"],
                showgrid=False,
                range=[-0.8, 23.8],
            )
            fig.update_yaxes(title_text="Avg Days/Hour")
            apply_side_legend(
                fig,
                width_px=WIDE_LEGEND_ENTRY_WIDTH,
                font_size=10,
                top_margin=36,
                title_text="Category",
                bgcolor="rgba(255,255,255,0.92)",
            )
            return fig

        def build_fog_low_cloud_wind_plot(dataset: pd.DataFrame, title: str) -> go.Figure | None:
            if dataset.empty:
                return None

            plot_df = dataset.copy()
            plot_df["is_fog"] = fog_observation_mask(plot_df)

            lowest_ceiling = lowest_low_cloud_ceiling(plot_df)
            plot_df["is_low_cloud_2000_1500"] = lowest_ceiling.lt(2000) & lowest_ceiling.ge(1500)
            plot_df["is_low_cloud_1500_1000"] = lowest_ceiling.lt(1500) & lowest_ceiling.ge(1000)
            plot_df["is_low_cloud_1000_500"] = lowest_ceiling.lt(1000) & lowest_ceiling.ge(500)
            plot_df["is_low_cloud_below_500"] = lowest_ceiling.lt(500)

            plot_df = plot_df[
                plot_df["is_fog"]
                | plot_df["is_low_cloud_2000_1500"]
                | plot_df["is_low_cloud_1500_1000"]
                | plot_df["is_low_cloud_1000_500"]
                | plot_df["is_low_cloud_below_500"]
            ].copy()
            plot_df = plot_df.dropna(subset=["WND_DIR", "WND_SPD"])
            if plot_df.empty:
                return None

            direction_step = 10.0
            speed_step = 1.0
            speed_values = pd.to_numeric(plot_df["WND_SPD"], errors="coerce").dropna()
            if speed_values.empty:
                return None
            observed_max_speed = float(speed_values.max())
            # Add a little headroom and round up to the next 5 kt so contours fill the panel.
            max_speed = max(10.0, float(math.ceil((observed_max_speed * 1.1) / 5.0) * 5.0))
            dir_edges = np.arange(0.0, 360.0 + direction_step, direction_step)
            dir_centers = dir_edges[:-1] + (direction_step / 2.0)
            speed_edges = np.arange(0.0, max_speed + speed_step, speed_step)
            cutoff_pct = 0.1
            category_colors = {
                "Fog": "#d4af37",
                "2000ft - 1500ft cloud": "#ef9a9a",
                "1500ft - 1000ft cloud": "#e57373",
                "1000ft - 500ft cloud": "#c62828",
                "< 500ft cloud": "#8b0000",
            }
            category_masks = {
                "Fog": plot_df["is_fog"],
                "2000ft - 1500ft cloud": plot_df["is_low_cloud_2000_1500"],
                "1500ft - 1000ft cloud": plot_df["is_low_cloud_1500_1000"],
                "1000ft - 500ft cloud": plot_df["is_low_cloud_1000_500"],
                "< 500ft cloud": plot_df["is_low_cloud_below_500"],
            }

            def hex_to_rgba(hex_color: str, alpha: float) -> str:
                color = hex_color.lstrip("#")
                if len(color) != 6:
                    return f"rgba(0,0,0,{alpha})"
                red = int(color[0:2], 16)
                green = int(color[2:4], 16)
                blue = int(color[4:6], 16)
                return f"rgba({red},{green},{blue},{alpha})"

            def smooth_frequency_field(field: np.ndarray, passes: int = 3) -> np.ndarray:
                out = field.astype(float).copy()
                for _ in range(passes):
                    out = (np.roll(out, 1, axis=1) + 2.0 * out + np.roll(out, -1, axis=1)) / 4.0
                    padded = np.pad(out, ((1, 1), (0, 0)), mode="edge")
                    out = (padded[:-2] + 2.0 * padded[1:-1] + padded[2:]) / 4.0
                return out

            def boundary_from_level(field: np.ndarray, level: float) -> np.ndarray:
                boundary = np.full(len(dir_centers), np.nan)
                for col_idx in range(len(dir_centers)):
                    column = field[:, col_idx]
                    hit_idx = np.where(column >= level)[0]
                    if len(hit_idx) > 0:
                        boundary[col_idx] = float(speed_edges[int(hit_idx.max()) + 1])
                boundary = np.nan_to_num(boundary, nan=0.0)
                boundary = (np.roll(boundary, 1) + 2.0 * boundary + np.roll(boundary, -1)) / 4.0
                return boundary

            fig = go.Figure()
            traces_added = 0
            max_plotted_speed = 0.0
            layer_order = [
                "2000ft - 1500ft cloud",
                "1500ft - 1000ft cloud",
                "1000ft - 500ft cloud",
                "< 500ft cloud",
                "Fog",
            ]
            layer_fields: dict[str, np.ndarray] = {}
            for label in layer_order:
                sub = plot_df[category_masks[label]].copy()

                if sub.empty:
                    continue

                dir_vals = np.mod(pd.to_numeric(sub["WND_DIR"], errors="coerce"), 360.0).to_numpy()
                spd_vals = pd.to_numeric(sub["WND_SPD"], errors="coerce").to_numpy()
                valid = np.isfinite(dir_vals) & np.isfinite(spd_vals)
                dir_vals = dir_vals[valid]
                spd_vals = np.clip(spd_vals[valid], 0.0, max_speed)
                if len(dir_vals) == 0:
                    continue

                hist2d, _, _ = np.histogram2d(spd_vals, dir_vals, bins=[speed_edges, dir_edges])
                total_obs = float(hist2d.sum())
                if total_obs <= 0:
                    continue

                rel_field = (hist2d / total_obs) * 100.0
                rel_field = smooth_frequency_field(rel_field, passes=3)
                layer_fields[label] = rel_field
                peak_rel = float(np.nanmax(rel_field)) if rel_field.size else 0.0
                if peak_rel < cutoff_pct:
                    continue

                low = cutoff_pct
                high = max(low, peak_rel * 0.92)
                if high <= low:
                    levels = [round(float(low), 3)]
                else:
                    levels = np.geomspace(low, high, num=6)
                    levels = sorted({round(float(level), 3) for level in levels})

                first_for_label = True
                for level_idx, level in enumerate(levels):
                    boundary = boundary_from_level(rel_field, level)
                    boundary_max = float(np.max(boundary))
                    if boundary_max <= 0.0:
                        continue
                    max_plotted_speed = max(max_plotted_speed, boundary_max)

                    theta_vals = list(dir_centers) + [float(dir_centers[0])]
                    r_vals = list(boundary) + [float(boundary[0])]
                    alpha = min(0.10 + level_idx * 0.07, 0.42)

                    fig.add_trace(go.Scatterpolar(
                        theta=theta_vals,
                        r=r_vals,
                        mode="lines",
                        name=label,
                        legendgroup=label,
                        showlegend=first_for_label,
                        line=dict(color=hex_to_rgba(category_colors[label], min(alpha + 0.28, 0.95)), width=1.1),
                        fill="toself",
                        fillcolor=hex_to_rgba(category_colors[label], alpha),
                        hoverinfo="skip",
                    ))
                    first_for_label = False

                if not first_for_label:
                    traces_added += 1

            if traces_added == 0:
                return None

            # Add a transparent hover mesh so one hover card shows all layer values
            # at the hovered direction/speed location.
            speed_centers = speed_edges[:-1] + (speed_step / 2.0)
            theta_mesh = np.tile(dir_centers, len(speed_centers))
            r_mesh = np.repeat(speed_centers, len(dir_centers))

            layer_hover_order = [
                "Fog",
                "2000ft - 1500ft cloud",
                "1500ft - 1000ft cloud",
                "1000ft - 500ft cloud",
                "< 500ft cloud",
            ]
            hover_fields = {
                label: layer_fields.get(label, np.zeros((len(speed_centers), len(dir_centers)), dtype=float))
                for label in layer_hover_order
            }

            custom_rows: list[list[float]] = []
            for speed_idx in range(len(speed_centers)):
                for dir_idx in range(len(dir_centers)):
                    custom_rows.append([
                        float(hover_fields["Fog"][speed_idx, dir_idx]),
                        float(hover_fields["2000ft - 1500ft cloud"][speed_idx, dir_idx]),
                        float(hover_fields["1500ft - 1000ft cloud"][speed_idx, dir_idx]),
                        float(hover_fields["1000ft - 500ft cloud"][speed_idx, dir_idx]),
                        float(hover_fields["< 500ft cloud"][speed_idx, dir_idx]),
                    ])

            fig.add_trace(go.Scatterpolar(
                theta=theta_mesh,
                r=r_mesh,
                mode="markers",
                name="",
                showlegend=False,
                marker=dict(size=14, color="rgba(0,0,0,0.001)"),
                meta={"hoverGrid": "fog_layer_values"},
                customdata=custom_rows,
                hovertemplate=(
                    "Direction: %{theta:.0f}°<br>"
                    "Wind Speed: %{r:.1f} kt<br>"
                    "Fog: %{customdata[0]:.3f}%<br>"
                    "2000ft - 1500ft cloud: %{customdata[1]:.3f}%<br>"
                    "1500ft - 1000ft cloud: %{customdata[2]:.3f}%<br>"
                    "1000ft - 500ft cloud: %{customdata[3]:.3f}%<br>"
                    "< 500ft cloud: %{customdata[4]:.3f}%"
                    "<extra></extra>"
                ),
            ))

            display_max_speed = max(10.0, float(math.ceil((max_plotted_speed * 1.1) / 5.0) * 5.0))

            bg_img_base64 = None
            try:
                airport_lat = COORDS_DF.loc[icao, "LAT"]
                airport_lon = COORDS_DF.loc[icao, "LONG"]
                bg_img_base64 = get_centered_background(float(airport_lat), float(airport_lon), zoom=ZOOM_LEVEL)
            except Exception:
                pass

            fig.update_layout(
                title=title,
                polar=dict(
                    bgcolor="rgba(0,0,0,0)",
                    angularaxis=dict(direction="clockwise", period=360),
                    radialaxis=dict(angle=90, tickangle=90, ticksuffix=" kt", range=[0, display_max_speed]),
                ),
                legend=dict(title_text="Category", groupclick="togglegroup"),
                margin=dict(l=36, r=36, t=52, b=22),
            )
            if bg_img_base64:
                apply_polar_background(fig, bg_img_base64)
            return fig

        if not fog_df.empty:
            fog_mode_map = split_fog_day_type_datasets(fog_df, icao)
            fog_df = fog_mode_map["all"][0]

            if fog_df.empty:
                add_placeholder("monthly_fog", "Fog/Low Cloud Frequency (Non-rain Days)", "No records for selected filters")
                add_placeholder("fog_share", "Fog/Low Cloud Frequency (Rain Days)", "No records for selected filters")
                add_placeholder("cloud_distribution", "Low Cloud Amount Distribution", "No records for selected filters")
                add_placeholder("fog_cloud_joint", "Fog + Low Cloud Co-occurrence", "No records for selected filters")
            else:
                selected_monthly_df, selected_monthly_label = fog_mode_map.get(fogMonthlyMode, fog_mode_map["all"])
                selected_hourly_df, selected_hourly_label = fog_mode_map.get(fogHourlyMode, fog_mode_map["all"])
                selected_wind_df, selected_wind_label = fog_mode_map.get(fogWindMode, fog_mode_map["all"])
                selected_dewpoint_df, selected_dewpoint_label = fog_mode_map.get(fogDewpointMode, fog_mode_map["all"])

                fig_selected_frequency = None
                if not selected_monthly_df.empty:
                    fig_selected_frequency = build_fog_low_cloud_frequency_figure(
                        selected_monthly_df,
                        f"Fog/Low Cloud Frequency ({selected_monthly_label})",
                        icao,
                        month_number_order,
                    )
                if fig_selected_frequency is not None:
                    apply_common_layout(fig_selected_frequency)
                    apply_fog_side_legend(fig_selected_frequency)
                    apply_frequency_panel_layout(fig_selected_frequency)
                    if "monthly_fog" in y_ceilings:
                        fig_selected_frequency.update_yaxes(range=[0, y_ceilings["monthly_fog"]], autorange=False)
                    fog_figures.append(fig_payload("monthly_fog", fig_selected_frequency))
                else:
                    add_placeholder("monthly_fog", f"Fog/Low Cloud Frequency ({selected_monthly_label})", "No records for selected day filter")

                fig_selected_hourly = build_fog_low_cloud_hourly_chart(
                    selected_hourly_df,
                    f"Fog/Low Cloud Frequency by Hour ({selected_hourly_label})",
                )
                if fig_selected_hourly is not None:
                    apply_common_layout(fig_selected_hourly)
                    apply_fog_side_legend(fig_selected_hourly)
                    apply_frequency_panel_layout(fig_selected_hourly)
                    if "fog_share" in y_ceilings:
                        fig_selected_hourly.update_yaxes(range=[0, y_ceilings["fog_share"]], autorange=False)
                    fog_figures.append(fig_payload("fog_share", fig_selected_hourly))
                else:
                    add_placeholder("fog_share", f"Fog/Low Cloud Frequency by Hour ({selected_hourly_label})", "No hourly fog/low cloud data available for selected day filter")

                fig_selected_wind = build_fog_low_cloud_wind_plot(
                    selected_wind_df,
                    f"Wind Direction/Strength ({selected_wind_label})",
                )
                if fig_selected_wind is not None:
                    apply_common_layout(fig_selected_wind)
                    apply_fog_side_legend(fig_selected_wind, groupclick="togglegroup", top_margin=52)
                    fog_figures.append(fig_payload("cloud_distribution", fig_selected_wind))
                else:
                    add_placeholder("cloud_distribution", f"Wind Direction/Strength ({selected_wind_label})", "No directional data available for selected day filter")

                fig_selected_dewpoint = build_fog_low_cloud_dewpoint_chart(
                    selected_dewpoint_df,
                    f"Avg Dewpoint by Month ({selected_dewpoint_label})",
                )
                if fig_selected_dewpoint is not None:
                    apply_common_layout(fig_selected_dewpoint)
                    apply_fog_side_legend(fig_selected_dewpoint)
                    apply_frequency_panel_layout(fig_selected_dewpoint)
                    if "fog_cloud_joint_min" in y_ceilings and "fog_cloud_joint_max" in y_ceilings:
                        fig_selected_dewpoint.update_yaxes(
                            range=[y_ceilings["fog_cloud_joint_min"], y_ceilings["fog_cloud_joint_max"]],
                            autorange=False,
                        )
                    fog_figures.append(fig_payload("fog_cloud_joint", fig_selected_dewpoint))
                else:
                    add_placeholder("fog_cloud_joint", f"Avg Dewpoint by Month ({selected_dewpoint_label})", "No dewpoint data available for selected day filter")
        else:
            add_placeholder("monthly_fog", "Fog/Low Cloud Frequency (All Days)", "No records for selected filters")
            add_placeholder("fog_share", "Fog/Low Cloud Frequency by Hour (All Days)", "No hourly fog/low cloud data available for selected filters")
            add_placeholder("cloud_distribution", "Wind Direction/Strength (All Days)", "No records for selected filters")
            add_placeholder("fog_cloud_joint", "Avg Dewpoint by Month (All Days)", "No dewpoint data available for selected filters")

        figures.extend(fog_figures[:4])


    elif section == "smoke_dust":
        # Select all relevant columns for all plots
        smoke_df = filtered_df.select([
            "year", "month", "hour", "PRST_WX_PHENOM_1", "PRST_WX_PHENOM_2",
            "WND_SPD", "DWPT", "WND_DIR"
        ]).to_pandas()
        smoke_tokens = ["FU", "DU", "SA", "VA"]
        phenom_colors = {
            "FU": "#7a7a7a",
            "DU": "#EF553B",
            "SA": "#00CC96",
            "VA": "#AB63FA",
        }

        # Filter to only dust/smoke/volcanic observations
        mask = token_mask_from_fields(smoke_df, ["PRST_WX_PHENOM_1", "PRST_WX_PHENOM_2"], smoke_tokens)
        dust_df = smoke_df[mask].copy()

        # Assign a single phenomenon code per observation for consistent coloring.
        def get_phenom(row: pd.Series) -> str:
            p1 = str(row.get("PRST_WX_PHENOM_1", "")).upper()
            p2 = str(row.get("PRST_WX_PHENOM_2", "")).upper()
            for code in smoke_tokens:
                if code in p1 or code in p2:
                    return code
            return "Other"

        if not dust_df.empty:
            dust_df["Phenomenon"] = dust_df.apply(get_phenom, axis=1)

        # Top left: Monthly paired frequency by phenomenon (averaged by month)
        if not dust_df.empty:
            monthly_smoke = (
                dust_df.groupby(["year", "month", "Phenomenon"], as_index=False)
                .size()
                .rename(columns={"size": "Count"})
            )
            monthly_smoke = (
                monthly_smoke.groupby(["month", "Phenomenon"], as_index=False)["Count"]
                .mean()
            )
            monthly_smoke = monthly_smoke[monthly_smoke["month"].isin(month_number_order)].copy()
            monthly_smoke["Month"] = monthly_smoke["month"].apply(lambda m: MONTH_NAMES[m - 1])
            monthly_smoke["Month"] = pd.Categorical(monthly_smoke["Month"], categories=month_name_order, ordered=True)
            monthly_smoke = monthly_smoke.sort_values(["Month", "Phenomenon"])

            fig_smoke = px.bar(
                monthly_smoke,
                x="Month",
                y="Count",
                color="Phenomenon",
                barmode="group",
                labels={"Count": "Avg Obs/Month", "Phenomenon": "Type"},
                title="Monthly Smoke/Dust Frequency by Phenomenon",
                color_discrete_map=phenom_colors,
                category_orders={"Month": month_name_order, "Phenomenon": smoke_tokens},
            )
            fig_smoke.update_xaxes(title_text="")
            apply_common_layout(fig_smoke)
            apply_frequency_panel_layout(fig_smoke)
            fig_smoke.update_layout(
                margin=dict(l=36, r=DEFAULT_LEGEND_ENTRY_WIDTH + LEGEND_MARGIN_PADDING, t=36, b=8),
            )
            if "monthly_smoke" in y_ceilings:
                fig_smoke.update_yaxes(range=[0, y_ceilings["monthly_smoke"]], autorange=False)
            figures.append(fig_payload("monthly_smoke", fig_smoke))
        else:
            # Placeholder if no data
            fig = build_placeholder_figure("Monthly Smoke/Dust Frequency by Phenomenon")
            apply_common_layout(fig)
            figures.append(fig_payload("monthly_smoke", fig))

        # Top right: Hourly paired frequency by phenomenon
        if not dust_df.empty and "hour" in dust_df.columns:
            hourly = (
                dust_df.groupby(["hour", "Phenomenon"], as_index=False)
                .size()
                .rename(columns={"size": "Count"})
            )
            fig_hour = px.bar(
                hourly,
                x="hour",
                y="Count",
                color="Phenomenon",
                barmode="group",
                labels={"Count": "Observations", "Phenomenon": "Type"},
                title="Hourly Smoke/Dust Frequency by Phenomenon",
                color_discrete_map=phenom_colors,
                category_orders={"Phenomenon": smoke_tokens},
            )
            fig_hour.update_xaxes(
                title_text="",
                tickmode="array",
                tickvals=[0, 5, 10, 15, 20],
                ticktext=["00Z", "05Z", "10Z", "15Z", "20Z"],
            )
            apply_common_layout(fig_hour)
            apply_frequency_panel_layout(fig_hour)
            if "hourly_smoke" in y_ceilings:
                fig_hour.update_yaxes(range=[0, y_ceilings["hourly_smoke"]], autorange=False)
            figures.append(fig_payload("hourly_smoke", fig_hour))
        else:
            fig = build_placeholder_figure("Hourly Smoke/Dust Frequency by Phenomenon")
            apply_common_layout(fig)
            figures.append(fig_payload("hourly_smoke", fig))

        scatter_payload: dict[str, Any]
        radial_payload: dict[str, Any]

        # Bottom right: Wind speed vs dew point scatter plot
        if not dust_df.empty and "WND_SPD" in dust_df.columns and "DWPT" in dust_df.columns:
            scatter_df = dust_df.dropna(subset=["WND_SPD", "DWPT"]).copy()
            fig_scatter = go.Figure()

            for code in smoke_tokens:
                sub = scatter_df[scatter_df["Phenomenon"] == code]
                if sub.empty:
                    continue

                fig_scatter.add_trace(go.Scatter(
                    x=sub["DWPT"],
                    y=sub["WND_SPD"],
                    mode="markers",
                    name=code,
                    legendgroup=code,
                    marker=dict(color=phenom_colors[code], size=7, opacity=0.65),
                    hovertemplate="Type: %{text}<br>Dew Point: %{x:.1f} °C<br>Wind Speed: %{y:.1f} kt<extra></extra>",
                    text=[code] * len(sub),
                ))

                # Add least-squares fit line per phenomenon when possible.
                x_vals = pd.to_numeric(sub["DWPT"], errors="coerce")
                y_vals = pd.to_numeric(sub["WND_SPD"], errors="coerce")
                fit_df = pd.DataFrame({"x": x_vals, "y": y_vals}).dropna()
                if len(fit_df) >= 2 and fit_df["x"].nunique() > 1:
                    x_mean = float(fit_df["x"].mean())
                    y_mean = float(fit_df["y"].mean())
                    var_x = float(((fit_df["x"] - x_mean) ** 2).sum())
                    if var_x > 0:
                        cov_xy = float(((fit_df["x"] - x_mean) * (fit_df["y"] - y_mean)).sum())
                        slope = cov_xy / var_x
                        intercept = y_mean - slope * x_mean
                        x_min = float(fit_df["x"].min())
                        x_max = float(fit_df["x"].max())
                        y_min = slope * x_min + intercept
                        y_max = slope * x_max + intercept

                        # 1 SD confidence-style shading around the fitted line.
                        y_std = float(fit_df["y"].std(ddof=1)) if len(fit_df) > 1 else 0.0
                        if math.isfinite(y_std) and y_std > 0:
                            ci_fill = phenom_colors[code]
                            if ci_fill.startswith("#") and len(ci_fill) == 7:
                                r = int(ci_fill[1:3], 16)
                                g = int(ci_fill[3:5], 16)
                                b = int(ci_fill[5:7], 16)
                                ci_fill = f"rgba({r},{g},{b},0.16)"
                            fig_scatter.add_trace(go.Scatter(
                                x=[x_min, x_max, x_max, x_min],
                                y=[y_min - y_std, y_max - y_std, y_max + y_std, y_min + y_std],
                                mode="lines",
                                name=f"{code} ±1SD",
                                legendgroup=code,
                                showlegend=False,
                                visible="legendonly",
                                line=dict(width=0, color="rgba(0,0,0,0)"),
                                fill="toself",
                                fillcolor=ci_fill,
                                hoverinfo="skip",
                                meta={"ciBand": True},
                            ))

                        fig_scatter.add_trace(go.Scatter(
                            x=[x_min, x_max],
                            y=[y_min, y_max],
                            mode="lines",
                            name=f"{code} fit",
                            legendgroup=code,
                            showlegend=False,
                            line=dict(color=phenom_colors[code], width=2),
                            hovertemplate=(
                                f"{code} fit<br>"
                                "Dew Point: %{x:.1f} °C<br>"
                                "Wind Speed: %{y:.1f} kt<extra></extra>"
                            ),
                        ))

            fig_scatter.update_layout(
                title="Wind Speed vs Dew Point (Dust/Smoke)",
                xaxis_title="Dew Point (°C)",
                yaxis_title="Wind Speed (kt)",
                legend=dict(title_text="Phenomenon", groupclick="togglegroup"),
            )
            apply_common_layout(fig_scatter)
            if "scatter_wind_dewpt" in y_ceilings:
                fig_scatter.update_yaxes(range=[0, y_ceilings["scatter_wind_dewpt"]], autorange=False)
            scatter_payload = fig_payload("scatter_wind_dewpt", fig_scatter)
        else:
            fig = build_placeholder_figure("Wind Speed vs Dew Point (Dust/Smoke)")
            apply_common_layout(fig)
            scatter_payload = fig_payload("scatter_wind_dewpt", fig)


        # Bottom left: Smoothed polar frequency glow plot (all phenomena at once).
        if not dust_df.empty and "WND_DIR" in dust_df.columns and "WND_SPD" in dust_df.columns:
            scatter_polar = go.Figure()

            direction_step = 10.0
            max_speed = 40.0
            speed_step = 1.0
            dir_edges = np.arange(0.0, 360.0 + direction_step, direction_step)
            dir_centers = dir_edges[:-1] + (direction_step / 2.0)
            speed_edges = np.arange(0.0, max_speed + speed_step, speed_step)

            # Keep low-frequency areas transparent so map background remains visible.
            cutoff_pct = 0.06

            def hex_to_rgba(hex_color: str, alpha: float) -> str:
                color = hex_color.lstrip("#")
                if len(color) != 6:
                    return f"rgba(0,0,0,{alpha})"
                r = int(color[0:2], 16)
                g = int(color[2:4], 16)
                b = int(color[4:6], 16)
                return f"rgba({r},{g},{b},{alpha})"

            def smooth_frequency_field(field: np.ndarray, passes: int = 3) -> np.ndarray:
                out = field.astype(float).copy()
                for _ in range(passes):
                    # Circular smoothing in direction.
                    out = (np.roll(out, 1, axis=1) + 2.0 * out + np.roll(out, -1, axis=1)) / 4.0
                    # Radial smoothing in speed.
                    padded = np.pad(out, ((1, 1), (0, 0)), mode="edge")
                    out = (padded[:-2] + 2.0 * padded[1:-1] + padded[2:]) / 4.0
                return out

            def boundary_from_level(field: np.ndarray, level: float) -> np.ndarray:
                boundary = np.full(len(dir_centers), np.nan)
                for col_idx in range(len(dir_centers)):
                    column = field[:, col_idx]
                    hit_idx = np.where(column >= level)[0]
                    if len(hit_idx) > 0:
                        boundary[col_idx] = float(speed_edges[int(hit_idx.max()) + 1])

                # Fill sparse gaps with zero radius to preserve transparency and avoid artifacts.
                boundary = np.nan_to_num(boundary, nan=0.0)
                boundary = (np.roll(boundary, 1) + 2.0 * boundary + np.roll(boundary, -1)) / 4.0
                return boundary

            traces_added = 0
            max_plotted_speed = 0.0
            legend_order = {code: idx for idx, code in enumerate(smoke_tokens)}
            layer_fields: dict[str, np.ndarray] = {}
            plotted_codes: list[str] = []
            # Draw order controls visual layering. Later traces sit on top.
            layer_order = ["DU", "FU", "SA", "VA"]
            for code in layer_order:
                sub = dust_df[(dust_df["Phenomenon"] == code) & dust_df["WND_DIR"].notna() & dust_df["WND_SPD"].notna()].copy()
                if sub.empty:
                    continue

                dir_vals = np.mod(pd.to_numeric(sub["WND_DIR"], errors="coerce"), 360.0).to_numpy()
                spd_vals = pd.to_numeric(sub["WND_SPD"], errors="coerce").to_numpy()
                valid = np.isfinite(dir_vals) & np.isfinite(spd_vals)
                dir_vals = dir_vals[valid]
                spd_vals = np.clip(spd_vals[valid], 0.0, max_speed)
                if len(dir_vals) == 0:
                    continue

                hist2d, _, _ = np.histogram2d(spd_vals, dir_vals, bins=[speed_edges, dir_edges])
                total_obs = float(hist2d.sum())
                if total_obs <= 0:
                    continue

                rel_field = (hist2d / total_obs) * 100.0
                rel_field = smooth_frequency_field(rel_field, passes=3)
                layer_fields[code] = rel_field

                peak_rel = float(np.nanmax(rel_field)) if rel_field.size else 0.0
                if peak_rel < cutoff_pct:
                    continue

                low = max(cutoff_pct, peak_rel * 0.08)
                high = max(low, peak_rel * 0.92)
                levels = np.geomspace(low, high, num=6)
                levels = sorted({round(float(level), 3) for level in levels})

                first_for_code = True
                for level_idx, level in enumerate(levels):
                    boundary = boundary_from_level(rel_field, level)
                    boundary_max = float(np.max(boundary))
                    if boundary_max <= 0.0:
                        continue
                    max_plotted_speed = max(max_plotted_speed, boundary_max)

                    theta_vals = list(dir_centers) + [float(dir_centers[0])]
                    r_vals = list(boundary) + [float(boundary[0])]
                    alpha = min(0.10 + level_idx * 0.07, 0.42)

                    scatter_polar.add_trace(go.Scatterpolar(
                        theta=theta_vals,
                        r=r_vals,
                        mode="lines",
                        name=code,
                        legendgroup=code,
                        showlegend=first_for_code,
                        legendrank=legend_order.get(code, 999),
                        meta={"legendColor": phenom_colors[code]},
                        line=dict(color=hex_to_rgba(phenom_colors[code], min(alpha + 0.28, 0.95)), width=1.1),
                        fill="toself",
                        fillcolor=hex_to_rgba(phenom_colors[code], alpha),
                        hoverinfo="skip",
                    ))
                    first_for_code = False

                if not first_for_code:
                    traces_added += 1
                    plotted_codes.append(code)

            if traces_added > 0:
                speed_centers = speed_edges[:-1] + (speed_step / 2.0)
                theta_mesh = np.tile(dir_centers, len(speed_centers))
                r_mesh = np.repeat(speed_centers, len(dir_centers))

                hover_order = plotted_codes
                hover_fields = {
                    code: layer_fields.get(code, np.zeros((len(speed_centers), len(dir_centers)), dtype=float))
                    for code in hover_order
                }

                custom_rows: list[list[float]] = []
                for speed_idx in range(len(speed_centers)):
                    for dir_idx in range(len(dir_centers)):
                        custom_rows.append([
                            float(hover_fields[code][speed_idx, dir_idx])
                            for code in hover_order
                        ])

                hover_lines = [
                    "Direction: %{theta:.0f}°",
                    "Wind Speed: %{r:.1f} kt",
                ]
                hover_lines.extend([
                    f"{code}: %{{customdata[{idx}]:.3f}}%"
                    for idx, code in enumerate(hover_order)
                ])
                hover_template = "<br>".join(hover_lines) + "<extra></extra>"

                scatter_polar.add_trace(go.Scatterpolar(
                    theta=theta_mesh,
                    r=r_mesh,
                    mode="markers",
                    name="",
                    showlegend=False,
                    marker=dict(size=14, color="rgba(0,0,0,0.001)"),
                    customdata=custom_rows,
                    hovertemplate=hover_template,
                ))

                display_max_speed = max(10.0, float(math.ceil((max_plotted_speed * 1.1) / 5.0) * 5.0))

                # Apply the same airport-centered topography background used by wind rose charts.
                bg_img_base64 = None
                try:
                    airport_lat = COORDS_DF.loc[icao, "LAT"]
                    airport_lon = COORDS_DF.loc[icao, "LONG"]
                    bg_img_base64 = get_centered_background(float(airport_lat), float(airport_lon), zoom=ZOOM_LEVEL)
                except Exception:
                    pass

                scatter_polar.update_layout(
                    title="Wind Direction/Strength Relative Frequency (Smoothed)",
                    polar=dict(
                        bgcolor="rgba(0,0,0,0)",
                        angularaxis=dict(direction="clockwise", period=360),
                        radialaxis=dict(angle=90, tickangle=90, ticksuffix=" kt", range=[0, display_max_speed]),
                    ),
                    legend=dict(title_text="Phenomenon", groupclick="togglegroup"),
                    margin=dict(l=36, r=36, t=52, b=22),
                )
                if bg_img_base64:
                    apply_polar_background(scatter_polar, bg_img_base64)
                apply_common_layout(scatter_polar)
                radial_payload = fig_payload("radial_scatter_dust", scatter_polar)
            else:
                fig = build_placeholder_figure("Wind Direction/Strength Relative Frequency (Smoothed)")
                apply_common_layout(fig)
                radial_payload = fig_payload("radial_scatter_dust", fig)
        else:
            fig = build_placeholder_figure("Wind Direction/Strength Relative Frequency (Smoothed)")
            apply_common_layout(fig)
            radial_payload = fig_payload("radial_scatter_dust", fig)

        figures.append(radial_payload)
        figures.append(scatter_payload)

    metrics = {
        "observations": int(len(filtered_df)),
        "meanSpeed": float(filtered_df["WND_SPD"].mean()) if len(filtered_df) else 0.0,
        "maxGust": float(filtered_df["MAX_WND_GUST_10"].max()) if len(filtered_df) else 0.0,
        "avgTemp": float(filtered_df["AIR_TEMP"].mean()) if len(filtered_df) else 0.0,
    }

    return {"section": section, "figures": figures, "metrics": metrics}
