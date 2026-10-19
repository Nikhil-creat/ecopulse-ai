-- =====================================================================
-- EcoPulse AI - core schema (TimescaleDB hypertables + Pgvector)
-- Runs once on first database initialisation.
-- =====================================================================

-- ---------- sensor_readings (hypertable) ----------
CREATE TABLE IF NOT EXISTS sensor_readings (
    time          TIMESTAMPTZ      NOT NULL,
    station_id    TEXT             NOT NULL,
    city          TEXT,
    latitude      DOUBLE PRECISION,
    longitude     DOUBLE PRECISION,
    aqi           REAL,
    pm25          REAL,
    pm10          REAL,
    no2           REAL,
    co            REAL,
    temperature   REAL,
    humidity      REAL,
    source        TEXT             NOT NULL DEFAULT 'unknown',
    quality_flag  SMALLINT         NOT NULL DEFAULT 0,  -- 0 ok, 1 suspect, 2 failed
    raw           JSONB,
    PRIMARY KEY (station_id, time)
);
SELECT create_hypertable('sensor_readings', 'time',
       chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS ix_sensor_city_time ON sensor_readings (city, time DESC);

ALTER TABLE sensor_readings SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'station_id'
);
SELECT add_compression_policy('sensor_readings', INTERVAL '7 days', if_not_exists => TRUE);

-- Hourly continuous aggregate for fast dashboards / model features
CREATE MATERIALIZED VIEW IF NOT EXISTS sensor_readings_hourly
WITH (timescaledb.continuous) AS
SELECT time_bucket('1 hour', time) AS bucket,
       station_id,
       avg(aqi)  AS aqi_avg,  avg(pm25) AS pm25_avg, avg(pm10) AS pm10_avg,
       avg(no2)  AS no2_avg,  avg(co)   AS co_avg,   avg(temperature) AS temp_avg,
       count(*)  AS samples
FROM sensor_readings
GROUP BY bucket, station_id
WITH NO DATA;
SELECT add_continuous_aggregate_policy('sensor_readings_hourly',
       start_offset => INTERVAL '3 days', end_offset => INTERVAL '1 hour',
       schedule_interval => INTERVAL '30 minutes', if_not_exists => TRUE);

-- ---------- forecasts (hypertable) ----------
CREATE TABLE IF NOT EXISTS forecasts (
    issued_at        TIMESTAMPTZ NOT NULL,
    target_time      TIMESTAMPTZ NOT NULL,
    station_id       TEXT        NOT NULL,
    pollutant        TEXT        NOT NULL,   -- aqi|pm25|pm10|no2|co|temperature
    horizon_hours    SMALLINT    NOT NULL,
    model_name       TEXT        NOT NULL,   -- prophet|arima|lstm|ensemble
    model_version    TEXT        NOT NULL,
    predicted        REAL        NOT NULL,
    lower_bound      REAL,
    upper_bound      REAL,
    confidence_level REAL        NOT NULL DEFAULT 0.95,
    verified         BOOLEAN     NOT NULL DEFAULT FALSE,  -- set by Forecast Verifier agent
    meta             JSONB,
    PRIMARY KEY (issued_at, station_id, pollutant, horizon_hours, model_name)
);
SELECT create_hypertable('forecasts', 'issued_at',
       chunk_time_interval => INTERVAL '7 days', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS ix_forecast_target ON forecasts (station_id, pollutant, target_time);

-- ---------- satellite_analyses (hypertable) ----------
CREATE TABLE IF NOT EXISTS satellite_analyses (
    captured_at           TIMESTAMPTZ NOT NULL,
    id                    UUID        NOT NULL DEFAULT gen_random_uuid(),
    region                TEXT        NOT NULL,
    bbox                  JSONB,                  -- [min_lon, min_lat, max_lon, max_lat]
    image_uri             TEXT        NOT NULL,
    image_type            TEXT        NOT NULL DEFAULT 'satellite', -- satellite|aerial|thermal
    smog_severity_index   REAL        NOT NULL,   -- 0..100
    green_canopy_density  REAL        NOT NULL,   -- 0..1
    heat_island_intensity REAL,                   -- deg C above rural baseline
    model_version         TEXT        NOT NULL,
    heatmap               JSONB,                  -- grid cells for 3D map
    meta                  JSONB,
    PRIMARY KEY (captured_at, id)
);
SELECT create_hypertable('satellite_analyses', 'captured_at',
       chunk_time_interval => INTERVAL '30 days', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS ix_sat_region_time ON satellite_analyses (region, captured_at DESC);

-- ---------- knowledge_embeddings (pgvector, hybrid-search ready) ----------
CREATE TABLE IF NOT EXISTS knowledge_embeddings (
    id           BIGSERIAL PRIMARY KEY,
    source       TEXT        NOT NULL,           -- e.g. WHO_AQG_2021, CPCB_NAAQS
    doc_title    TEXT        NOT NULL,
    doc_type     TEXT        NOT NULL DEFAULT 'guideline', -- guideline|policy|medical
    chunk_index  INTEGER     NOT NULL,
    content      TEXT        NOT NULL,
    content_tsv  TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    meta         JSONB,
    embedding    VECTOR(384) NOT NULL,           -- all-MiniLM-L6-v2
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, doc_title, chunk_index)
);
CREATE INDEX IF NOT EXISTS ix_knowledge_embedding_hnsw
    ON knowledge_embeddings USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS ix_knowledge_tsv ON knowledge_embeddings USING gin (content_tsv);

-- ---------- audit_logs ----------
CREATE TABLE IF NOT EXISTS audit_logs (
    id           BIGSERIAL PRIMARY KEY,
    ts           TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor        TEXT        NOT NULL,           -- user id, agent name, or system
    actor_type   TEXT        NOT NULL DEFAULT 'system', -- user|agent|system
    action       TEXT        NOT NULL,
    entity_type  TEXT,
    entity_id    TEXT,
    details      JSONB,
    ip_address   INET
);
CREATE INDEX IF NOT EXISTS ix_audit_ts ON audit_logs (ts DESC);
CREATE INDEX IF NOT EXISTS ix_audit_actor ON audit_logs (actor, ts DESC);

-- ---------- user_alerts ----------
CREATE TABLE IF NOT EXISTS user_alerts (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_ref         TEXT        NOT NULL,
    city             TEXT        NOT NULL,
    pollutant        TEXT        NOT NULL,
    threshold        REAL        NOT NULL,
    severity         TEXT        NOT NULL DEFAULT 'warning', -- info|warning|critical
    message          TEXT,
    status           TEXT        NOT NULL DEFAULT 'active',  -- active|triggered|acknowledged|disabled
    channel          TEXT        NOT NULL DEFAULT 'dashboard',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    triggered_at     TIMESTAMPTZ,
    acknowledged_at  TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_alert_user_status ON user_alerts (user_ref, status);
