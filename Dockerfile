FROM python:3.10-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    curl \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && useradd -m -u 1000 user

USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PORT=7860

WORKDIR $HOME/app

COPY --chown=user:user webapp/requirements.txt ./webapp/requirements.txt
RUN pip install --no-cache-dir --user -r webapp/requirements.txt

COPY --chown=user:user . .

RUN bash scripts/helpers/bootstrap_data_from_release.sh \
 && python scripts/helpers/split_fog_wind_by_mode.py \
 && python scripts/helpers/precompute_overview_fog_monthly.py \
 && python scripts/helpers/precompute_overview_rain_thunder_monthly.py \
 && python scripts/helpers/precompute_overview_temp_dewpoint_monthly.py \
 && python scripts/helpers/precompute_overview_wind_rose.py \
 && python scripts/helpers/precompute_y_ceilings.py \
 && python scripts/helpers/precompute_fog_low_cloud.py \
 && python scripts/helpers/split_fog_low_cloud_precomputed.py \
 && python scripts/helpers/precompute_wind_gale_monthly.py \
 && python scripts/helpers/precompute_precipitation.py \
 && python scripts/helpers/precompute_smoke_dust.py

EXPOSE 7860

CMD ["bash", "scripts/helpers/start_render.sh"]