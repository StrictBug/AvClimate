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

EXPOSE 7860

CMD ["bash", "scripts/helpers/start_render.sh"]