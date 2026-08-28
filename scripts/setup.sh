#!/usr/bin/env bash
set -euo pipefail

echo "== Voice Agent VPS (Vapi) setup =="
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

echo "-- Pulling Ollama models (requires Ollama installed) --"
ollama pull llama3:8b || true
ollama pull nomic-embed-text || true

echo "-- Running DB migrations --"
psql "$POSTGRES_URL" -f db/migrations/001_init.sql

echo "-- Seeding example businesses --"
python -m db.seed.seed_business

echo "Setup complete."
echo "Next: cp .env.example .env, fill in VAPI_API_KEY, VAPI_SERVER_SECRET, PUBLIC_BASE_URL,"
echo "put this server behind TLS, then for each business run:"
echo "  python -m app.vapi.provision --business <business_id> --attach-number +1... --twilio-sid ... --twilio-token ..."
