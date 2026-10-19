migrate: ; docker compose exec -T postgres-timescaledb-vector psql -U $${POSTGRES_USER:-ecopulse} -d $${POSTGRES_DB:-ecopulse} < infra/db/init/03_users.sql
mlflow:        ; docker compose --profile mlops up -d mlflow
streaming:     ; docker compose --profile streaming up -d redpanda stream-consumer
loadtest:      ; docker run --rm -i --network host -e BASE=$${BASE:-http://localhost} -e API_KEY=$${API_KEY:-} grafana/k6 run - < loadtest/k6-api.js
helm-lint:     ; helm lint deploy/helm/ecopulse && helm template ecopulse deploy/helm/ecopulse >/dev/null
# Optional stacks
observability: ; docker compose --profile observability up -d prometheus grafana
mcp:           ; docker compose --profile mcp up -d --build mcp-server
.PHONY: streaming loadtest helm-lint mlflow migrate observability mcp up down logs bootstrap test ps psql
up:        ; docker compose up --build -d
down:      ; docker compose down
logs:      ; docker compose logs -f --tail=100
ps:        ; docker compose ps
bootstrap: ; ./scripts/bootstrap.sh
test:      ; cd backend && pip install -q -r requirements-dev.txt && pytest -q
psql:      ; docker compose exec postgres-timescaledb-vector psql -U $${POSTGRES_USER:-ecopulse} -d $${POSTGRES_DB:-ecopulse}
