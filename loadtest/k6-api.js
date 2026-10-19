// k6 load test: realistic dashboard read traffic + a trickle of authenticated ingest writes.
// Run: make loadtest   (BASE=http://host API_KEY=... make loadtest)
import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE = __ENV.BASE || 'http://localhost';
const KEY = __ENV.API_KEY || '';

export const options = {
  scenarios: {
    dashboard: { executor: 'ramping-vus', stages: [{ duration: '30s', target: 20 }, { duration: '1m', target: 50 }, { duration: '30s', target: 0 }], exec: 'dashboard' },
    ingest: { executor: 'constant-arrival-rate', rate: 2, timeUnit: '1s', duration: '2m', preAllocatedVUs: 5, exec: 'ingest' },
  },
  thresholds: { http_req_failed: ['rate<0.01'], 'http_req_duration{scenario:dashboard}': ['p(95)<800'] },
};

export function dashboard() {
  const r = http.batch([
    ['GET', `${BASE}/api/v1/readings/latest`],
    ['GET', `${BASE}/api/v1/stats/summary?city=Warangal`],
    ['GET', `${BASE}/api/v1/health/ready`],
  ]);
  r.forEach((x) => check(x, { 'status 2xx': (res) => res.status >= 200 && res.status < 300 }));
  sleep(1);
}

export function ingest() {
  const body = JSON.stringify({ readings: [{ station_id: 'loadtest-01', city: 'LoadTest', time: new Date().toISOString(), pm25: 40 + Math.random() * 20, pm10: 80, source: 'k6' }] });
  const res = http.post(`${BASE}/api/v1/ingest/readings`, body, { headers: { 'Content-Type': 'application/json', 'X-API-Key': KEY } });
  check(res, { 'ingest ok': (r) => r.status === 200 });
}
