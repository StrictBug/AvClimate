import streamlit as st
import polars as pl
import pandas as pd
import plotly.express as px
import math
import os
import base64
from io import BytesIO
from PIL import Image

# --- CONFIGURATION ---
st.set_page_config(
    layout="wide",
    page_title="Aviation climatology",
    page_icon="favicon.svg"
)

# Use absolute paths to avoid directory confusion in Codespaces
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_TILE_CANDIDATES = [
    os.path.join(SCRIPT_DIR, "tiles"),
    os.path.join(SCRIPT_DIR, "map tiles"),
]
TILE_DIR = next((p for p in _TILE_CANDIDATES if os.path.isdir(p)), _TILE_CANDIDATES[0])
ZOOM_LEVEL = 9
COORD_FILE = os.path.join(SCRIPT_DIR, "aerodrome_lat_long.csv")
DATA_FILE = os.path.join(SCRIPT_DIR, "TAF3.parquet")


def inject_avmaps_theme():
    """Apply AvMaps-inspired styling to the Streamlit UI."""
    st.markdown(
        """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;500;600;700&display=swap');

            :root {
                --av-blue: #2159D1;
                --av-blue-light: #3B6ED8;
                --av-text: #333333;
                --av-surface: #ffffff;
                --av-border: #c7d4ef;
            }

            html, body, [class*="css"] {
                font-family: "BP Noname Pro", "Source Sans 3", "Source Sans Pro", "Open Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                color: var(--av-text);
            }

            [data-testid="stAppViewContainer"] {
                background: #e7e7e7;
            }

            [data-testid="stSidebar"] {
                background: #eef3fb;
                border-right: 1px solid #d4e0f5;
            }

            [data-testid="stSidebar"] {
                display: none;
            }

            [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2,
            [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3,
            [data-testid="stSidebar"] label {
                color: #173b88;
                font-weight: 600;
            }


            /* Hide native Streamlit top chrome; we render our own fixed header */
            [data-testid="stHeader"],
            [data-testid="stToolbar"],
            [data-testid="stDecoration"] {
                display: none !important;
            }

            [data-testid="stMainMenu"] {
                visibility: hidden;
            }

            [data-testid="stAppViewContainer"] {
                background: #e7e7e7;
                margin: 0 !important;
                padding: 0 !important;
            }

            /* Zero out ALL the padding Streamlit adds above the first element */
            .main .block-container,
            section[data-testid="stMain"] .block-container,
            [data-testid="stAppViewBlockContainer"],
            div[data-testid="stVerticalBlock"] > div:first-child {
                padding-top: 0 !important;
                margin-top: 0 !important;
            }

            .main .block-container,
            section[data-testid="stMain"] .block-container {
                padding-bottom: 8.8rem;
            }

            /* Spacer placeholder that reserves exactly the height of the fixed topbar (30+30 = 60px) */
            .topbar-host {
                height: 60px;
                line-height: 0;
                margin: 0;
                padding: 0;
                display: block;
            }

            /* Remove markdown wrapper spacing around the topbar placeholder */
            div[data-testid="stVerticalBlock"]:has(.topbar-host) {
                margin: 0 !important;
                padding: 0 !important;
            }

            div[data-testid="stVerticalBlock"]:has(.topbar-host) [data-testid="stMarkdownContainer"] {
                margin: 0 !important;
                padding: 0 !important;
                line-height: 0 !important;
            }

            .app-topbar {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                z-index: 9999;
            }

            .app-topbar-title {
                height: 30px;
                line-height: 30px;
                text-align: center;
                background: #2159D1;
                color: #ffffff;
                font-size: 0.95rem;
                font-weight: 800;
                letter-spacing: 0.3px;
                border-bottom: 1px solid #1a4cb3;
            }

            .app-topbar-nav {
                min-height: 30px;
                padding: 4px 0;
                text-align: center;
                background: #3B6ED8;
                border-top: 1px solid #2d5fc2;
                border-bottom: 1px solid #2d5fc2;
                margin-bottom: 0.2rem;
            }

            .avmaps-subtitle {
                font-size: 0.9rem;
                opacity: 0.95;
                margin-top: 2px;
            }

            [data-testid="stPlotlyChart"] {
                background: #e2e2e2;
                border: 1px solid #bfc5cc;
                border-radius: 4px;
                box-shadow: none;
                padding: 6px 6px 2px;
            }

            [data-testid="metric-container"] {
                background: #ffffff;
                border: 1px solid var(--av-border);
                border-radius: 8px;
                box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
                padding: 8px 10px;
            }

            div.stButton > button,
            div.stDownloadButton > button {
                border-radius: 3px;
                font-weight: 600;
                border: 1px solid #c9c9c9;
                background: #f7f7f7;
                color: #2f3b4f;
            }

            div.stButton > button:hover,
            div.stDownloadButton > button:hover {
                border-color: #4472C4;
                color: #1d3f85;
                background: #f0f6ff;
            }

            .stSlider [data-baseweb="slider"] div[role="slider"] {
                background: var(--av-blue);
                border-color: var(--av-blue);
            }

            .stSlider [data-baseweb="slider"] > div > div {
                background: #bcd0f7;
            }

            .app-topbar-nav .nav-link {
                display: inline-block;
                margin: 0 10px;
                padding: 2px 10px;
                min-height: 24px;
                line-height: 20px;
                font-size: 0.72rem;
                font-weight: 600;
                border: 1px solid #c9c9c9;
                border-radius: 3px;
                background: #f7f7f7;
                color: #2f3b4f;
                text-decoration: none;
            }

            .app-topbar-nav .nav-link:hover {
                border-color: #4472C4;
                color: #1d3f85;
                background: #f0f6ff;
            }

            .app-topbar-nav .nav-link.active {
                background: #4472C4;
                border-color: #2E5BBA;
                color: #ffffff;
                box-shadow: 0 1px 3px rgba(33, 89, 209, 0.32);
            }

            div.stButton {
                margin-top: 0;
                margin-bottom: 0;
            }

            div.stButton > button {
                min-height: 26px;
                padding: 1px 8px;
                font-size: 0.72rem;
                letter-spacing: 0.2px;
                border: 1px solid #c9c9c9;
                background: #f7f7f7;
                color: #2f3b4f;
            }

            div.stButton > button[kind="primary"] {
                background: #4472C4;
                border-color: #2E5BBA;
                color: #ffffff;
                box-shadow: 0 1px 3px rgba(33, 89, 209, 0.32);
            }

            .panel-title {
                margin-top: 0.3rem;
            }

            .bottom-controls-anchor {
                display: none;
            }

            div[data-testid="stVerticalBlock"]:has(.bottom-controls-anchor) {
                position: fixed;
                left: 0;
                right: 0;
                bottom: 0;
                z-index: 1000;
                background: #3B6ED8;
                border-top: 1px solid #2159D1;
                box-shadow: 0 -1px 4px rgba(0, 0, 0, 0.15);
                padding: 8px 14px 10px;
            }

            div[data-testid="stVerticalBlock"]:has(.bottom-controls-anchor) label {
                color: #ffffff;
                font-size: 0.76rem;
                font-weight: 600;
            }

            div[data-testid="stVerticalBlock"]:has(.bottom-controls-anchor) [data-baseweb="select"] > div,
            div[data-testid="stVerticalBlock"]:has(.bottom-controls-anchor) [data-baseweb="slider"] {
                background: #f5f8ff;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

# --- HELPER FUNCTIONS ---

@st.cache_data
def get_data_source():
    """Loads the main TAF climatology dataset."""
    return pl.scan_parquet(DATA_FILE)

@st.cache_data
def load_airport_coords():
    """Loads the ICAO coordinate mapping."""
    return pd.read_csv(COORD_FILE).set_index("ICAO")

def categorize_speed(speed):
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


def get_centered_background(lat, lon, zoom=9, base_dir=TILE_DIR, crop_size=512):
    """
    Stitches a 3x3 grid of tiles and crops it to center on the exact lat/lon.
    Handles coordinate offset for cropped tile sets (e.g., Australia region).
    """
    n = 2.0 ** zoom
    
    # Calculate precise fractional tile positions
    x_frac = (lon + 180.0) / 360.0 * n
    lat_rad = math.radians(lat)
    y_frac = (1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n
    
    # Get the global tile coordinates
    xtile_global = int(x_frac)
    ytile_global = int(y_frac)
    
    # Pixel offset within the central tile
    x_offset = int((x_frac - xtile_global) * 256)
    y_offset = int((y_frac - ytile_global) * 256)
    
    # Build a robust tile index: X folders with their available Y files.
    if not os.path.isdir(base_dir):
        raise FileNotFoundError(f"Tile directory not found: {base_dir}")

    available_x = sorted(
        int(d)
        for d in os.listdir(base_dir)
        if d.isdigit() and os.path.isdir(os.path.join(base_dir, d))
    )
    if not available_x:
        raise RuntimeError(f"No X tile folders found in: {base_dir}")

    y_by_x = {}
    for x in available_x:
        x_dir = os.path.join(base_dir, str(x))
        y_vals = sorted(
            int(fname[:-4])
            for fname in os.listdir(x_dir)
            if fname.endswith(".jpg") and fname[:-4].isdigit()
        )
        if y_vals:
            y_by_x[x] = y_vals

    available_x = sorted(y_by_x.keys())
    if not available_x:
        raise RuntimeError(f"No JPG tile files found in: {base_dir}")

    xtile_center = min(available_x, key=lambda t: abs(t - xtile_global))
    ytile_center = min(y_by_x[xtile_center], key=lambda t: abs(t - ytile_global))
    
    # Create a 3x3 canvas (768x768 pixels)
    canvas = Image.new('RGB', (256 * 3, 256 * 3), (200, 200, 200))
    
    loaded_center = False
    for i, x in enumerate(range(xtile_center - 1, xtile_center + 2)):
        x_clamped = min(available_x, key=lambda t: abs(t - x))
        y_candidates = y_by_x.get(x_clamped, y_by_x[xtile_center])
        for j, y in enumerate(range(ytile_center - 1, ytile_center + 2)):
            y_clamped = min(y_candidates, key=lambda t: abs(t - y))
            
            tile_path = os.path.join(base_dir, str(x_clamped), f"{y_clamped}.jpg")
            
            if os.path.exists(tile_path):
                try:
                    tile = Image.open(tile_path)
                    canvas.paste(tile, (i * 256, j * 256))
                    if i == 1 and j == 1:
                        loaded_center = True
                except Exception:
                    tile = Image.new('RGB', (256, 256), (220, 220, 220))
                    canvas.paste(tile, (i * 256, j * 256))
            else:
                tile = Image.new('RGB', (256, 256), (220, 220, 220))
                canvas.paste(tile, (i * 256, j * 256))

    if not loaded_center:
        raise RuntimeError(
            f"Center tile missing near X={xtile_center}, Y={ytile_center} in {base_dir}"
        )

    left = (256 + x_offset) - (crop_size // 2)
    top = (256 + y_offset) - (crop_size // 2)
    right = left + crop_size
    bottom = top + crop_size
    
    cropped_canvas = canvas.crop((left, top, right, bottom))
    
    # Convert PIL Image to base64-encoded data URL for Plotly
    buffer = BytesIO()
    cropped_canvas.save(buffer, format="PNG")
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.getvalue()).decode()

    return f"data:image/png;base64,{img_base64}"

# --- MAIN APP LOGIC ---





inject_avmaps_theme()

# --- HORIZONTAL NAVIGATION BUTTONS (SECOND BLUE ROW) ---
button_labels = [
    ("overview", "Overview"),
    ("wind", "Wind"),
    ("precipitation", "Precipitation"),
    ("fog_low_cloud", "Fog/Low cloud"),
    ("smoke_dust", "Smoke/Dust"),
]

valid_sections = {k for k, _ in button_labels}
query_section = st.query_params.get("section", "overview")
if isinstance(query_section, list):
    query_section = query_section[0] if query_section else "overview"
if query_section not in valid_sections:
    query_section = "overview"
section = query_section
st.session_state.active_section = section

nav_links = []
for section_key, label in button_labels:
    active_class = "active" if section_key == section else ""
    nav_links.append(f'<a class="nav-link {active_class}" href="?section={section_key}">{label}</a>')

st.markdown(
    f'''
    <div class="topbar-host">
        <div class="app-topbar">
            <div class="app-topbar-title">Aviation Climatology</div>
            <div class="app-topbar-nav">{"".join(nav_links)}</div>
        </div>
    </div>
    ''',
    unsafe_allow_html=True,
)

# --- DATA LOADING (once) ---
source = get_data_source()
coords_df = load_airport_coords()
airport_list = source.select("TARGET_ICAO").unique().sort("TARGET_ICAO").collect().to_series().to_list()

# --- TOP DATA SELECTION BAR ---
with st.container():
    t1, t2, t3, t4 = st.columns([1.5, 1.2, 1.1, 1.1])
    with t1:
        st.selectbox(
            "Aerodrome",
            airport_list,
            key="icao_select",
        )

    with t2:
        st.slider("Year Range", 2000, 2025, value=st.session_state.get("year_range", (2015, 2024)), key="year_range")
    with t3:
        st.slider("Month Range", 1, 12, value=st.session_state.get("month_range", (1, 12)), key="month_range")
    with t4:
        st.slider("Hour (UTC)", 0, 23, value=st.session_state.get("hour_range", (0, 23)), key="hour_range")

# --- FILTER STATE (controls rendered at bottom) ---
if "icao_select" not in st.session_state or st.session_state.icao_select not in airport_list:
    st.session_state.icao_select = "YMML" if "YMML" in airport_list else (airport_list[0] if airport_list else None)

# Ensure all ranges are tuples (start, end)
if "year_range" not in st.session_state or not isinstance(st.session_state.year_range, tuple):
    st.session_state.year_range = (2015, 2024)
if "month_range" not in st.session_state or not isinstance(st.session_state.month_range, tuple):
    st.session_state.month_range = (1, 12)
if "hour_range" not in st.session_state or not isinstance(st.session_state.hour_range, tuple):
    st.session_state.hour_range = (0, 23)

icao = st.session_state.icao_select
year_range = st.session_state.year_range
month_range = st.session_state.month_range
hour_range = st.session_state.hour_range

# --- DATA PROCESSING ---
filtered_df = source.filter(
    (pl.col("TARGET_ICAO") == icao) &
    (pl.col("year").is_between(year_range[0], year_range[1])) &
    (pl.col("month").is_between(month_range[0], month_range[1])) &
    (pl.col("hour").is_between(hour_range[0], hour_range[1]))
).collect()


def contains_any_token(row_values, tokens):
    joined = " ".join(str(v) for v in row_values).upper()
    return any(token in joined for token in tokens)


def monthly_flag_frequency(df, tokens, target_col):
    if df.empty:
        return pd.DataFrame(columns=["year", "month", target_col, "date"])
    df[target_col] = df.apply(
        lambda r: int(contains_any_token([r.get("PRST_WX_PHENOM_1"), r.get("PRST_WX_PHENOM_2")], tokens)),
        axis=1,
    )
    monthly = df.groupby(["year", "month"])[target_col].sum().reset_index()
    monthly["date"] = pd.to_datetime(dict(year=monthly["year"], month=monthly["month"], day=1))
    return monthly


def apply_common_layout(fig):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#333333", family="Source Sans 3, Open Sans, Arial, sans-serif"),
    )



if filtered_df.is_empty():
    st.warning(f"No data found for {icao} with these filters.")
else:
    if section == "overview":
        c1, c2 = st.columns(2)

        with c1:
            st.subheader("Wind Rose")
            wr_df = filtered_df.select(["WND_DIR", "WND_SPD"]).drop_nulls()
            wr_df = wr_df.with_columns(((pl.col("WND_DIR") + 11.25) % 360 // 22.5 * 22.5).alias("dir_bin"))
            rose_data = (
                wr_df.with_columns(
                    pl.col("WND_SPD").map_elements(categorize_speed, return_dtype=pl.Utf8).alias("Speed Range")
                )
                .group_by(["dir_bin", "Speed Range"])
                .agg(pl.len().alias("Frequency"))
                .to_pandas()
            )
            fig_rose = px.bar_polar(
                rose_data, r="Frequency", theta="dir_bin",
                color="Speed Range",
                color_discrete_sequence=px.colors.sequential.Turbo,
                category_orders={"Speed Range": ["0-1 kt", "1-5 kt", "5-10 kt", "10-15 kt", "15-22 kt", "22+ kt"]}
            )
            try:
                airport_lat = coords_df.loc[icao, "LAT"]
                airport_lon = coords_df.loc[icao, "LONG"]
                bg_img_base64 = get_centered_background(airport_lat, airport_lon, zoom=ZOOM_LEVEL, base_dir=TILE_DIR)
                fig_rose.update_layout(
                    images=[dict(
                        source=bg_img_base64,
                        xref="paper", yref="paper", x=0.5, y=0.5,
                        sizex=1.1, sizey=1.1, xanchor="center", yanchor="middle",
                        sizing="contain", layer="below", opacity=0.7,
                    )]
                )
            except Exception as e:
                st.warning(f"Map background unavailable: {e}")
            fig_rose.update_layout(
                legend=dict(bgcolor="rgba(255,255,255,0.88)", bordercolor="#c7d4ef", borderwidth=1),
                polar=dict(bgcolor="rgba(0,0,0,0)", angularaxis=dict(direction="clockwise", period=360)),
            )
            apply_common_layout(fig_rose)
            st.plotly_chart(fig_rose, width="stretch")

        with c2:
            st.subheader("Monthly Temperature & Dewpoint")
            temp_df = filtered_df.select(["year", "month", "AIR_TEMP", "DWPT"]).to_pandas()
            if not temp_df.empty:
                monthly = temp_df.groupby(["year", "month"]).agg({"AIR_TEMP": ["max", "min"], "DWPT": ["max", "min"]})
                monthly.columns = ["Max T", "Min T", "Max Td", "Min Td"]
                monthly = monthly.reset_index()
                monthly["date"] = pd.to_datetime(dict(year=monthly["year"], month=monthly["month"], day=1))
                fig_temp = px.line(monthly, x="date", y=["Max T", "Min T", "Max Td", "Min Td"], labels={"value": "°C", "variable": ""}, markers=True)
                apply_common_layout(fig_temp)
                st.plotly_chart(fig_temp, width="stretch")
            else:
                st.info("No temperature data available for this selection.")

        c3, c4 = st.columns(2)
        with c3:
            st.subheader("Monthly Rain/Thunderstorm Frequency")
            rain_df = filtered_df.select(["year", "month", "PRST_WX_PHENOM_1", "PRST_WX_PHENOM_2"]).to_pandas()
            rain_monthly = monthly_flag_frequency(rain_df, ["RA", "TS"], "Rain/TS")
            if not rain_monthly.empty:
                fig_rain = px.bar(rain_monthly, x="date", y="Rain/TS", labels={"Rain/TS": "Rain/TS Obs"})
                apply_common_layout(fig_rain)
                st.plotly_chart(fig_rain, width="stretch")
            else:
                st.info("No rain/thunderstorm data available for this selection.")

        with c4:
            st.subheader("Monthly Fog/Low Cloud Frequency")
            fog_df = filtered_df.select(["year", "month", "PRST_WX_PHENOM_1", "PRST_WX_PHENOM_2", "CEIL_CLD_AMT_1", "CEIL_CLD_AMT_2"]).to_pandas()
            if not fog_df.empty:
                fog_df["Fog/LowCloud"] = fog_df.apply(
                    lambda r: int(
                        contains_any_token([r.get("PRST_WX_PHENOM_1"), r.get("PRST_WX_PHENOM_2")], ["FG"]) or
                        str(r.get("CEIL_CLD_AMT_1", "")).startswith(("BKN", "OVC")) or
                        str(r.get("CEIL_CLD_AMT_2", "")).startswith(("BKN", "OVC"))
                    ),
                    axis=1,
                )
                fog_monthly = fog_df.groupby(["year", "month"])["Fog/LowCloud"].sum().reset_index()
                fog_monthly["date"] = pd.to_datetime(dict(year=fog_monthly["year"], month=fog_monthly["month"], day=1))
                fig_fog = px.bar(fog_monthly, x="date", y="Fog/LowCloud", labels={"Fog/LowCloud": "Fog/Low Cloud Obs"})
                apply_common_layout(fig_fog)
                st.plotly_chart(fig_fog, width="stretch")
            else:
                st.info("No fog/low cloud data available for this selection.")

    elif section == "wind":
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Wind Direction Frequency")
            wind_df = filtered_df.select(["WND_DIR"]).drop_nulls().with_columns(
                ((pl.col("WND_DIR") + 11.25) % 360 // 22.5 * 22.5).alias("dir_bin")
            )
            dir_counts = wind_df.group_by("dir_bin").agg(pl.len().alias("Frequency")).sort("dir_bin").to_pandas()
            fig_dir = px.bar_polar(dir_counts, r="Frequency", theta="dir_bin", color="Frequency", color_continuous_scale="Blues")
            apply_common_layout(fig_dir)
            st.plotly_chart(fig_dir, width="stretch")
        with c2:
            st.subheader("Monthly Wind Speed and Gust")
            ws_df = filtered_df.select(["year", "month", "WND_SPD", "MAX_WND_GUST_10"]).to_pandas()
            monthly_ws = ws_df.groupby(["year", "month"]).agg({"WND_SPD": "mean", "MAX_WND_GUST_10": "max"}).reset_index()
            monthly_ws["date"] = pd.to_datetime(dict(year=monthly_ws["year"], month=monthly_ws["month"], day=1))
            fig_ws = px.line(monthly_ws, x="date", y=["WND_SPD", "MAX_WND_GUST_10"], markers=True, labels={"value": "kt", "variable": ""})
            apply_common_layout(fig_ws)
            st.plotly_chart(fig_ws, width="stretch")

    elif section == "precipitation":
        c1, c2 = st.columns(2)
        precip_df = filtered_df.select(["year", "month", "PRST_WX_PHENOM_1", "PRST_WX_PHENOM_2"]).to_pandas()
        with c1:
            st.subheader("Monthly Rain/Thunderstorm Frequency")
            monthly_precip = monthly_flag_frequency(precip_df.copy(), ["RA", "TS"], "Precip")
            if not monthly_precip.empty:
                fig_precip = px.bar(monthly_precip, x="date", y="Precip", labels={"Precip": "Observations"})
                apply_common_layout(fig_precip)
                st.plotly_chart(fig_precip, width="stretch")
            else:
                st.info("No precipitation data available for this selection.")
        with c2:
            st.subheader("Monthly Convective vs Rain Split")
            if not precip_df.empty:
                rain_only = monthly_flag_frequency(precip_df.copy(), ["RA", "SH", "DZ"], "Rain")
                thunder = monthly_flag_frequency(precip_df.copy(), ["TS"], "Thunderstorm")
                merged = rain_only[["date", "Rain"]].merge(thunder[["date", "Thunderstorm"]], on="date", how="outer").fillna(0)
                stacked = merged.melt(id_vars="date", value_vars=["Rain", "Thunderstorm"], var_name="Type", value_name="Count")
                fig_split = px.bar(stacked, x="date", y="Count", color="Type")
                apply_common_layout(fig_split)
                st.plotly_chart(fig_split, width="stretch")
            else:
                st.info("No precipitation type data available for this selection.")

    elif section == "fog_low_cloud":
        c1, c2 = st.columns(2)
        fog_df = filtered_df.select(["year", "month", "PRST_WX_PHENOM_1", "PRST_WX_PHENOM_2", "CEIL_CLD_AMT_1", "CEIL_CLD_AMT_2"]).to_pandas()
        with c1:
            st.subheader("Monthly Fog/Low Cloud Frequency")
            if not fog_df.empty:
                fog_df["Fog/LowCloud"] = fog_df.apply(
                    lambda r: int(
                        contains_any_token([r.get("PRST_WX_PHENOM_1"), r.get("PRST_WX_PHENOM_2")], ["FG", "BR"]) or
                        str(r.get("CEIL_CLD_AMT_1", "")).startswith(("BKN", "OVC")) or
                        str(r.get("CEIL_CLD_AMT_2", "")).startswith(("BKN", "OVC"))
                    ),
                    axis=1,
                )
                fog_monthly = fog_df.groupby(["year", "month"])["Fog/LowCloud"].sum().reset_index()
                fog_monthly["date"] = pd.to_datetime(dict(year=fog_monthly["year"], month=fog_monthly["month"], day=1))
                fig_fog = px.bar(fog_monthly, x="date", y="Fog/LowCloud", labels={"Fog/LowCloud": "Observations"})
                apply_common_layout(fig_fog)
                st.plotly_chart(fig_fog, width="stretch")
            else:
                st.info("No fog/low cloud data available for this selection.")
        with c2:
            st.subheader("Low Cloud Amount Distribution")
            if not fog_df.empty:
                cloud_amounts = pd.concat([fog_df["CEIL_CLD_AMT_1"], fog_df["CEIL_CLD_AMT_2"]], ignore_index=True).dropna()
                cloud_counts = cloud_amounts.value_counts().reset_index()
                cloud_counts.columns = ["Cloud Amount", "Count"]
                fig_cloud = px.bar(cloud_counts, x="Cloud Amount", y="Count")
                apply_common_layout(fig_cloud)
                st.plotly_chart(fig_cloud, width="stretch")
            else:
                st.info("No cloud amount data available for this selection.")

    elif section == "smoke_dust":
        c1, c2 = st.columns(2)
        smoke_df = filtered_df.select(["year", "month", "PRST_WX_PHENOM_1", "PRST_WX_PHENOM_2"]).to_pandas()
        smoke_tokens = ["FU", "DU", "SA", "HZ", "VA"]
        with c1:
            st.subheader("Monthly Smoke/Dust/Haze Frequency")
            monthly_smoke = monthly_flag_frequency(smoke_df.copy(), smoke_tokens, "SmokeDust")
            if not monthly_smoke.empty:
                fig_smoke = px.bar(monthly_smoke, x="date", y="SmokeDust", labels={"SmokeDust": "Observations"})
                apply_common_layout(fig_smoke)
                st.plotly_chart(fig_smoke, width="stretch")
            else:
                st.info("No smoke/dust data available for this selection.")
        with c2:
            st.subheader("Phenomenon Type Breakdown")
            if not smoke_df.empty:
                all_codes = (smoke_df["PRST_WX_PHENOM_1"].fillna("") + " " + smoke_df["PRST_WX_PHENOM_2"].fillna("")).str.upper()
                breakdown = {"FU": 0, "DU": 0, "SA": 0, "HZ": 0, "VA": 0}
                for code in breakdown:
                    breakdown[code] = int(all_codes.str.contains(code).sum())
                breakdown_df = pd.DataFrame({"Phenomenon": list(breakdown.keys()), "Count": list(breakdown.values())})
                fig_breakdown = px.pie(breakdown_df, names="Phenomenon", values="Count")
                apply_common_layout(fig_breakdown)
                st.plotly_chart(fig_breakdown, width="stretch")
            else:
                st.info("No smoke/dust breakdown data available for this selection.")

    # --- SUMMARY METRICS ---
    st.divider()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Observations", f"{len(filtered_df):,}")
    m2.metric("Mean Speed", f"{filtered_df['WND_SPD'].mean():.1f} kt")
    m3.metric("Max Gust", f"{filtered_df['MAX_WND_GUST_10'].max():.1f} kt")
    m4.metric("Avg Temp", f"{filtered_df['AIR_TEMP'].mean():.1f} C")

