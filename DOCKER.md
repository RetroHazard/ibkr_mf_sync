# Docker Deployment Guide

Self-hosting guide for running IBKR MF Syncer on a NAS via Docker and Portainer.

---

## Dependency Management

Python dependencies are managed as two files:

- **`requirements.txt`** — direct dependencies only. This is the file you edit when adding or upgrading a package.
- **`requirements.lock`** — the full pinned dependency tree with SHA256 hashes for every package, generated from `requirements.txt`. This is what the Docker image installs from (`pip install --require-hashes`), ensuring no package can be silently swapped for a malicious version.

### Regenerating the lock file

Run this whenever you change `requirements.txt`. The command runs inside a Linux container to guarantee the hashes match the target platform:

```bash
MSYS_NO_PATHCONV=1 docker run --rm \
  -v "$(pwd -W):/app" \
  -w /app \
  python:3.11-slim \
  bash -c "pip install pip-tools --quiet && pip-compile --generate-hashes --output-file=requirements.lock requirements.txt"
```

Commit both `requirements.txt` and `requirements.lock` together. The next merge to `main` will rebuild the Docker image with the updated lock file.

---

## Release Pipeline

Every merge to `main` automatically builds a new Docker image and pushes it to **GitHub Container Registry (GHCR)** via GitHub Actions (`.github/workflows/docker-release.yml`).

The workflow triggers only when files that affect the image change (Python source, `requirements.txt`, `Dockerfile`, `docker/`). Documentation-only changes do not trigger a build.

### Image location

```
ghcr.io/retrohazard/ibkr_mf_sync:latest
```

Two tags are published on each build:
- `latest` — always points to the most recent build from `main`
- `sha-<commit>` — pinned to a specific commit for rollback

### Pulling the latest image on Portainer

In Portainer, go to **Stacks → ibkr-mf-sync → Editor**, then click **Pull and redeploy**. The NAS fetches the new image from GHCR and restarts the container with zero downtime.

### Automatic redeployment via Watchtower

The `docker-compose.yml` includes a **Watchtower** service that runs alongside the sync container on your NAS. Watchtower polls GHCR on a schedule and automatically pulls and restarts the container whenever a new image is published — no inbound network access or webhooks required.

By default it checks every 6 hours. Override with `WATCHTOWER_POLL_INTERVAL` (in seconds) in your `.env` file:

```ini
WATCHTOWER_POLL_INTERVAL=3600  # check hourly
```

Watchtower is scoped to only manage containers that carry the `com.centurylinklabs.watchtower.enable=true` label, so it will not touch other containers running on your NAS.

**Prerequisite — make the GHCR package public:**

The image contains no secrets (credentials are injected at runtime via env vars), so it can be made public. This lets Watchtower and Portainer pull it without any credentials:

1. Go to `https://github.com/users/RetroHazard/packages/container/ibkr_mf_sync`
2. Click **Package settings → Change visibility → Public**

This only needs to be done once, after the Actions workflow publishes the image for the first time.

---

## Deployment (NAS / Portainer)

The recommended way to run this on a schedule from a NAS (Synology, QNAP, etc.) is via Docker with Portainer. The container runs a cron daemon internally, so no external scheduler is required.

### Prerequisites

- Docker and Portainer installed on your NAS
- The project files cloned locally on a machine where you can run Python + Playwright for the initial session setup

> **Architecture note**: The official Playwright base image (`mcr.microsoft.com/playwright/python`) ships binaries for `linux/amd64` only. If your NAS uses an ARM CPU (e.g., Synology with an ARM SoC), you will need to build the image locally on an ARM machine or use a cross-compilation approach (`docker buildx`). Most Intel/AMD NAS devices work without modification.

---

### Step 1 — Seed the browser session locally

The container runs entirely headless. MoneyForward requires an email 2FA code on first login, which cannot be completed without a browser window. You must complete this once on your local machine to generate a saved session file that the container reuses on every subsequent run.

```bash
# Install dependencies locally (skip if already done)
pip install -r requirements.txt
playwright install chromium

# Run once — a browser window will open for 2FA
python main.py
```

After a successful run, `.browser_session.json` is created in the project directory. This file contains your MoneyForward login cookies and allows the container to skip 2FA on future runs.

> **Keep this file private.** It provides authenticated access to your MoneyForward account. It is already listed in `.gitignore`.

---

### Step 2 — Configure environment variables

Copy `.env.template` to `.env` and fill in your credentials:

```bash
cp .env.template .env
```

```ini
MF_EMAIL=your_email@example.com
MF_PASSWORD=your_password
MF_IB_INSTITUTION_URL=https://moneyforward.com/accounts/show_manual/YOUR_INSTITUTION_ID

IBKR_FLEX_TOKEN=your_token
IBKR_FLEX_QUERY_ID=your_query_id

# Cron schedule (default: 6am daily)
CRON_SCHEDULE=0 6 * * *

# Set to true to run once immediately when the container starts
RUN_ON_START=false
```

**Never commit `.env` to version control.**

---

### Step 3 — Deploy in Portainer

The pre-built image is published to GHCR automatically on every merge to `main` — no local Docker build is required.

1. In Portainer, go to **Stacks → Add Stack**
2. Paste the contents of `docker-compose.yml` into the Web editor
3. Under **Environment variables**, add each key from your `.env` file (or use the "Load variables from .env file" option if available)
4. Click **Deploy the stack** — Portainer pulls `ghcr.io/retrohazard/ibkr_mf_sync:latest` from GHCR automatically

The stack creates two named Docker volumes automatically:
- `ibkr-mf-sync_ibkr-session` — stores the MoneyForward login session
- `ibkr-mf-sync_ibkr-cache` — stores IBKR Flex Query response cache (avoids redundant API calls within a 4-hour window)

---

### Step 4 — Copy the session file into the volume

After the stack is deployed and the container is running, copy your locally-generated session into the volume:

```bash
# From the machine where you ran main.py locally
docker run --rm \
  -v ibkr-mf-sync_ibkr-session:/session \
  -v "$(pwd)":/src \
  alpine cp /src/.browser_session.json /session/.browser_session.json
```

If you're on the NAS itself and the session file is already there, reference it directly:

```bash
docker run --rm \
  -v ibkr-mf-sync_ibkr-session:/session \
  alpine sh -c "ls -lh /session"
```

You should see `.browser_session.json` listed. The container will load it automatically on its next run.

---

### Scheduling

The schedule is controlled by the `CRON_SCHEDULE` environment variable using standard cron syntax. The default is `0 6 * * *` (6:00 AM daily, container local time).

| Example | Meaning |
|---------|---------|
| `0 6 * * *` | 6:00 AM every day |
| `0 8 * * 1-5` | 8:00 AM weekdays only |
| `0 6,18 * * *` | 6:00 AM and 6:00 PM daily |
| `0 */4 * * *` | Every 4 hours |

To apply a schedule change, update the environment variable in Portainer and re-deploy the stack.

To trigger an immediate run without waiting for the next scheduled time, set `RUN_ON_START=true` and re-deploy (then set it back to `false`).

---

### Monitoring

View live logs in Portainer under **Containers → ibkr-mf-sync → Logs**, or from the CLI:

```bash
docker logs ibkr-mf-sync -f
```

Logs are retained in JSON format with a 10 MB cap and 3 file rotation (configured in `docker-compose.yml`).

---

### Handling 2FA in the container

Browser sessions last a long time, but MoneyForward may occasionally require re-verification (e.g., after a session timeout or suspicious login detection). When this happens the container **does not crash** — it pauses the sync and waits for you to provide the OTP code.

**What you will see in the logs:**

```
WARNING ============================================================
WARNING 2FA REQUIRED — OPERATOR ACTION NEEDED
WARNING Provide the OTP code using one of:
WARNING   docker exec ibkr-mf-sync sh -c 'echo YOUR_CODE > /app/session/2fa_input'
WARNING   Portainer console: echo YOUR_CODE > /app/session/2fa_input
WARNING Waiting up to 10 minutes...
WARNING ============================================================
```

**How to respond:**

Check your MoneyForward account email for the OTP code, then deliver it to the container using any of these methods:

**Option A — Portainer console**
1. Go to **Containers → ibkr-mf-sync → Console**
2. Connect using `/bin/sh`
3. Run: `echo 123456 > /app/session/2fa_input`

**Option B — SSH into the NAS**
```bash
docker exec ibkr-mf-sync sh -c 'echo 123456 > /app/session/2fa_input'
```

The script detects the file within 5 seconds, submits the code to the MoneyForward form automatically, and continues the sync. If no code is provided within 10 minutes, the run times out and will be retried at the next scheduled time.

You can also detect the 2FA wait state programmatically — while waiting, the container creates `/app/session/2fa_required` containing an ISO timestamp. This can be used to trigger notifications (webhook, email, etc.) in a companion script.

---

### Session expiry

Sessions typically last several months. If the session expires, the next scheduled run will trigger the 2FA flow described above. After successfully completing 2FA in the container, the session file is automatically refreshed and saved — future runs will not need 2FA again until the next expiry.

If you prefer to refresh the session proactively, repeat [Step 1](#step-1--seed-the-browser-session-locally) locally and re-copy the file using the command in [Step 4](#step-4--copy-the-session-file-into-the-volume).

---

### Troubleshooting

**Container exits immediately**
Check the logs: `docker logs ibkr-mf-sync`. The most common cause is a missing or incorrect environment variable.

**`2FA required` loop on every run**
The session file is not being persisted. Verify the `ibkr-session` volume is mounted correctly and that the session file exists inside it:
```bash
docker run --rm -v ibkr-mf-sync_ibkr-session:/s alpine ls -lh /s
```

**`playwright install` errors during build**
Ensure you have a stable internet connection during `docker build`. The Chromium download is ~200 MB.

**NAS ARM architecture error**
If you see `exec format error` or `no matching manifest`, your NAS CPU is ARM-based. Build the image on an ARM machine, or use `docker buildx build --platform linux/arm64 -t ibkr-mf-sync:latest .` and push to a local registry.

**IBKR Flex Token expired**
The token has a 1-year validity. Regenerate it in your IBKR account portal (Flex Web Service settings) and update the `IBKR_FLEX_TOKEN` environment variable in Portainer.
