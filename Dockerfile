# Base image for Python applications
FROM python:3.9-slim-buster AS base

WORKDIR /app

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libnss3 \
    libfontconfig1 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libgdk-pixbuf2.0-0 \
    libgtk-3-0 \
    libxkbcommon-x11-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm-dev \
    libasound2 \
    libdbus-1-3 \
    libdrm-dev \
    libegl1 \
    libepoxy0 \
    libevdev2 \
    libffi-dev \
    libgirepository-1.0-1 \
    libgl1 \
    libgles2 \
    libinput-dev \
    libjpeg-dev \
    libmount-dev \
    libopengl0 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libpng-dev \
    libudev-dev \
    libwayland-client0 \
    libwayland-cursor0 \
    libwayland-egl1 \
    libwayland-server0 \
    libwebp-dev \
    libx11-xcb1 \
    libxcb-dri3-0 \
    libxcb-render0 \
    libxcb-shm0 \
    libxcb-sync1 \
    libxcursor1 \
    libxext6 \
    libxi6 \
    libxinerama1 \
    libxkbcommon0 \
    libxrandr2 \
    libxrender1 \
    libxshmfence6 \
    libxtst6 \
    mesa-common-dev \
    udev \
    xkb-data \
    fonts-liberation \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
# This step is crucial for Playwright to function inside the container
RUN playwright install --with-deps chromium

# --- Stage for Mock Social Server ---
FROM base AS mock_social_server

COPY src/mock_social_server.py /app/src/mock_social_server.py
COPY src/models.py /app/src/models.py # Mock server uses Pydantic models

EXPOSE 8080

CMD ["uvicorn", "src.mock_social_server:app", "--host", "0.0.0.0", "--port", "8080"]

# --- Stage for Agent Service ---
FROM base AS agent_service

COPY src /app/src
COPY evaluate.py /app/evaluate.py
COPY tests /app/tests

# Create necessary directories if they don't exist
RUN mkdir -p /app/data /app/results

# Ensure data files exist, even if empty, for initial setup
RUN touch /app/data/posted_ids.json \
    /app/data/browser_state.json \
    /app/data/traces.jsonl

# Default command is set in docker-compose.yml
# CMD ["python", "src/agent.py"]
