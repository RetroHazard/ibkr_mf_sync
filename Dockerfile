FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Install cron
RUN apt-get update && apt-get install -y --no-install-recommends cron \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Chromium browser (only what we need)
RUN playwright install chromium

# Copy application code
COPY *.py ./

# Create persistent data directories
RUN mkdir -p /app/session /app/.cache

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
