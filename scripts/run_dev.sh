#!/usr/bin/env bash
set -euo pipefail
export APP_ENV=development
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
