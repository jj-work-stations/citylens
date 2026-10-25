# Traefik API Gateway — Operations Guide

Single public entrypoint for everything: **`https://gateway.kashefteam.org`**.
The frontend talks to one origin only; Traefik routes each path prefix to the
right backend. This document describes how the gateway is wired and **exactly
what to do to add a new service**.

---

## 1. Architecture

```
internet
   │  https://gateway.kashefteam.org
   ▼
nginx (host)          :443   TLS termination, wildcard *.kashefteam.org cert
   │
   ├─ /api/v1/*                ──▶ 127.0.0.1:8090 ─┐
   ├─ /health /docs /tiles/*   ──▶ 127.0.0.1:8090 ─┤
   ├─ /svc1..4/*               ──▶ 127.0.0.1:8090 ─┤
   │                                                ▼
   │                              Traefik (map_traefik) :80, "web" entrypoint
   │                                │  path-based routing + rate limit,
   │                                │  body limit, health checks, metrics
   │                                ├─ /api*, /health, /docs* ─▶ map_api:8000    (FastAPI)
   │                                ├─ /tiles/*  (prefix strip) ─▶ map_martin:3000 (Martin tiles)
   │                                └─ /svc1..4/* (prefix strip) ─▶ service1..4    (file provider)
   │
   └─ /dashboard/*  and /api/* (non-v1) ──▶ 127.0.0.1:8091
                                              Traefik dashboard + REST API
```

Key facts:

| Item | Value |
| --- | --- |
| Public host | `gateway.kashefteam.org` (DNS A → this server) |
| Traefik gateway port | `127.0.0.1:8090` → container `:80` (`web` entrypoint) |
| Traefik dashboard/API | `127.0.0.1:8091` → container `:8080` (`traefik` entrypoint) |
| Shared Docker network | `map_net` (fixed subnet `10.211.0.0/24`) |
| TLS | nginx only — Traefik does **not** terminate TLS, no ACME |
| Env vars | `.env`: `DOMAIN`, `TRAEFIK_HTTP_PORT=8090`, `TRAEFIK_API_PORT=8091` |

> `TRAEFIK_API_PORT` is **8091**, not 8080 — port 8080 on this host is taken
> by another process (`openshell-gateway`). If Traefik ever refuses to start,
> check that first.

---

## 2. Files

| File | Purpose | Reload |
| --- | --- | --- |
| `docker/traefik/traefik.yml` | **Static** config: entrypoints, providers, metrics, tracing. | restart container |
| `docker/traefik/dynamic/middlewares.yml` | Shared middlewares (rate-limit, body-limit, compress, retry, strip-tiles). | hot reload |
| `docker/traefik/dynamic/external-services.yml` | Routers/services for backends **not** in this compose project (svc1–4). | hot reload |
| `docker-compose.yml` (labels) | Routers for containers **in** this project (api, martin). | recreate container |
| `docker/traefik/nginx/apigateway.kashefteam.org.conf` | Reference nginx front door (installed copy lives in `/etc/nginx/sites-available/`, gateway block currently inside `newhamkar`). | `nginx -t && systemctl reload nginx` |
| `.env` | `DOMAIN`, `TRAEFIK_HTTP_PORT`, `TRAEFIK_API_PORT` used by compose labels/ports. | recreate container |

Two providers feed Traefik:

1. **Docker provider** — watches containers, picks up ones with
   `traefik.enable=true` (used for services inside this compose project).
2. **File provider** — watches `/etc/traefik/dynamic/*.yml` (used for
   middlewares and external backends). **Hot-reloads, no restart.**

---

## 3. Adding a new service

### Option A — container in this compose project (preferred)

Add the service to `docker-compose.yml` with labels:

```yaml
  myservice:
    image: myservice:latest
    container_name: map_myservice
    restart: unless-stopped
    networks:
      - map_net                     # ← REQUIRED, Traefik only routes on map_net
    ports:
      - "127.0.0.1:9001:9000"      # local debugging only; public = via Traefik
    labels:
      traefik.enable: "true"
      traefik.docker.network: "map_net"

      traefik.http.routers.myservice.rule: "Host(`${DOMAIN:-gateway.kashefteam.org}`) && PathPrefix(`/myservice`)"
      traefik.http.routers.myservice.entrypoints: "web"
      traefik.http.routers.myservice.middlewares: "rate-limit@file,in-flight@file,strip-myservice@file"
      traefik.http.routers.myservice.service: "myservice"

      traefik.http.services.myservice.loadbalancer.server.port: "9000"
      traefik.http.services.myservice.loadbalancer.healthcheck.path: "/health"
      traefik.http.services.myservice.loadbalancer.healthcheck.interval: "15s"
      traefik.http.services.myservice.loadbalancer.healthcheck.timeout: "5s"
```

If the backend expects the prefix **stripped** (`/myservice/foo` → `/foo`),
also define the middleware once in `dynamic/middlewares.yml`:

```yaml
    strip-myservice:
      stripPrefix:
        prefixes:
          - "/myservice"
```

Then apply:

```bash
docker compose up -d myservice     # labels only apply at container CREATION
```

**Rules:**

- `@file` suffix is **mandatory** when a Docker-label router references a
  middleware defined in `dynamic/` (without it Traefik looks for the
  middleware in the Docker provider and the router errors).
- `${DOMAIN}` expansion happens **only in docker-compose.yml labels** —
  Compose expands it, Traefik never does.
- The container **must** be attached to `map_net`. A container on another
  network is invisible to the gateway (`traefik.docker.network: map_net`).
- Editing labels on an already-running container does nothing — you must
  **recreate** it (`docker compose up -d <service>`, not `restart`).
- Route rule pattern used by existing services:
  `Host(\`gateway.kashefteam.org\`) && PathPrefix(\`/yourservice\`)`.

### Option B — backend outside this compose project

Add a block to `dynamic/external-services.yml` (hot-reloaded, no restart).
Copy the `svc1` pattern:

```yaml
http:
  services:
    myservice:
      loadBalancer:
        servers:
          - url: "http://my-backend-host:9000"   # LITERAL host — no ${VAR} here
        serversTransport: external
        passHostHeader: false

  routers:
    myservice:
      rule: "Host(`gateway.kashefteam.org`) && PathPrefix(`/myservice`)"
      entryPoints:
        - web
      service: myservice@file
      middlewares:
        - rate-limit@file
        - body-limit@file
        - strip-myservice@file      # define in middlewares.yml
        - cb-myservice@file         # optional circuit breaker
```

**Rules:**

- The `Host(...)` is **literal** — Traefik does not expand `${DOMAIN}` in
  file-provider config. Keep it in sync with `DOMAIN` in `.env`.
- The backend must be reachable from `map_net` (join the network, or it must
  be a routable host/IP).
- `docker compose up -d` is **not** needed — the file provider hot-reloads.

### Option C — frontend/static site

Serve it from nginx directly (like the other sites on this host), or give it
a path prefix through Traefik with a `fileServer`/`static` setup. For an SPA
built to a directory, the nginx `root + try_files` pattern already used on
this host is simpler — no Traefik involvement needed.

### After adding: nginx side

The current nginx gateway block routes:

- `/api/v1*` → `127.0.0.1:8090` (Traefik → FastAPI)
- `/dashboard/`, `/api/*` (anything else) → `127.0.0.1:8091` (dashboard)
- everything else (`/`, `/health`, `/docs`, `/tiles`, `/svc1..4`) → `127.0.0.1:8090`

New path prefixes under `/` need **no nginx change** — they flow through the
`location /` catch-all to Traefik. Only a new *top-level domain* needs a new
nginx `server` block, and a new `DOMAIN`/host in the router rules.

---

## 4. Middlewares reference (`dynamic/middlewares.yml`)

| Name | What it does | Attach to |
| --- | --- | --- |
| `rate-limit@file` | 100 req/s avg, burst 50, per client IP | every router |
| `in-flight@file` | max 200 concurrent requests per client | every router |
| `body-limit@file` | 10 MiB request body hard cap | every router |
| `compress@file` | gzip responses (skip if app already gzips) | tile/other non-compressing backends |
| `retry@file` | 3 attempts, 100 ms apart — **GET-like routes only** | tiles, GET APIs |
| `strip-tiles@file` | strips `/tiles` prefix | tiles router |
| `security-headers` | commented out — nginx emits these headers instead | — |

Middlewares run **in the order listed** in the router's `middlewares` list.

---

## 5. Dashboard, metrics, tracing

- **Dashboard**: <https://gateway.kashefteam.org/dashboard/> (proxied by nginx
  to `127.0.0.1:8091`). Its REST API lives under `/api/*` (non-`v1`) on the
  same port — which is why nginx splits `/api/v1` (FastAPI) from other
  `/api/*` (Traefik).
- **Metrics**: Prometheus scrapes `http://127.0.0.1:8091/metrics`.
- **Tracing**: Traefik exports OTLP spans to `tempo:4317`; the API propagates
  `traceparent`, so a request can be followed end-to-end in Grafana/Tempo.
- **Logs**: JSON access logs in `docker logs map_traefik`; nginx logs at
  `/var/log/nginx/gateway_{access,error}.log`.

---

## 6. Verification checklist

```bash
# Traefik healthy + routers registered
curl -s http://127.0.0.1:8091/api/http/routers | python3 -m json.tool | grep -E '"name"|"status"'

# Public endpoints
curl -s -o /dev/null -w '%{http_code}\n' https://gateway.kashefteam.org/health          # 200
curl -s -o /dev/null -w '%{http_code}\n' https://gateway.kashefteam.org/docs           # 200
curl -s -o /dev/null -w '%{http_code}\n' https://gateway.kashefteam.org/api/v1/auth/me # 401 (auth required)
curl -s -o /dev/null -w '%{http_code}\n' https://gateway.kashefteam.org/tiles/health   # 200
curl -s -o /dev/null -w '%{http_code}\n' https://gateway.kashefteam.org/dashboard/     # 200

# Config validation
docker compose config --quiet && echo OK
nginx -t
```

---

## 7. Troubleshooting (issues seen on this host)

| Symptom | Cause | Fix |
| --- | --- | --- |
| Browser shows "Welcome to nginx!" or nginx 404 on the gateway host | nginx `server` block has no `location /` → 8090, or points at the wrong port | Gateway block must proxy `location /` → `127.0.0.1:8090` (see §3) |
| Traefik 404 for `/health`, `/api` | No Docker routers: containers missing `traefik.enable` labels (created before labels existed) | `docker compose up -d <service>` to **recreate** with labels |
| Router exists but 502 | Backend container not on `map_net`, or wrong port label | attach to `map_net`, check `loadbalancer.server.port` |
| Dashboard works, app routes 404 (or vice versa) | nginx routes everything to 8091 (dashboard port) | split: `/api/v1*` + `location /` → 8090; `/dashboard/` + other `/api/*` → 8091 |
| Traefik fails to bind its API port | `TRAEFIK_API_PORT` collides with another process (8080 is taken here) | set `TRAEFIK_API_PORT=8091` in `.env`, `docker compose up -d traefik` |
| `${DOMAIN}` not expanded in a rule | Traefik never expands env vars — only Compose does, in labels | use labels for the rule, or write the host literally in `dynamic/*.yml` |
| Middleware "not found" error on a label router | Missing `@file` provider suffix | `rate-limit@file`, not `rate-limit` |
| Large upload rejected with 413 | nginx `client_max_body_size` < Traefik `body-limit` | keep nginx ≥ 10 m (body-limit middleware = 10 MiB) |
| `svc1..4` return 502 | Expected: backends don't exist yet (placeholders) | real: add backend on `map_net` or fix the `url` in `external-services.yml` |

---

## 8. Security notes

- Traefik binds **loopback only** (`127.0.0.1:8090/8091`); nothing is
  published to the internet. Public access exists only through nginx+TLS.
- The Docker socket is never mounted into Traefik — it reads a read-only
  `docker-socket-proxy` on an isolated internal network (`socket_net`).
- Backend debug ports (`8001`, `3001`) are `127.0.0.1`-bound.
- Security headers (HSTS/X-Frame/nosniff) are emitted by **nginx**, not
  Traefik, to avoid duplicates. If Traefik ever moves in front of nginx,
  uncomment `security-headers` in `middlewares.yml` and drop the nginx
  `add_header` lines.

---

## 9. Roadmap: Professional API Gateway — Auth & Load Balancing

### ✅ Completed (Currently Working)

| Feature | Status | Implementation |
| --- | --- | --- |
| **Single public entrypoint** | ✅ Done | `https://gateway.kashefteam.org` via nginx TLS termination |
| **Path-based routing** | ✅ Done | Traefik routes `/api/v1/*`, `/tiles/*`, `/svc1..4/*`, `/health`, `/docs` |
| **Rate limiting** | ✅ Done | `rate-limit@file` (100 req/s, burst 50) on every router |
| **In-flight request limit** | ✅ Done | `in-flight@file` (max 200 concurrent per client) |
| **Body size limit** | ✅ Done | `body-limit@file` (10 MiB) |
| **Request retry** | ✅ Done | `retry@file` (3 attempts, 100ms) for GET-like routes |
| **Prefix stripping** | ✅ Done | `strip-tiles@file` for `/tiles`, pattern ready for new services |
| **Health checks** | ✅ Done | Per-service `loadbalancer.healthcheck` (15s interval, 5s timeout) |
| **Load balancing** | ✅ Done | Round-robin via Traefik service `loadBalancer` |
| **Circuit breaker** | ✅ Partial | Middleware `cb-<service>@file` defined in pattern, ready to enable |
| **Metrics (Prometheus)** | ✅ Done | Scraped at `http://127.0.0.1:8091/metrics` |
| **Distributed tracing** | ✅ Done | OTLP → `tempo:4317`, `traceparent` propagated by API |
| **Dashboard + REST API** | ✅ Done | `https://gateway.kashefteam.org/dashboard/` + `/api/*` (non-v1) |
| **Hot-reload config** | ✅ Done | File provider watches `/etc/traefik/dynamic/*.yml` |
| **Security headers** | ✅ Done | HSTS, X-Frame-Options, X-Content-Type-Options via nginx |
| **Docker socket isolation** | ✅ Done | Read-only `docker-socket-proxy` on `socket_net` |

---

### 🔄 In Progress / Next Steps

| Priority | Feature | Description | Effort |
| --- | --- | --- | --- |
| **HIGH** | **Authentication / Authorization** | Add `ForwardAuth` middleware (OAuth2/OIDC/JWT validation) or integrate with existing auth service. Attach to protected routes (`/api/v1/*`, `/svc*`). | Medium |
| **HIGH** | **mTLS between services** | Enable Traefik `serversTransport` with TLS for backend connections; issue certs via internal CA. | Medium |
| **HIGH** | **API key management** | Middleware to validate API keys (header/query), rate-limit per key, integrate with key store (Redis/DB). | Medium |
| **MEDIUM** | **Request/Response transformation** | Add `replacePathRegex`, `addPrefix`, header manipulation middlewares for versioning/compat. | Low |
| **MEDIUM** | **WAF / IP allow/deny lists** | `IPWhiteList` / `IPAllowList` middlewares for admin endpoints (`/dashboard`, `/api/metrics`). | Low |
| **MEDIUM** | **Canary / Blue-Green deployments** | Weighted round-robin (`weight` on servers) or `mirroring` middleware for traffic shadowing. | Medium |
| **MEDIUM** | **Enhanced observability** | Add structured access logs to Loki, custom Prometheus metrics per route (latency, error rate). | Low |
| **LOW** | **Service mesh integration** | Evaluate Consul/Linkerd for service-to-service auth, retries, timeouts beyond edge gateway. | High |
| **LOW** | **GraphQL / gRPC routing** | Traefik v3 native gRPC routing; GraphQL query complexity limiting middleware. | Medium |

---

### 📋 Future Enhancements (Backlog)

| Feature | Notes |
| --- | --- |
| **OAuth2 / OIDC provider integration** | Keycloak, Auth0, or custom issuer; `forwardAuth` → token introspection endpoint |
| **JWT validation at edge** | `plugin/jwt` or custom middleware; validate `aud`, `iss`, `exp`, scopes |
| **Dynamic rate limiting tiers** | Per-client/per-route limits from Redis (sliding window log) |
| **Request/response body inspection** | Plugin for PII masking, schema validation, payload size alerts |
| **Automated certificate rotation** | If Traefik ever terminates TLS: ACME (Let's Encrypt) with DNS challenge |
| **Multi-region / geo-routing** | `X-Forwarded-For` geo lookup → route to nearest backend |
| **Chaos engineering hooks** | Fault injection middleware (latency, errors) for resilience testing |
| **GitOps for dynamic config** | ArgoCD/Flux sync `dynamic/*.yml` from Git; PR-based preview environments |
| **Developer portal** | Auto-generated OpenAPI docs per service behind `/docs/<service>` |
| **Cost attribution** | Per-service request/bandwidth metrics for chargeback/showback |

---

### 🛠 Implementation Notes for Auth (Next Major Step)

1. **Choose auth strategy**:
   - **Option 1**: `ForwardAuth` → call internal auth service (`/auth/validate`) on every request
   - **Option 2**: JWT validation middleware (stateless, verify signature + claims)
   - **Option 3**: OAuth2 introspection (RFC 7662) against token issuer

2. **Minimal `ForwardAuth` example** (add to `middlewares.yml`):
   ```yaml
   auth-validation:
     forwardAuth:
       address: "http://auth-service:8080/auth/validate"
       trustForwardHeader: true
       authResponseHeaders:
         - "X-User-ID"
         - "X-User-Roles"
         - "X-User-Permissions"
   ```
   Then attach: `middlewares: ["rate-limit@file", "auth-validation@file", ...]`

3. **Protect routes selectively**:
   - Public: `/health`, `/docs`, `/tiles/*` (read-only)
   - Protected: `/api/v1/*`, `/svc1..4/*`, `/dashboard/*`

4. **Pass user context downstream**:
   - Auth service sets `X-User-ID`, `X-User-Roles` headers
   - Backends trust these headers (validate in dev, enforce in prod)

5. **Token refresh / logout**:
   - Short-lived access tokens (15m) + refresh tokens
   - Logout → revoke refresh token in auth store

---

*Last updated: $(date -u +"%Y-%m-%d") — Review monthly or when adding new services.*
