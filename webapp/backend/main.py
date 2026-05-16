import base64
import json
import math
import os
import re
import struct
from functools import lru_cache
from io import BytesIO
from typing import Any

import pandas as pd
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

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTH_TO_NUM = {m: i + 1 for i, m in enumerate(MONTH_NAMES)}

# Load data once in memory for fast interactive filtering.
DATA_DF = pl.read_parquet(DATA_FILE)
COORDS_DF = pd.read_csv(COORD_FILE).set_index("ICAO")
AIRPORTS = DATA_DF.select("TARGET_ICAO").unique().sort("TARGET_ICAO").to_series().to_list()
TZ_FINDER = TimezoneFinder(in_memory=True)

PLOT_HEIGHT = 300

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


def fog_low_cloud_mask(df: pd.DataFrame) -> pd.Series:
    fog = token_mask_from_columns(df, ["FG"])
    cld1 = df["CEIL_CLD_AMT_1"].fillna("").astype(str).str.startswith(("BKN", "OVC"))
    cld2 = df["CEIL_CLD_AMT_2"].fillna("").astype(str).str.startswith(("BKN", "OVC"))
    return fog | cld1 | cld2


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


def build_fog_low_cloud_frequency_figure(fog_df: pd.DataFrame, title: str) -> go.Figure:
    work = fog_df.copy()

    low1 = work["CEIL_CLD_AMT_1"].fillna("").astype(str).str.upper().str.startswith(("BKN", "OVC"))
    low2 = work["CEIL_CLD_AMT_2"].fillna("").astype(str).str.upper().str.startswith(("BKN", "OVC"))
    h1 = pd.to_numeric(work["CEIL_CLD_HT_1"], errors="coerce")
    h2 = pd.to_numeric(work["CEIL_CLD_HT_2"], errors="coerce")

    threshold_specs = [
        ("below 2000ft", 2000, "#b67a3e"),
        ("below 1500ft", 1500, "#a3612f"),
        ("below 1000ft", 1000, "#8b4a25"),
        ("below 500ft", 500, "#6d2f18"),
    ]

    monthly_components: list[pd.DataFrame] = []
    for label, threshold, _ in threshold_specs:
        mask = ((low1 & h1.lt(threshold)) | (low2 & h2.lt(threshold))).astype(int)
        comp = work[["year", "month"]].copy()
        comp[label] = mask
        monthly = comp.groupby(["year", "month"])[label].sum().reset_index()
        monthly = monthly.groupby("month", as_index=False)[label].mean()
        monthly["Component"] = label
        monthly.rename(columns={label: "Count"}, inplace=True)
        monthly_components.append(monthly)

    low_cloud_components = pd.concat(monthly_components, ignore_index=True)
    low_cloud_components["Month"] = low_cloud_components["month"].apply(lambda m: MONTH_NAMES[m - 1])
    low_cloud_components["Month"] = pd.Categorical(low_cloud_components["Month"], categories=MONTH_NAMES, ordered=True)

    fog_monthly = monthly_flag_frequency(
        work[["year", "month", "PRST_WX_PHENOM_1", "PRST_WX_PHENOM_2"]].copy(),
        ["FG"],
        "Fog",
        fields=["PRST_WX_PHENOM_1", "PRST_WX_PHENOM_2"],
    )
    if not fog_monthly.empty:
        fog_monthly = fog_monthly.groupby("month", as_index=False)["Fog"].mean()
    else:
        fog_monthly = pd.DataFrame({"month": list(range(1, 13)), "Fog": 0.0})
    fog_monthly["Month"] = fog_monthly["month"].apply(lambda m: MONTH_NAMES[m - 1])
    fog_monthly["Month"] = pd.Categorical(fog_monthly["Month"], categories=MONTH_NAMES, ordered=True)
    fog_monthly = fog_monthly.sort_values("Month")

    fig = go.Figure()
    for label, _, color in threshold_specs:
        band = low_cloud_components[low_cloud_components["Component"] == label][["Month", "Count"]].copy()
        band = band.set_index("Month").reindex(MONTH_NAMES, fill_value=0.0).reset_index()
        fig.add_bar(
            x=band["Month"],
            y=band["Count"],
            name=label,
            offsetgroup="low_cloud",
            legendgroup="low_cloud",
            marker_color=color,
            hovertemplate="Month: %{x}<br>Low cloud " + label + ": %{y:.2f}<extra></extra>",
        )

    fig.add_bar(
        x=fog_monthly["Month"],
        y=fog_monthly["Fog"],
        name="Fog",
        offsetgroup="fog",
        legendgroup="fog",
        marker_color="#d4af37",
        hovertemplate="Month: %{x}<br>Fog: %{y:.2f}<extra></extra>",
    )

    fig.update_layout(
        barmode="stack",
        title=title,
        yaxis_title="Avg Obs/Month",
        legend_title_text="Category",
    )
    return fig


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


def build_range_mask(col_name: str, selected_range: tuple[int, int], invert: bool = False) -> pl.Expr:
    start, end = selected_range
    if invert:
        return (pl.col(col_name) <= start) | (pl.col(col_name) >= end)
    return pl.col(col_name).is_between(start, end)


@lru_cache(maxsize=128)
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


def apply_common_layout(fig: Any, height: int = PLOT_HEIGHT) -> None:
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#333333", family="Source Sans 3, Open Sans, Arial, sans-serif"),
        title=dict(x=0.01, xanchor="left", y=0.98, yanchor="top", font=dict(size=18)),
        legend=dict(
            x=1.18,
            xanchor="right",
            y=0.98,
            yanchor="top",
            font=dict(size=11),
            bgcolor="rgba(255,255,255,0.88)",
            bordercolor="#c7d4ef",
            borderwidth=1,
        ),
        margin=dict(l=36, r=180, t=36, b=22),
        height=height,
    )


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
    # Convert figure to dict and decode any binary-encoded arrays
    fig_dict = json.loads(fig.to_json())

    # Recursively decode binary data in figure
    dtype_map: dict[str, tuple[str, int]] = {
        "f8": ("d", 8),
        "f4": ("f", 4),
        "i8": ("q", 8),
        "i4": ("i", 4),
        "i2": ("h", 2),
        "i1": ("b", 1),
        "u8": ("Q", 8),
        "u4": ("I", 4),
        "u2": ("H", 2),
        "u1": ("B", 1),
        "b1": ("?", 1),
    }

    def decode_binary_arrays(obj: Any) -> Any:
        if isinstance(obj, dict):
            if "dtype" in obj and "bdata" in obj:
                # Decode Plotly's binary format
                try:
                    dtype = str(obj["dtype"])
                    bdata = base64.b64decode(obj["bdata"])
                    fmt_info = dtype_map.get(dtype)
                    if fmt_info is None:
                        return obj

                    fmt_char, item_size = fmt_info
                    if len(bdata) == 0:
                        return []
                    if len(bdata) % item_size != 0:
                        return obj

                    count = len(bdata) // item_size
                    return list(struct.unpack(f"<{count}{fmt_char}", bdata))
                except Exception:
                    pass
                return obj
            else:
                return {k: decode_binary_arrays(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [decode_binary_arrays(item) for item in obj]
        else:
            return obj
    
    fig_dict = decode_binary_arrays(fig_dict)
    return {"id": fig_id, "figure": fig_dict}


@app.get("/")
def root() -> FileResponse:
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/favicon.svg")
def favicon() -> FileResponse:
    return FileResponse(os.path.join(ROOT_DIR, "favicon.svg"))


@app.get("/api/options")
def options() -> dict[str, Any]:
    airports = AIRPORTS
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

    month_range = (MONTH_TO_NUM[monthStart], MONTH_TO_NUM[monthEnd])

    filtered_df = DATA_DF.filter(
        (pl.col("TARGET_ICAO") == icao)
        & (build_range_mask("year", (yearStart, yearEnd)))
        & (build_range_mask("month", month_range, invertMonth))
        & (build_range_mask("hour", (hourStart, hourEnd), invertHour))
    )

    if filtered_df.is_empty():
        return {"section": section, "figures": [], "warning": f"No data found for {icao} with these filters."}

    figures: list[dict[str, Any]] = []

    if section == "overview":
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
            fig_rose.update_layout(
                images=[
                    dict(
                        source=bg_img_base64,
                        xref="paper",
                        yref="paper",
                        x=0.5,
                        y=0.5,
                        sizex=1.1,
                        sizey=1.1,
                        xanchor="center",
                        yanchor="middle",
                        sizing="contain",
                        layer="below",
                        opacity=0.7,
                    )
                ]
            )
        except Exception:
            pass
        fig_rose.update_layout(
            legend=dict(bgcolor="rgba(255,255,255,0.88)", bordercolor="#c7d4ef", borderwidth=1),
            polar=dict(bgcolor="rgba(0,0,0,0)", angularaxis=dict(direction="clockwise", period=360)),
        )
        apply_wind_rose_style(fig_rose)
        apply_common_layout(fig_rose)
        figures.append(fig_payload("wind_rose", fig_rose))

        rain_df = filtered_df.select([
            "year",
            "month",
            "PRST_WX_DSC_1",
            "PRST_WX_PHENOM_1",
            "PRST_WX_DSC_2",
            "PRST_WX_PHENOM_2",
        ]).to_pandas()
        if not rain_df.empty:
            rain_avg = paired_monthly_frequency(
                rain_df,
                {
                    "Rain": {"fields": ["PRST_WX_PHENOM_1", "PRST_WX_PHENOM_2"], "tokens": ["RA", "SH", "DZ"]},
                    "Thunderstorm": {"fields": ["PRST_WX_DSC_1", "PRST_WX_DSC_2"], "tokens": ["TS"]},
                },
            )
            fig_rain = px.bar(
                rain_avg,
                x="Month",
                y="Count",
                color="Type",
                barmode="group",
                color_discrete_map={"Rain": "#2159d1", "Thunderstorm": "#c62828"},
                labels={"Count": "Avg Obs/Month", "Type": "Category"},
                title="Rain/Thunderstorm Frequency",
                category_orders={"Month": MONTH_NAMES, "Type": ["Rain", "Thunderstorm"]},
            )
            apply_common_layout(fig_rain)
            figures.append(fig_payload("rain_thunder", fig_rain))

        temp_df = filtered_df.select(["TM_FULL", "AIR_TEMP", "DWPT"]).to_pandas()
        if not temp_df.empty:
            temp_avg = monthly_avg_daily_extremes(temp_df, icao)
        else:
            temp_avg = pd.DataFrame()

        if not temp_avg.empty:
            fig_temp = px.line(
                temp_avg,
                x="Month",
                y=["Avg Daily Max T", "Avg Daily Min T", "Avg Daily Max Td", "Avg Daily Min Td"],
                labels={"value": "C", "variable": ""},
                markers=True,
                title="Temperature & Dewpoint",
            )
            temp_trace_styles = {
                "Avg Daily Max T": {"color": "#d32f2f", "visible": True},
                "Avg Daily Min T": {"color": "#ef9a9a", "visible": True},
                "Avg Daily Max Td": {"color": "#1565c0", "visible": "legendonly"},
                "Avg Daily Min Td": {"color": "#90caf9", "visible": "legendonly"},
            }
            for trace in fig_temp.data:
                style = temp_trace_styles.get(trace.name)
                if style:
                    trace.line.color = style["color"]
                    trace.marker.color = style["color"]
                    trace.visible = style["visible"]
            apply_common_layout(fig_temp)
            figures.append(fig_payload("temp_dewpoint", fig_temp))

        fog_df = filtered_df.select([
            "year",
            "month",
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
            # Get fog counts by month
            fog_count = fog_df.copy()
            fog_count["is_fog"] = token_mask_from_fields(fog_count, ["PRST_WX_PHENOM_1", "PRST_WX_PHENOM_2"], ["FG"])
            fog_monthly_count = fog_count[fog_count["is_fog"]].groupby("month").size().reset_index(name="Count")
            fog_monthly_count["Type"] = "Fog"
            
            # Get low cloud counts by month and ceiling height threshold
            lc_df = fog_df.copy()
            lc_df["is_low_cloud"] = token_mask_from_fields(lc_df, ["CEIL_CLD_AMT_1", "CEIL_CLD_AMT_2"], ["BKN", "OVC"])
            
            # Expand heights to long format
            heights_list = []
            months_list = []
            for idx, row in lc_df[lc_df["is_low_cloud"]].iterrows():
                for ht_col in ["CEIL_CLD_HT_1", "CEIL_CLD_HT_2"]:
                    if pd.notna(row[ht_col]):
                        heights_list.append(row[ht_col])
                        months_list.append(row["month"])
            
            if heights_list:
                height_month_df = pd.DataFrame({"month": months_list, "height": heights_list})
                # Classify by threshold (heights in feet; working backwards from largest)
                height_month_df["Threshold"] = "below 2000ft"
                height_month_df.loc[height_month_df["height"] < 1500, "Threshold"] = "below 1500ft"
                height_month_df.loc[height_month_df["height"] < 1000, "Threshold"] = "below 1000ft"
                height_month_df.loc[height_month_df["height"] < 500, "Threshold"] = "below 500ft"
                
                lc_monthly_count = height_month_df.groupby(["month", "Threshold"]).size().reset_index(name="Count")
                # Normalize by number of months
                num_years = len(lc_df["year"].unique())
                lc_monthly_count["Count"] = lc_monthly_count["Count"] / num_years if num_years > 0 else 0
                lc_monthly_count["Type"] = "Low cloud"
            else:
                lc_monthly_count = pd.DataFrame(columns=["month", "Threshold", "Count", "Type"])
            
            # Add Month column for both
            fog_monthly_count["Threshold"] = None
            fog_monthly_count["Month"] = fog_monthly_count["month"].apply(lambda m: MONTH_NAMES[m - 1])
            
            lc_monthly_count["Month"] = lc_monthly_count["month"].apply(lambda m: MONTH_NAMES[m - 1])
            
            # Combine for plotting
            combined = pd.concat([
                fog_monthly_count[["Month", "Count", "Type", "Threshold"]],
                lc_monthly_count[["Month", "Count", "Type", "Threshold"]]
            ], ignore_index=True)
            
            # Create grouped/stacked bar chart
            # Use custom sorting for legend
            threshold_order = ["below 500ft", "below 1000ft", "below 1500ft", "below 2000ft"]
            combined_sorted = combined.copy()
            combined_sorted["Threshold"] = combined_sorted["Threshold"].fillna("N/A")
            
            fig_fog = px.bar(
                combined_sorted,
                x="Month",
                y="Count",
                color="Threshold",
                facet_col="Type",
                labels={"Count": "Avg Obs/Month", "Threshold": "Ceiling Height"},
                title="Fog/Low Cloud Frequency",
                category_orders={
                    "Month": MONTH_NAMES,
                    "Type": ["Low cloud", "Fog"],
                    "Threshold": threshold_order + ["N/A"]
                },
                color_discrete_map={
                    "below 500ft": "#8b0000",
                    "below 1000ft": "#c62828",
                    "below 1500ft": "#e57373",
                    "below 2000ft": "#ef9a9a",
                    "N/A": "#d4af37",
                },
                barmode="stack",
            )
            fig_fog.update_xaxes(title_text="")
            fig_fog.update_yaxes(title_text="Avg Obs/Month")
            # Clean up facet labels
            for annotation in fig_fog.layout.annotations:
                if "Threshold=" not in annotation.text:
                    annotation.text = annotation.text.replace("Type=", "")
            apply_common_layout(fig_fog)
            figures.append(fig_payload("fog_low_cloud", fig_fog))

    elif section == "wind":
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
            fig_rose.update_layout(
                images=[
                    dict(
                        source=bg_img_base64,
                        xref="paper",
                        yref="paper",
                        x=0.5,
                        y=0.5,
                        sizex=1.1,
                        sizey=1.1,
                        xanchor="center",
                        yanchor="middle",
                        sizing="contain",
                        layer="below",
                        opacity=0.7,
                    )
                ]
            )
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
            margin=dict(l=62, r=180, t=48, b=22),
            polar=dict(
                domain=dict(x=[0.14, 0.92], y=[0.0, 0.93]),
                bgcolor="rgba(0,0,0,0)",
                angularaxis=dict(direction="clockwise", period=360),
            ),
        )
        figures.append(fig_payload("wind_rose", fig_rose))

        gale_df = filtered_df.select([
            "year",
            "month",
            "WND_SPD",
            "MAX_WND_GUST_10",
            "PRST_WX_DSC_1",
            "PRST_WX_PHENOM_1",
            "PRST_WX_DSC_2",
            "PRST_WX_PHENOM_2",
        ]).to_pandas()

        categories = ["No wx", "SHRA", "TS"]
        full_index = pd.MultiIndex.from_product([range(1, 13), categories], names=["month", "Category"])
        monthly_avg = pd.DataFrame(index=full_index).reset_index()
        monthly_avg["Count"] = 0.0

        if not gale_df.empty:
            # Gale definition: WND_SPD > 34 knots OR MAX_WND_GUST_10 > 41 knots
            # ADAM provides speeds in m/s, so convert: 34 kt ≈ 17.49 m/s, 41 kt ≈ 21.09 m/s
            gale_mask = (gale_df["WND_SPD"].fillna(-9999) > 17.49) | (gale_df["MAX_WND_GUST_10"].fillna(-9999) > 21.09)
            gale_obs = gale_df[gale_mask].copy()

            if not gale_obs.empty:
                dsc = (gale_obs["PRST_WX_DSC_1"].fillna("").astype(str) + " " + gale_obs["PRST_WX_DSC_2"].fillna("").astype(str)).str.upper()
                phenom = (gale_obs["PRST_WX_PHENOM_1"].fillna("").astype(str) + " " + gale_obs["PRST_WX_PHENOM_2"].fillna("").astype(str)).str.upper()

                is_ts = dsc.str.contains("TS", regex=False)
                is_shra = dsc.str.contains("SH", regex=False) & phenom.str.contains("RA", regex=False)

                gale_obs["Category"] = "No wx"
                gale_obs.loc[is_shra, "Category"] = "SHRA"
                gale_obs.loc[is_ts, "Category"] = "TS"

                monthly_counts = gale_obs.groupby(["year", "month", "Category"]).size().reset_index(name="Gales")
                monthly_avg_counts = monthly_counts.groupby(["month", "Category"], as_index=False)["Gales"].mean()
                monthly_avg_counts = monthly_avg_counts.rename(columns={"Gales": "Count"})

                monthly_avg = monthly_avg.drop(columns=["Count"]).merge(monthly_avg_counts, on=["month", "Category"], how="left")
                monthly_avg["Count"] = monthly_avg["Count"].fillna(0.0)

        monthly_avg["Month"] = monthly_avg["month"].apply(lambda m: MONTH_NAMES[m - 1])
        monthly_avg["Month"] = pd.Categorical(monthly_avg["Month"], categories=MONTH_NAMES, ordered=True)
        monthly_avg = monthly_avg.sort_values(["Month", "Category"])
        
        # Convert to native Python types to avoid Plotly binary encoding
        monthly_avg["Count"] = monthly_avg["Count"].apply(float)
        monthly_avg["Month"] = monthly_avg["Month"].astype(str)

        fig_gales = px.bar(
            monthly_avg,
            x="Month",
            y="Count",
            color="Category",
            barmode="stack",
            labels={"Count": "Avg Gale Obs/Month"},
            title="Monthly Gale Frequency by Weather Type",
            category_orders={"Month": MONTH_NAMES, "Category": categories},
            color_discrete_map={"No wx": "#7a7a7a", "SHRA": "#3b82c4", "TS": "#c62828"},
        )
        apply_common_layout(fig_gales, height=380)
        figures.append(fig_payload("gale_weather_split", fig_gales))

    elif section == "precipitation":
        precip_df = filtered_df.select([
            "year",
            "month",
            "WND_DIR",
            "VSBY",
            "PRST_WX_DSC_1",
            "PRST_WX_PHENOM_1",
            "PRST_WX_DSC_2",
            "PRST_WX_PHENOM_2",
        ]).to_pandas()
        if not precip_df.empty:
            monthly_precip = paired_monthly_frequency(
                precip_df,
                {
                    "Rain": {"fields": ["PRST_WX_PHENOM_1", "PRST_WX_PHENOM_2"], "tokens": ["RA", "SH", "DZ"]},
                    "Thunderstorm": {"fields": ["PRST_WX_DSC_1", "PRST_WX_DSC_2"], "tokens": ["TS"]},
                },
            )
            fig_precip = px.bar(
                monthly_precip,
                x="Month",
                y="Count",
                color="Type",
                barmode="group",
                color_discrete_map={"Rain": "#2159d1", "Thunderstorm": "#c62828"},
                labels={"Count": "Avg Obs/Month", "Type": "Category"},
                title="Monthly Rain/Thunderstorm Frequency",
                category_orders={"Month": MONTH_NAMES, "Type": ["Rain", "Thunderstorm"]},
            )
            apply_common_layout(fig_precip)
            figures.append(fig_payload("monthly_precip", fig_precip))

        if not precip_df.empty:
            vis_df = precip_df.dropna(subset=["WND_DIR", "VSBY"]).copy()
            vis_df["dir_bin"] = ((vis_df["WND_DIR"] + 11.25) % 360 // 22.5 * 22.5)

            precip_tokens = ["RA", "DZ", "SN", "GS", "GR", "PL", "SH", "TS"]
            precip_fields = ["PRST_WX_DSC_1", "PRST_WX_PHENOM_1", "PRST_WX_DSC_2", "PRST_WX_PHENOM_2"]
            is_precip = token_mask_from_fields(vis_df, precip_fields, precip_tokens)
            precip_obs = vis_df[is_precip].copy()

            if not precip_obs.empty:
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
                    sub = precip_obs[precip_obs["VSBY"] < threshold]
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
                    fig_split.update_layout(
                        images=[
                            dict(
                                source=bg_img_base64,
                                xref="paper",
                                yref="paper",
                                x=0.5,
                                y=0.5,
                                sizex=1.1,
                                sizey=1.1,
                                xanchor="center",
                                yanchor="middle",
                                sizing="contain",
                                layer="below",
                                opacity=0.7,
                            )
                        ]
                    )
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
                figures.append(fig_payload("precip_split", fig_split))

    elif section == "fog_low_cloud":
        fog_df = filtered_df.select([
            "year",
            "month",
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

        def add_placeholder(fig_id: str, title: str, subtitle: str) -> None:
            fig = go.Figure()
            fig.add_annotation(
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                text=subtitle,
                showarrow=False,
                font=dict(size=14, color="#435a84"),
            )
            fig.update_xaxes(visible=False)
            fig.update_yaxes(visible=False)
            fig.update_layout(title=title, plot_bgcolor="white", paper_bgcolor="white")
            apply_common_layout(fig)
            fog_figures.append(fig_payload(fig_id, fig))

        if not fog_df.empty:
            fog_monthly = paired_monthly_frequency(
                fog_df,
                {
                    "Low cloud": {"fields": ["CEIL_CLD_AMT_1", "CEIL_CLD_AMT_2"], "tokens": ["BKN", "OVC"]},
                    "Fog": {"fields": ["PRST_WX_PHENOM_1", "PRST_WX_PHENOM_2"], "tokens": ["FG"]},
                },
            )

            # Top-left: frequency chart with low cloud stacked by ceiling height threshold
            if not fog_monthly.empty:
                # Get fog counts by month
                fog_count = fog_df.copy()
                fog_count["is_fog"] = token_mask_from_fields(fog_count, ["PRST_WX_PHENOM_1", "PRST_WX_PHENOM_2"], ["FG"])
                fog_monthly_count = fog_count[fog_count["is_fog"]].groupby("month").size().reset_index(name="Count")
                fog_monthly_count["Type"] = "Fog"
                
                # Get low cloud counts by month and ceiling height threshold
                lc_df = fog_df.copy()
                lc_df["is_low_cloud"] = token_mask_from_fields(lc_df, ["CEIL_CLD_AMT_1", "CEIL_CLD_AMT_2"], ["BKN", "OVC"])
                
                # Expand heights to long format
                heights_list = []
                months_list = []
                for idx, row in lc_df[lc_df["is_low_cloud"]].iterrows():
                    for ht_col in ["CEIL_CLD_HT_1", "CEIL_CLD_HT_2"]:
                        if pd.notna(row[ht_col]):
                            heights_list.append(row[ht_col])
                            months_list.append(row["month"])
                
                if heights_list:
                    height_month_df = pd.DataFrame({"month": months_list, "height": heights_list})
                    # Classify by threshold (heights in feet; working backwards from largest)
                    height_month_df["Threshold"] = "below 2000ft"
                    height_month_df.loc[height_month_df["height"] < 1500, "Threshold"] = "below 1500ft"
                    height_month_df.loc[height_month_df["height"] < 1000, "Threshold"] = "below 1000ft"
                    height_month_df.loc[height_month_df["height"] < 500, "Threshold"] = "below 500ft"
                    
                    lc_monthly_count = height_month_df.groupby(["month", "Threshold"]).size().reset_index(name="Count")
                    # Normalize by number of months
                    num_years = len(lc_df["year"].unique())
                    lc_monthly_count["Count"] = lc_monthly_count["Count"] / num_years if num_years > 0 else 0
                    lc_monthly_count["Type"] = "Low cloud"
                else:
                    lc_monthly_count = pd.DataFrame(columns=["month", "Threshold", "Count", "Type"])
                
                # Add Month column for both
                fog_monthly_count["Threshold"] = None
                fog_monthly_count["Month"] = fog_monthly_count["month"].apply(lambda m: MONTH_NAMES[m - 1])
                
                lc_monthly_count["Month"] = lc_monthly_count["month"].apply(lambda m: MONTH_NAMES[m - 1])
                
                # Combine for plotting
                combined = pd.concat([
                    fog_monthly_count[["Month", "Count", "Type", "Threshold"]],
                    lc_monthly_count[["Month", "Count", "Type", "Threshold"]]
                ], ignore_index=True)
                
                # Create grouped/stacked bar chart
                # Use custom sorting for legend
                threshold_order = ["below 500ft", "below 1000ft", "below 1500ft", "below 2000ft"]
                combined_sorted = combined.copy()
                combined_sorted["Threshold"] = combined_sorted["Threshold"].fillna("N/A")
                
                fig_fog = px.bar(
                    combined_sorted,
                    x="Month",
                    y="Count",
                    color="Threshold",
                    facet_col="Type",
                    labels={"Count": "Avg Obs/Month", "Threshold": "Ceiling Height"},
                    title="Fog/Low Cloud Frequency",
                    category_orders={
                        "Month": MONTH_NAMES,
                        "Type": ["Low cloud", "Fog"],
                        "Threshold": threshold_order + ["N/A"]
                    },
                    color_discrete_map={
                        "below 500ft": "#8b0000",
                        "below 1000ft": "#c62828",
                        "below 1500ft": "#e57373",
                        "below 2000ft": "#ef9a9a",
                        "N/A": "#d4af37",
                    },
                    barmode="stack",
                )
                fig_fog.update_xaxes(title_text="")
                fig_fog.update_yaxes(title_text="Avg Obs/Month")
                # Clean up facet labels
                for annotation in fig_fog.layout.annotations:
                    if "Threshold=" not in annotation.text:
                        annotation.text = annotation.text.replace("Type=", "")
                apply_common_layout(fig_fog)
                fog_figures.append(fig_payload("monthly_fog", fig_fog))
            else:
                add_placeholder("monthly_fog", "Fog/Low Cloud Frequency", "No data available")

            # Top-right: relative split between fog and low cloud by month.
            if not fog_monthly.empty:
                split = (
                    fog_monthly.pivot_table(index="Month", columns="Type", values="Count", aggfunc="sum")
                    .reindex(MONTH_NAMES)
                    .fillna(0.0)
                    .reset_index()
                )
                split["Total"] = split.get("Fog", 0.0) + split.get("Low cloud", 0.0)
                split["Fog Share"] = split.apply(
                    lambda r: (float(r.get("Fog", 0.0)) / float(r["Total"]) * 100.0) if r["Total"] > 0 else 0.0,
                    axis=1,
                )
                fig_share = px.line(
                    split,
                    x="Month",
                    y="Fog Share",
                    markers=True,
                    labels={"Fog Share": "Fog Share (%)"},
                    title="Fog Share of Combined Fog/Low Cloud",
                    category_orders={"Month": MONTH_NAMES},
                )
                fig_share.update_traces(line=dict(color="#d4af37", width=3), marker=dict(color="#8b5a2b", size=8))
                fig_share.update_layout(yaxis=dict(range=[0, 100]))
                apply_common_layout(fig_share)
                fog_figures.append(fig_payload("fog_share", fig_share))
            else:
                add_placeholder("fog_share", "Fog Share of Combined Fog/Low Cloud", "No data available")

            # Bottom-left: low cloud amount distribution.
            cloud_amounts = pd.concat([fog_df["CEIL_CLD_AMT_1"], fog_df["CEIL_CLD_AMT_2"]], ignore_index=True).dropna()
            if not cloud_amounts.empty:
                cloud_counts = cloud_amounts.value_counts().reset_index()
                cloud_counts.columns = ["Cloud Amount", "Count"]
                fig_cloud = px.bar(
                    cloud_counts,
                    x="Cloud Amount",
                    y="Count",
                    color="Cloud Amount",
                    color_discrete_map={"BKN": "#8b5a2b", "OVC": "#d4af37"},
                    title="Low Cloud Amount Distribution",
                )
                fig_cloud.update_layout(showlegend=False)
                apply_common_layout(fig_cloud)
                fog_figures.append(fig_payload("cloud_distribution", fig_cloud))
            else:
                add_placeholder("cloud_distribution", "Low Cloud Amount Distribution", "No cloud amount records")

            # Bottom-right: monthly co-occurrence rate of fog and low cloud.
            joint = fog_df.copy()
            joint["is_fog"] = token_mask_from_fields(joint, ["PRST_WX_PHENOM_1", "PRST_WX_PHENOM_2"], ["FG"])
            joint["is_low_cloud"] = token_mask_from_fields(joint, ["CEIL_CLD_AMT_1", "CEIL_CLD_AMT_2"], ["BKN", "OVC"])
            joint["joint"] = (joint["is_fog"] & joint["is_low_cloud"]).astype(int)
            joint_monthly = joint.groupby("month", as_index=False)["joint"].mean()
            if not joint_monthly.empty:
                joint_monthly["JointPct"] = joint_monthly["joint"] * 100.0
                joint_monthly["Month"] = joint_monthly["month"].apply(lambda m: MONTH_NAMES[m - 1])
                joint_monthly["Month"] = pd.Categorical(joint_monthly["Month"], categories=MONTH_NAMES, ordered=True)
                joint_monthly = joint_monthly.sort_values("Month")
                fig_joint = px.bar(
                    joint_monthly,
                    x="Month",
                    y="JointPct",
                    labels={"JointPct": "Obs with Fog and Low Cloud (%)"},
                    title="Fog + Low Cloud Co-occurrence",
                    color_discrete_sequence=["#2159d1"],
                    category_orders={"Month": MONTH_NAMES},
                )
                apply_common_layout(fig_joint)
                fog_figures.append(fig_payload("fog_cloud_joint", fig_joint))
            else:
                add_placeholder("fog_cloud_joint", "Fog + Low Cloud Co-occurrence", "No data available")
        else:
            add_placeholder("fog_share", "Fog Share of Combined Fog/Low Cloud", "No records for selected filters")
            add_placeholder("monthly_fog", "Fog/Low Cloud Frequency", "No records for selected filters")
            add_placeholder("cloud_distribution", "Low Cloud Amount Distribution", "No records for selected filters")
            add_placeholder("fog_cloud_joint", "Fog + Low Cloud Co-occurrence", "No records for selected filters")

        figures.extend(fog_figures[:4])

    elif section == "smoke_dust":
        smoke_df = filtered_df.select(["year", "month", "PRST_WX_PHENOM_1", "PRST_WX_PHENOM_2"]).to_pandas()
        smoke_tokens = ["FU", "DU", "SA", "HZ", "VA"]

        monthly_smoke = monthly_flag_frequency(smoke_df.copy(), smoke_tokens, "SmokeDust")
        if not monthly_smoke.empty:
            fig_smoke = px.bar(
                monthly_smoke,
                x="date",
                y="SmokeDust",
                labels={"SmokeDust": "Observations"},
                title="Monthly Smoke/Dust/Haze Frequency",
            )
            apply_common_layout(fig_smoke)
            figures.append(fig_payload("monthly_smoke", fig_smoke))

        if not smoke_df.empty:
            all_codes = (smoke_df["PRST_WX_PHENOM_1"].fillna("") + " " + smoke_df["PRST_WX_PHENOM_2"].fillna("")).str.upper()
            breakdown = {"FU": 0, "DU": 0, "SA": 0, "HZ": 0, "VA": 0}
            for code in breakdown:
                breakdown[code] = int(all_codes.str.contains(code).sum())
            breakdown_df = pd.DataFrame({"Phenomenon": list(breakdown.keys()), "Count": list(breakdown.values())})
            fig_breakdown = px.pie(breakdown_df, names="Phenomenon", values="Count", title="Phenomenon Type Breakdown")
            apply_common_layout(fig_breakdown)
            figures.append(fig_payload("smoke_breakdown", fig_breakdown))

    metrics = {
        "observations": int(len(filtered_df)),
        "meanSpeed": float(filtered_df["WND_SPD"].mean()) if len(filtered_df) else 0.0,
        "maxGust": float(filtered_df["MAX_WND_GUST_10"].max()) if len(filtered_df) else 0.0,
        "avgTemp": float(filtered_df["AIR_TEMP"].mean()) if len(filtered_df) else 0.0,
    }

    return {"section": section, "figures": figures, "metrics": metrics}
