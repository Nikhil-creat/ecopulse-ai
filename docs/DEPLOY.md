# EcoPulse AI - deployment checklist

Run on any Linux host with Docker + Compose (a small cloud VM works; 4 GB RAM minimum because of PyTorch and the embedding model; 8 GB is comfortable).

## Before first start
- [ ] `cp .env.example .env`; set a strong `POSTGRES_PASSWORD`, `SECRET_KEY`, and `API_KEYS` (generate with `python3 -c "import secrets;print(secrets.token_urlsafe(32))"`)
- [ ] Set `CORS_ORIGINS` to your real domain(s)
- [ ] Add real stations in `STATIONS_JSON` (exact lat/lon, e.g. Thorrur) and `OPENWEATHER_API_KEY` / `CPCB_API_KEY`
- [ ] Optional: `GROQ_API_KEY`, `GEMINI_API_KEY` for LLM-written narratives

## HTTPS
Only Nginx publishes a port. Put TLS in front: easiest is a host-level Caddy/Traefik/Cloudflare proxy forwarding to port 80,
or add certbot to the nginx service. The rate limiter keys on the last proxy's `X-Forwarded-For`; behind another proxy configure
that proxy to pass the real client IP.

## After start
1. `./scripts/bootstrap.sh http://YOUR_HOST YOUR_API_KEY` (seeds knowledge, backfills simulated history, trains forecasts)
2. Verify: `/api/v1/health/ready` shows `timescaledb,vector`; dashboard loads; `/docs` lists endpoints
3. Upload the official WHO / CPCB PDFs via `POST /api/v1/knowledge/upload` (header `X-API-Key`)
4. Remove simulated data once real feeds run: `DELETE FROM sensor_readings WHERE source LIKE 'simulated%';`

## Operate
- Backups: `docker compose exec postgres-timescaledb-vector pg_dump -U ecopulse ecopulse | gzip > backup_$(date +%F).sql.gz` (cron daily, copy off-host)
- Logs: `make logs`; worker schedule: ingest 15 min, forecasts every 3 h, drift hourly
- Updates: `git pull && docker compose up --build -d`
- Schema changes need a migration (the init SQL only runs on an empty volume)

## Known limits
- No user accounts; only API-key protection on write/admin endpoints and IP rate limits on expensive ones. Dashboard reads are public.
- WebSocket has no auth/limits yet.
- Satellite CNN uses heuristic scoring until trained: `docker compose exec celery-worker python -m app.ml.train_spatial_cnn --images <dir>`
