#!/bin/bash
set -e

# Export container environment to /etc/environment so cron jobs inherit it.
# Cron runs with a stripped shell that doesn't inherit Docker env vars by default.
printenv | grep -v "^_=" > /etc/environment

CRON_SCHEDULE="${CRON_SCHEDULE:-0 6 * * *}"

# Write crontab entry - pipe output to Docker's stdout so `docker logs` shows it
cat > /etc/cron.d/ibkr-sync << EOF
$CRON_SCHEDULE root cd /app && python main.py >> /proc/1/fd/1 2>&1
EOF
chmod 0644 /etc/cron.d/ibkr-sync

# cron requires a trailing newline
echo "" >> /etc/cron.d/ibkr-sync

# Run once immediately on container start if requested
if [ "${RUN_ON_START:-false}" = "true" ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] RUN_ON_START=true — running sync now..."
    python /app/main.py
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Cron started with schedule: $CRON_SCHEDULE"
exec cron -f
