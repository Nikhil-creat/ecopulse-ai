# EcoPulse AI - Phase 1

Containerized infrastructure + TimescaleDB/Pgvector schema.

## Run
```bash
cp .env.example .env     # set POSTGRES_PASSWORD and SECRET_KEY
docker compose up --build
```
- App: http://localhost
- API docs: http://localhost/docs
- Readiness: http://localhost/api/v1/health/ready (shows timescaledb + vector extensions)

## Notes
- Schema is created once from `infra/db/init/*.sql`. To re-run after changes:
  `docker compose down -v` (wipes data) then `up --build`.
- ORM models in `backend/app/models` mirror the SQL schema.
- Phase 2 adds ingestion, CNN module, drift monitor.

## Phase 2 - ingestion, CNN, drift
- `POST /api/v1/ingest/readings` - validated batch upsert; `POST /api/v1/ingest/fetch` - poll providers now
- Celery beat: fetch every 15 min (OpenWeatherMap / CPCB; **simulated data if no keys set**), drift check hourly
- `POST /api/v1/satellite/analyze` (multipart: file, region, image_type) -> queued CNN job; `GET /api/v1/satellite/latest`
- `GET /api/v1/mlops/drift`, `POST /api/v1/mlops/drift/run`
- CNN runs heuristic scoring until weights exist: `docker compose exec celery-worker python -m app.ml.train_spatial_cnn --images <dir>`
- Set `STATIONS_JSON` in `.env` with exact coordinates for your stations.

## Phase 3 - RAG + agents
1. `POST /api/v1/knowledge/seed` (first run downloads the MiniLM model) - loads WHO/CPCB/advisory/playbook docs
2. `GET /api/v1/knowledge/search?q=asthma outdoor exercise` - hybrid (vector + full-text, RRF) retrieval
3. `POST /api/v1/agents/run {"city":"Warangal"}` - Integrity -> Risk -> Policy graph
- Works without LLM keys (deterministic + templated text); with `GROQ_API_KEY` / `GEMINI_API_KEY` the narratives are LLM-written.
- Until forecasters are trained, forecasts come from a labelled `baseline-damped-trend` fallback.
- Add official PDFs: `POST /api/v1/knowledge/upload` (file, source, doc_type).

## Phase 4 - REST, WebSocket, SSE chat, PDF
- `GET /api/v1/stats/summary?city=`, `/stats/timeseries?station_id=&field=pm25&hours=48`, `/forecasts?station_id=`
- `GET /api/v1/reports/executive?city=Warangal` -> PDF (runs the agent pipeline)
- `ws://localhost/ws/live-metrics?city=Warangal` -> snapshot, then pushes on every ingest (Redis pub/sub)
- `POST /api/v1/chat {"message": "...", "city": "...", "session_id": "..."}` -> SSE (`meta`, `token`, `done`)
  - `curl -N -X POST localhost/api/v1/chat -H 'content-type: application/json' -d '{"message":"Safe to exercise outside? I have asthma","city":"Warangal"}'`
- No authentication yet (added before any public deployment).

## Phase 5 - Dashboard (http://localhost)
- Live AQI gauge + pollutant cards (WebSocket), 48h history + forecast chart, 3D deck.gl map (station columns + CNN grid), floating streaming chat drawer, one-click PDF report.
- Quick start: `POST /api/v1/ingest/fetch` -> open http://localhost -> `POST /api/v1/knowledge/seed` for chat/report citations.
- Map has no basemap tiles (works offline); CNN grid is centred on the stations because uploads carry no georeference.

## Hardening & ops (final pass)
- Real forecaster: Holt-Winters / damped-trend / seasonal-naive chosen on a 24 h hold-out, retrained every 3 h and on drift
- API-key auth on ingest/knowledge/drift-run (`X-API-Key`), per-IP rate limits on chat, reports, agents, satellite upload
- `make bootstrap`, `make test`, CI workflow, `docs/DEPLOY.md`
