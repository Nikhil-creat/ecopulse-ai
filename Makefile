migrate: ; docker compose exec -T postgres-timescaledb-vector psql -U $${POSTGRES_USER:-ecopulse} -d $${POSTGRES_DB:-ecopulse} < infra/db/init/03_users.sql
mlflow:        ; docker compose --profile mlops up -d mlflow
# Optional stacks
observability: ; docker compose --profile observability up -d prometheus grafana
mcp:           ; docker compose --profile mcp up -d --build mcp-server
.PHONY: mlflow migrate observability mcp up down logs bootstrap test ps psql
up:        ; docker compose up --build -d
down:      ; docker compose down
logs:      ; docker compose logs -f --tail=100
ps:        ; docker compose ps
bootstrap: ; ./scripts/bootstrap.sh
test:      ; cd backend && pip install -q -r requirements-dev.txt && pytest -q
psql:      ; docker compose exec postgres-timescaledb-vector psql -U $${POSTGRES_USER:-ecopulse} -d $${POSTGRES_DB:-ecopulse}
