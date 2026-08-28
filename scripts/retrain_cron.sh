#!/usr/bin/env bash
# Run nightly via cron/systemd timer for every active business.
set -euo pipefail
source .venv/bin/activate
export APP_ENV=production

for business in $(psql "$POSTGRES_URL" -tAc "SELECT business_id FROM businesses WHERE active"); do
  echo "Checking $business..."
  python -m app.training.live_feedback.retrain_trigger "$business"
done
