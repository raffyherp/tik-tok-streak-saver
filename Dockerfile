FROM python:3.12-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir . \
    && playwright install --with-deps chromium

# Click/Typer stores the app state under $XDG_DATA_HOME/streak_saver.
# Coolify mounts /data so configuration and TikTok cookies survive redeploys.
ENV XDG_DATA_HOME=/data

# Coolify Scheduled Tasks runs `streak-saver send_messages` in this container.
CMD ["sleep", "infinity"]
