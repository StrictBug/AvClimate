import base64
import json
import math
import os
import re
from functools import lru_cache
from io import BytesIO
from typing import Any

import pandas as pd
import polars as pl
import plotly.express as px
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


def categorize_speed(speed: float) -> str:
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


def fig_payload(fig_id: str, fig: Any) -> dict[str, Any]:
    import base64
    import struct
    
    # Convert figure to dict and decode any binary-encoded arrays
    fig_dict = json.loads(fig.to_json())
    
    # Recursively decode binary data in figure
    def decode_binary_arrays(obj):
        if isinstance(obj, dict):
            if 'dtype' in obj and 'bdata' in obj:
                # Decode Plotly's binary format
                try:
                    dtype = obj['dtype']
                    bdata = base64.b64decode(obj['bdata'])
                    if dtype == 'f8':  # float64
                        count = len(bdata) // 8
                        return list(struct.unpack(f'{count}d', bdata))
                    elif dtype == 'f4':  # float32
                        count = len(bdata) // 4
                        return list(struct.unpack(f'{count}f', bdata))
                except:
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
        fig_rose = px.bar_polar(
            rose_data,
            r="Frequency",
            theta="dir_bin",
            color="Speed Range",
            color_discrete_sequence=px.colors.sequential.Turbo,
            title="Wind Rose",
            category_orders={"Speed Range": ["0-1 kt", "1-5 kt", "5-10 kt", "10-15 kt", "15-22 kt", "22+ kt"]},
        )
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
        ]).to_pandas()
        if not fog_df.empty:
            fog_avg = paired_monthly_frequency(
                fog_df,
                {
                    "Low cloud": {"fields": ["CEIL_CLD_AMT_1", "CEIL_CLD_AMT_2"], "tokens": ["BKN", "OVC"]},
                    "Fog": {"fields": ["PRST_WX_PHENOM_1", "PRST_WX_PHENOM_2"], "tokens": ["FG"]},
                },
            )
            fig_fog = px.bar(
                fog_avg,
                x="Month",
                y="Count",
                color="Type",
                barmode="group",
                color_discrete_map={"Low cloud": "#8b5a2b", "Fog": "#d4af37"},
                labels={"Count": "Avg Obs/Month", "Type": "Category"},
                title="Fog/Low Cloud Frequency",
                category_orders={"Month": MONTH_NAMES, "Type": ["Low cloud", "Fog"]},
            )
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
        fig_rose = px.bar_polar(
            rose_data,
            r="Frequency",
            theta="dir_bin",
            color="Speed Range",
            color_discrete_sequence=px.colors.sequential.Turbo,
            title="Wind Rose",
            category_orders={"Speed Range": ["0-1 kt", "1-5 kt", "5-10 kt", "10-15 kt", "15-22 kt", "22+ kt"]},
        )
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
        apply_common_layout(fig_rose)
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
                monthly_avg_counts = monthly_counts.groupby(["month", "Category"], as_index=False)["Gales"].sum()
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
            labels={"Count": "Total Gale Obs"},
            title="Monthly Gale Frequency by Weather Type",
            category_orders={"Month": MONTH_NAMES, "Category": categories},
            color_discrete_map={"No wx": "#7a7a7a", "SHRA": "#3b82c4", "TS": "#c62828"},
        )
        apply_common_layout(fig_gales)
        figures.append(fig_payload("gale_weather_split", fig_gales))

    elif section == "precipitation":
        precip_df = filtered_df.select([
            "year",
            "month",
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
            rain_only = monthly_flag_frequency(precip_df.copy(), ["RA", "SH", "DZ"], "Rain")
            thunder = monthly_flag_frequency(
                precip_df.copy(),
                ["TS"],
                "Thunderstorm",
                fields=["PRST_WX_DSC_1", "PRST_WX_DSC_2"],
            )
            merged = rain_only[["date", "Rain"]].merge(thunder[["date", "Thunderstorm"]], on="date", how="outer").fillna(0)
            stacked = merged.melt(id_vars="date", value_vars=["Rain", "Thunderstorm"], var_name="Type", value_name="Count")
            fig_split = px.bar(
                stacked,
                x="date",
                y="Count",
                color="Type",
                barmode="group",
                color_discrete_map={"Rain": "#2159d1", "Thunderstorm": "#c62828"},
                title="Monthly Convective vs Rain Split",
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
        ]).to_pandas()

        if not fog_df.empty:
            fog_monthly = paired_monthly_frequency(
                fog_df,
                {
                    "Low cloud": ["BKN", "OVC"],
                    "Fog": ["FG"],
                },
            )
            fig_fog = px.bar(
                fog_monthly,
                x="Month",
                y="Count",
                color="Type",
                barmode="group",
                color_discrete_map={"Low cloud": "#8b5a2b", "Fog": "#d4af37"},
                labels={"Count": "Avg Obs/Month", "Type": "Category"},
                title="Monthly Fog/Low Cloud Frequency",
                category_orders={"Month": MONTH_NAMES, "Type": ["Low cloud", "Fog"]},
            )
            apply_common_layout(fig_fog)
            figures.append(fig_payload("monthly_fog", fig_fog))

            cloud_amounts = pd.concat([fog_df["CEIL_CLD_AMT_1"], fog_df["CEIL_CLD_AMT_2"]], ignore_index=True).dropna()
            cloud_counts = cloud_amounts.value_counts().reset_index()
            cloud_counts.columns = ["Cloud Amount", "Count"]
            fig_cloud = px.bar(cloud_counts, x="Cloud Amount", y="Count", title="Low Cloud Amount Distribution")
            apply_common_layout(fig_cloud)
            figures.append(fig_payload("cloud_distribution", fig_cloud))

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
