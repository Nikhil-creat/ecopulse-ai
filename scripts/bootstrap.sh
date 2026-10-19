#!/usr/bin/env bash
# One-shot first-run helper:  ./scripts/bootstrap.sh [BASE_URL] [API_KEY]
set -euo pipefail
BASE="${1:-http://localhost}"; KEY="${2:-}"
H=(); [ -n "$KEY" ] && H=(-H "X-API-Key: $KEY")
echo "Waiting for API..."; for i in $(seq 1 60); do
  curl -fs "$BASE/api/v1/health/ready" >/dev/null 2>&1 && break; sleep 3; done
curl -fs "$BASE/api/v1/health/ready"; echo
echo "Seeding knowledge base (first run downloads the embedding model)..."
curl -fs -X POST "${H[@]}" "$BASE/api/v1/knowledge/seed"; echo
echo "Backfilling simulated history (skip with Ctrl-C if you have real data)..."
python3 "$(dirname "$0")/backfill_simulated.py" --base "$BASE" ${KEY:+--api-key "$KEY"}
echo "Training forecasts (via worker)..."
docker compose exec -T celery-worker python -c "from app.workers.tasks import train_forecasts; print(train_forecasts.run())"
echo "Done. Open $BASE"
