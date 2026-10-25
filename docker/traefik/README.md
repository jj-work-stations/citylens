# API Gateway (Traefik)

Single public entrypoint for the frontend. The frontend talks to **one**
host — `https://gateway.kashefteam.org` — and Traefik routes each path
prefix to the right backend, so backend URLs never leak into the client.

```
internet
   │  https://gateway.kashefteam.org
   ▼
nginx (host)          :443   TLS termination, wildcard *.kashefteam.org cert
   │  http://127.0.0.1:8090
   ▼
Traefik               :80    routing, rate limiting, health checks, metrics
   │
   ├── /api/*, /health, /docs*   ──▶  api:8000      (FastAPI, this repo)
   ├── /tiles/*                  ──▶  martin:3000   (tile server, prefix stripped)
   └── /svc1..4/*                ──▶  service1..4   (external microservices)
```

nginx stays the edge because this server already fronts ~15 other projects
with it, and its wildcard certificate already covers `*.kashefteam.org` —
so **no new certificate has to be issued** and no other site is touched.

## Files

| File | Purpose |
| --- | --- |
| `traefik.yml` | Static config: entrypoints, providers, observability. Read once at startup. |
| `dynamic/middlewares.yml` | Rate limiting, request-size limits, compression, prefix stripping. Hot-reloaded. |
| `dynamic/external-services.yml` | Routes + circuit breakers for the external microservices. Hot-reloaded. |
| `nginx/gateway.kashefteam.org.conf` | The nginx server block that fronts Traefik. |

Routing for services **in** this Compose project (`api`, `martin`) is declared
with Docker labels in `docker-compose.yml`, so it is environment-driven
(`Host(\`${DOMAIN}\`)` is expanded by Compose).

## Setup

```bash
# 1. Environment
cp .env.example .env          # then set DOMAIN / TRAEFIK_HTTP_PORT

# 2. DNS — point the host at this server
#    gateway.kashefteam.org  A  31.7.70.193      (this host)

# 3. Start the gateway
docker compose up -d traefik docker-socket-proxy

# 4. nginx front door
sudo cp docker/traefik/nginx/gateway.kashefteam.org.conf \
        /etc/nginx/sites-available/gateway.kashefteam.org
sudo ln -s /etc/nginx/sites-available/gateway.kashefteam.org \
           /etc/nginx/sites-enabled/gateway.kashefteam.org
sudo nginx -t && sudo systemctl reload nginx
```

Verify:

```bash
curl -s https://gateway.kashefteam.org/health          # {"status":"ok",...}
curl -s -o /dev/null -w '%{http_code}\n' \
     https://gateway.kashefteam.org/api/v1/...          # 200 / 401
```

## Adding a service

**Container in this Compose project** (preferred) — add labels to that
service and Traefik discovers it automatically:

```yaml
    labels:
      traefik.enable: "true"
      traefik.docker.network: "map_net"
      traefik.http.routers.myservice.rule: "Host(`${DOMAIN:-gateway.kashefteam.org}`) && PathPrefix(`/myservice`)"
      traefik.http.routers.myservice.entrypoints: "web"
      traefik.http.routers.myservice.middlewares: "rate-limit@file,in-flight@file"
      traefik.http.services.myservice.loadbalancer.server.port: "9000"
      traefik.http.services.myservice.loadbalancer.healthcheck.path: "/health"
```

Note: the `@file` suffix is required when a Docker-label router references a
middleware defined in `dynamic/`.

**Service running elsewhere** — add a router + service to
`dynamic/external-services.yml` (see `svc1` for the pattern) and keep the host
literal, because Traefik never expands `${VAR}` in dynamic config.

## Operational notes

- **Security headers** are emitted by nginx, not Traefik, to avoid duplicate
  `Strict-Transport-Security` / `X-Frame-Options` on the same response. If
  Traefik is ever moved in front of nginx, uncomment `security-headers` in
  `dynamic/middlewares.yml` and drop the `add_header` lines from the nginx block.
- **Dashboard** — bound to `127.0.0.1:8080` only. Reach it over an SSH tunnel:
  `ssh -L 8080:127.0.0.1:8080 <server>` then open <http://localhost:8080/dashboard/>.
- **Metrics** — Prometheus scrapes `http://127.0.0.1:8080/metrics`.
  `TRAEFIK_API_PORT` must be free; on this host `8080` is used by another
  process, so set e.g. `TRAEFIK_API_PORT=8091` in `.env` if the gateway
  refuses to start.
- **Tracing** — Traefik exports OTLP spans to `tempo:4317` and propagates
  trace context, so a frontend request can be followed end-to-end in Tempo.
- **Docker socket** — Traefik never mounts `/var/run/docker.sock`; it reads a
  read-only docker-socket-proxy on an internal network. Only the containers,
  services, tasks, networks, events and ping endpoints are allowed.
- **Backend ports** (`api` 8001, `martin` 3001) are published on `127.0.0.1`
  only, for local debugging. Public traffic must go through the gateway.

## Switching Traefik to the edge (future)

If you later retire host nginx and let Traefik terminate TLS, add to
`traefik.yml`:

```yaml
entryPoints:
  web:
    address: ":80"
    http:
      redirections:
        entryPoint: { to: websecure, scheme: https, permanent: true }
  websecure:
    address: ":443"
certificatesResolvers:
  letsencrypt:
    acme:
      storage: /letsencrypt/acme.json
      httpChallenge: { entryPoint: web }
```

then move the routers to the `websecure` entrypoint with
`tls.certresolver=letsencrypt`, publish `80:80` / `443:443`, add the
`traefik_letsencrypt` volume, and enable the `security-headers` middleware.
