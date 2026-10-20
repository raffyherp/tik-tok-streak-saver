FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./

RUN pip install --no-cache-dir \
        "fastapi>=0.115.0" \
        "jinja2>=3.1.4" \
        "playwright>=1.58.0" \
        "typer>=0.24.1" \
        "pyautostart>=0.1.2" \
        "rich>=13.9.0" \
        "uvicorn[standard]>=0.34.0" \
    && playwright install --with-deps chromium

COPY . .

RUN pip install --no-cache-dir --no-deps .

# Click/Typer stores the app state under $XDG_DATA_HOME/streak_saver.
# Coolify mounts /data so configuration and TikTok cookies survive redeploys.
ENV XDG_DATA_HOME=/data
ENV STREAK_SAVER_DATA_DIR=/data/streak_saver

EXPOSE 8000

CMD ["uvicorn", "streak_saver.web:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
