FROM python:3.12-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir . \
    && playwright install --with-deps chromium

# Click/Typer stores the app state under $XDG_DATA_HOME/streak_saver.
# Coolify mounts /data so configuration and TikTok cookies survive redeploys.
ENV XDG_DATA_HOME=/data

EXPOSE 8000

CMD ["uvicorn", "streak_saver.web:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
