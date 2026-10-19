# Optional stacks
observability: ; docker compose --profile observability up -d prometheus grafana
mcp:           ; docker compose --profile mcp up -d --build mcp-server
.PHONY: observability mcp up down logs bootstrap test ps psql
up:        ; docker compose up --build -d
down:      ; docker compose down
logs:      ; docker compose logs -f --tail=100
ps:        ; docker compose ps
bootstrap: ; ./scripts/bootstrap.sh
test:      ; cd backend && pip install -q -r requirements-dev.txt && pytest -q
psql:      ; docker compose exec postgres-timescaledb-vector psql -U $${POSTGRES_USER:-ecopulse} -d $${POSTGRES_DB:-ecopulse}
