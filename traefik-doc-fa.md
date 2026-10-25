# راهنمای عمل گیت API — راهنمای عملی Traefik

ورودی عمومی واحد برای همه چیز: **`https://gateway.kashefteam.org`**.
інтерфейس به یکorigin فقط صحبت می‌کند؛ Traefik مسیر پیشوندهای مسیر را به backends مناسب می‌رساند. این مستندsyntax به شرحרת كيفية اتصال گیت است و دقیقاً **چه کاری باید برای افزودن یک سرویس جدید انجام شود**.

---

## 1. معماری

```
اینترنت
    │  https://gateway.kashefteam.org
    ▼
nginx (میزبان)          :443   پایان دادن TLS، گواهینامه Wildcard *.kashefteam.org
    │
    ├─ /api/v1/*                ──▶ 127.0.0.1:8090 ─┐
    ├─ /health /docs /tiles/*   ──▶ 127.0.0.1:8090 ─┤
    ├─ /svc1..4/*               ──▶ 127.0.0.1:8090 ─┤
    │                                                ▼
    │                              Traefik (map_traefik) :80، "web" ورودی
    │                                │  مسیر مبتنی بر routing + محدودیت نرخ،
    │                                │  محدودیت بدنه، بررسی سلامت، متریک
    │                                ├─ /api*، /health، /docs* ─▶ map_api:8000    (FastAPI)
    │                                ├─ /tiles/*  (حذف پیشوند) ─▶ map_martin:3000 (Martin tiles)
    │                                └─ /svc1..4/* (حذف پیشوند) ─▶ service1..4    (ارائه‌دهنده پرونده)
    │
    └─ /dashboard/*  و /api/* (غیر-v1) ──▶ 127.0.0.1:8091
                                               داشبورد Traefik + REST API
```

حقایق کلیدی:

| قلم | مقدار |
| --- | --- |
| میزبان عمومی | `gateway.kashefteam.org` (DNS A → این سرور) |
| پورت گیت Traefik | `127.0.0.1:8090` → حاوية `:80` (`web` ورودی) |
| داشبورد/API Traefik | `127.0.0.1:8091` → حاوية `:8080` (`traefik` ورودی) |
| شبکه Docker مشترک | `map_net` (زیرش شبکه ثابت `10.211.0.0/24`) |
| TLS | فقط nginx — Traefik **خالصاً** TLS خاتمه نمی‌دهد، هیچ ACME‌ای |
| متغیرهای محیطی | `.env`: `DOMAIN`, `TRAEFIK_HTTP_PORT=8090`, `TRAEFIK_API_PORT=8091` |

> `TRAEFIK_API_PORT` **8091** است، نه 8080 — پورت 8080 در این میزبان توسط یک processus دیگر (`openshell-gateway`) اشغال شده است. اگر Traefik هرگز شروع نشد، ابتدا این مورد را بررسی کنید.

---

## 2. پرونده‌ها

| پرونده | هدف | بارگذاری مجدد |
| --- | --- | --- |
| `docker/traefik/traefik.yml` | **پیکربندی استاتیک**: ورودی‌ها، ارائه‌دهندگان، متریک، پیگیری. | راه‌اندازی مجدد حاوية |
| `docker/traefik/dynamic/middlewares.yml` | میان‌افزارهای مشترک (محدودیت نرخ، محدودیت بدنه، فشرده‌سازی، تلاش دوباره، حذف tiles). | بارگذاری مجدد غیارشده |
| `docker/traefik/dynamic/external-services.yml` | روترها/خدمات برای backends **نه** در این پروژه-compose (svc1–4). | بارگذاری مجدد غیارشده |
| `docker-compose.yml` (برچسب‌ها) | روترها برای حاويات **در** این پروژه (api، martin). | بازسازی حاوية |
| `docker/traefik/nginx/apigateway.kashefteam.org.conf` | دروازه nginx مرجع (نسخه نصب شده در `/etc/nginx/sites-available/` lebt، بلوک gateway در حال حاضر داخل `newhamkar`). | `nginx -t && systemctl reload nginx` |
| `.env` | `DOMAIN`, `TRAEFIK_HTTP_PORT`, `TRAEFIK_API_PORT` توسط برچسب‌های compose/ports استفاده می‌شود. | بازسازی حاوية |

دو ارائه‌دهنده Traefik را تغذیه می‌کنند:

1. **ارائه‌ده Docker** — حاويات را見て، حاویاتی که `traefik.enable=true` دارند را انتخاب می‌کند (برای خدمات داخل این پروژه-compose استفاده می‌شود).
2. **ارائه‌ده پرونده** — `/etc/traefik/dynamic/*.yml` را watched می‌کند (برای میان‌افزارها و backends خارجی استفاده می‌شود). **بارگذاری مجدد غیارشده، بدون restart.**

---

## 3. افزودن یک سرویس جدید

### گزینهٔ A — حاوية در این پروژه-compose (مهمان)

سرویس را به `docker-compose.yml` با برچسب‌ها اضافه کنید:

```yaml
  myservice:
    image: myservice:latest
    container_name: map_myservice
    restart: unless-stopped
    networks:
      - map_net                     # ← لازم، Traefik فقط بر روی map_net مسیر می‌دهد
    ports:
      - "127.0.0.1:9001:9000"      # فقط برای دیباگ محلی؛ عمومی = از طریق Traefik
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

اگر backend انتظار دارد پیشوند **حذف شود** (`/myservice/foo` → `/foo`)، همچنین middleware یک بار در `dynamic/middlewares.yml` تعریف کنید:

```yaml
    strip-myservice:
      stripPrefix:
        prefixes:
          - "/myservice"
```

سپس اعمال کنید:

```bash
docker compose up -d myservice     # برچسب‌ها فقط در زمان **ایجاد** حاوية اعمال می‌شوند
```

**قوانین:**

- پسوند `@file` **الزامی** است وقتی Router برچسب Docker به middlewareی در `dynamic/` Refer می‌کند (بدون آن Traefik به دنبال middleware در ارائه‌ده Docker می‌گردد و router خطا می‌دهد).
- توسعه `${DOMAIN}` **فقط در برچسب‌های docker-compose.yml** رخ می‌دهد — Compose آن را گسترش می‌دهد، Traefik هرگز نکند.
- حاوية **باید** به `map_net` متصل باشد. یک حاوية در شبکه دیگری برای gateway **ناتوان** است (`traefik.docker.network: map_net`).
- ویرایش برچسب‌های در حاوية در حال اجرا کاری انجام نمی‌دهد — باید آن را **بازسازی** کنید (`docker compose up -d <service>`, نه `restart`).
- الگو Rule استفاده شده توسط خدمات موجود:
  `Host(\`gateway.kashefteam.org\`) && PathPrefix(\`/yourservice\`)`.

### گزینهٔ B — backend خارج از این پروژه-compose

یک bloc به `dynamic/external-services.yml` اضافه کنید (بارگذاری مجدد غیارشده، بدون restart). الگوی `svc1` را کپی کنید:

```yaml
http:
  services:
    myservice:
      loadBalancer:
        servers:
          - url: "http://my-backend-host:9000"   # هاست لیت럴 — هیچ ${VAR} ندارد
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
        - strip-myservice@file      # تعریف در middlewares.yml
        - cb-myservice@file         # optional circuit breaker
```

**قوانین:**

- `Host(...)` **litera** است — Traefik در config ارائه‌دهنده پرونده `${DOMAIN}` را گسترش نمی‌دهد. آن را با `DOMAIN` در `.env` همگام کنید.
- backend باید از `map_net` قابل دسترسی باشد (به شبکه بپیوندید، یا یک host/IP قابل routing باشد).
- `docker compose up -d` **لازم نیست** — ارائه‌دهنده پرونده بارگذاری مجدد غیارشده می‌کند.

### گزینهٔ C — سایت frontend/static

از nginx مستقیم (مثل سایر سایت‌ها در این میزبان) برای ارائه آن استفاده کنید، یا آن را از طریق Traefik با یک `fileServer`/`static` setup پیشوند مسیر دهید. برای SPA که به یک دایرکتوریBuilt شده است، الگوی nginx `root + try_files` که در این میزبان قبلاً استفاده شده است، ساده‌تر است — هیچ Include Traefik لازم نیست.

### پس از افزودن: جانب nginx

بلوک gateway nginx فعلی مسیرهای زیر را rout می‌کند:

- `/api/v1*` → `127.0.0.1:8090` (Traefik → FastAPI)
- `/dashboard/`, `/api/*` (همه چیز دیگر) → `127.0.0.1:8091` (داشبورد)
- همه چیز دیگر (`/`, `/health`, `/docs`, `/tiles`, `/svc1..4`) → `127.0.0.1:8090`

پیشوندهای مسیر جدید تحت `/` **هیچ تغییری در nginx نیازی ندارند** — آنها از طریق `location /` catch-all به Traefik می‌روند. فقط یک *دامنه سطح بالا* جدید نیاز به یک بلوک nginx `server` جدید دارد، و یک `DOMAIN`/host جدید در قوانین روتر.

---

## 4. مرجع میان‌افزارها (`dynamic/middlewares.yml`)

| نام | چه کاری انجام می‌دهد | پیوست به |
| --- | --- | --- |
| `rate-limit@file` | 100 req/s متوسط،突發 50، به ازای هر IP کلاینت | هر روتر |
| `in-flight@file` | حداکثر 200 درخواست concurrents به ازای هر کلاینت | هر روتر |
| `body-limit@file` | سقف بدنه درخواست 10 MiB | هر روتر |
| `compress@file` | پاسخ‌ها را gzip می‌کند (اگر برنامه قبلاً gzip کرده باشد، رد می‌شود) | بک‌اندهای tile/non-compress |
| `retry@file` | 3 تلاش، 100 ms جداگانه — **فقط مسیرهای類似 GET** | tiles، GET APIs |
| `strip-tiles@file` | پیشوند `/tiles` را حذف می‌کند | روتر tiles |
| `security-headers` | commentary out — nginx این هدرها را ب stattdessen می‌دهد | — |

میان‌افزارها **در ترتیب لیست شده** در لیست `middlewares` روتر اجرا می‌شوند.

---

## 5. داشبورد، متریک، پیگیری

- **داشبورد**: <https://gateway.kashefteam.org/dashboard/> (nginx به `127.0.0.1:8091` پروکسی می‌کند). API REST آن تحت `/api/*` (غیر-`v1`) در همان پورت زندگی می‌کند — کهértگی این است که nginx `/api/v1` (FastAPI) را از دیگر `/api/*` (Traefik) جداگانه می‌کند.
- **متریک**: Prometheus `http://127.0.0.1:8091/metrics` را هرا می‌گیرد.
- **پیگیری**: Traefik مقاطع OTLP را به `tempo:4317` صادر می‌کند؛ API `traceparent` را प्रसारित می‌کند، بنابراین یک درخواست می‌تواند end-to-end در Grafana/Tempo دنبال شود.
- **لاگ‌ها**: لاگ‌های دسترسی JSON در `docker logs map_traefik`؛ لاگ‌های nginx در `/var/log/nginx/gateway_{access,error}.log`.

---

## 6. چکلیست تأیید

```bash
# Traefik سالم + روترها ثبت شد
curl -s http://127.0.0.1:8091/api/http/routers | python3 -m json.tool | grep -E '"name"|"status"'

# endpoints عمومی
curl -s -o /dev/null -w '%{http_code}\n' https://gateway.kashefteam.org/health          # 200
curl -s -o /dev/null -w '%{http_code}\n' https://gateway.kashefteam.org/docs           # 200
curl -s -o /dev/null -w '%{http_code}\n' https://gateway.kashefteam.org/api/v1/auth/me # 401 (اجازهٔ لازم)
curl -s -o /dev/null -w '%{http_code}\n' https://gateway.kashefteam.org/tiles/health   # 200
curl -s -o /dev/null -w '%{http_code}\n' https://gateway.kashefteam.org/dashboard/     # 200

# تأیید config
docker compose config --quiet && echo OK
nginx -t
```

---

## 7. عیب‌یابی (مسائل دیده شده در این میزبان)

| علامت | دلیل | رفع |
| --- | --- | --- |
| مرورگر "خوش آمدید به nginx!" یا nginx 404 را نشان می‌دهد | بلوک nginx `server` هیچ `location /` → 8090 ندارد، یا به پورت نادرست اشاره می‌کند | بلوک gateway باید `location /` → `127.0.0.1:8090` را پروکسی کند (بخش 3 را ببینید) |
| Traefik 404 برای `/health`، `/api` | هیچ روتر Docker: حاويات برچسب `traefik.enable` ندارند (قبل از وجود برچسب‌ها ایجاد شده‌اند) | `docker compose up -d <service>` را برای **بازسازی** با برچسب‌ها اجرا کنید |
| روتر وجود دارد اما 502 | حاوية backend بر روی `map_net` نیست، یا برچسب پورت نادرست | به `map_net` متصل شوید، `loadbalancer.server.port` را بررسی کنید |
| داشبورد کار می‌کند، مسیرهای اپلیکیشن 404 می‌دهند (یا برعکس) | nginx همه چیز را به 8091 (پورت داشبورد) می‌روند | تقسیم: `/api/v1*` + `location /` → 8090؛ `/dashboard/` + دیگر `/api/*` → 8091 |
| Traefik porte API خود را نمی‌تواند bind کند | `TRAEFIK_API_PORT` با یک processus دیگر (8080 در اینجا اشغال است) برخورد می‌کند | در `.env` `TRAEFIK_API_PORT=8091` تنظیم کنید، `docker compose up -d traefik` را اجرا کنید |
| `${DOMAIN}` در یک قواعد گسترش نیodas است | Traefik هرگز متغیرهای محیط را گسترش نمی‌دهد — فقط Compose در برچسب‌ها ऐसा می‌کند | برای القاعدة، برچسب‌ها را استفاده کنید، یا میزبان را به طور litral در `dynamic/*.yml` بنویسید |
| خطا "middleware یافت نشد" در روتر برچسب | falta suffix `@file` provider | `rate-limit@file`، نه `rate-limit` |
| آپلود بزرگ با 413 رد می‌شود | nginx `client_max_body_size` < Traefik `body-limit` | nginx را ≥ 10 m نگه دارید (middleware body-limit = 10 MiB) |
| `svc1..4` 502 برمی‌گردند | مورد انتظار: backends وجود ندارند (جایگزین) | واقعی: backend روی `map_net` اضافه کنید یا `url` در `external-services.yml` را اصلاح کنید |

---

## 8. نکات امنیتی

- Traefik فقط **loopback** را bind می‌کند (`127.0.0.1:8090/8091`); هیچ چیزی به اینترنت منتشر نمی‌شود. دسترسی عمومی تنها از طریق nginx+TLS موجود است.
- nooit Socket Docker به داخل Traefik mount نمی‌شود — آن یک `docker-socket-proxy` فقط خواندن در یک شبکه داخلی изолированное (`socket_net`) می‌خواند.
- پورتهای دیباگ backend (`8001`, `3001`) به `127.0.0.1`-bound هستند.
- هدرهای امنیتی (HSTS/X-Frame/nosniff) توسط **nginx**، نه Traefik،发散 می‌شوند تا تکرار جلوگیری شود. اگر Traefik هرگز قبل از nginx قرار گیرد، `security-headers` را در `middlewares.yml` uncomment کنید و خطوط `add_header` nginx را حذف کنید.

---

## 9. نقشه راه: API Gateway حرفه‌ای — احراز هویت & توزیع بار

### ✅ تکمیل شده (در حال کار)

| ویژگی | وضعیت | پیاده‌سازی |
| --- | --- | --- |
| **ورودی عمومی واحد** | ✅ انجام شده | `https://gateway.kashefteam.org` از طریق پایان دادن TLS nginx |
| **مسیر مبتنی بر Routing** | ✅ انجام شده | Traefik مسیر `/api/v1/*`، `/tiles/*`، `/svc1..4/*`، `/health`، `/docs` را می‌دهد |
| **محدودیت نرخ** | ✅ انجام شده | `rate-limit@file` (100 req/s،突発 50) در هر روتر |
| **محدودیت درخواست در حال پروسه** | ✅ انجام شده | `in-flight@file` (حداکثر 200 concurrents به ازای هر کلاینت) |
| **محدودیت بدنه** | ✅ انجام شده | `body-limit@file` (10 MiB) |
| **تلاش دوباره درخواست** | ✅ انجام شده | `retry@file` (3 تلاش، 100ms) برای مسیرهای類似 GET |
| **حذف پیشوند** | ✅ انجام شده | `strip-tiles@file` برای `/tiles`، الگوی آماده برای خدمات جدید |
| **بررسی‌های سلامت** | ✅ انجام شده | `loadbalancer.healthcheck` به ازای هر سرویس (فاصلہ 15s، مهلت 5s) |
| **توزیع بار** | ✅ انجام شده | Round-robin از طریق سرویس `loadBalancer` Traefik |
| **циркуит breaker** | ✅ جزئی | middleware `cb-<service>@file` در الگو تعریف شده، آماده برای فعال‌سازی |
| **متریک (Prometheus)** | ✅ انجام شده | اسکرپ شده در `http://127.0.0.1:8091/metrics` |
| **پیگیری توزیع‌شده** | ✅ انجام شده | OTLP → `tempo:4317`؛ `traceparent` توسط API प्रसارित می‌شود |
| **داشبورد + REST API** | ✅ انجام شده | `https://gateway.kashefteam.org/dashboard/` + `/api/*` (غیر-v1) |
| **بارگذاری مجدد غیارشده config** | ✅ انجام شده | ارائه‌دهنده پرونده `/etc/traefik/dynamic/*.yml` را watched می‌کند |
| **هدرهای امنیتی** | ✅ انجام شده | HSTS، X-Frame-Options، X-Content-Type-Options از طریق nginx |
| **عزلهaking Socket Docker** | ✅ انجام شده | `docker-socket-proxy` فقط خواندن در `socket_net` |

---

### 🔄 در حال پیشبرد / مراحل بعدی

| اولویت | ویژگی | توضیح | تلاش |
| --- | --- | --- | --- |
| **بالا** | **احراز هویت / مجوزها** | اضافه کردن middleware `ForwardAuth` (احراز هویت OAuth2/OIDC/JWT) یا یکپارچه‌سازی با سرویس احراز هویت موجود. به مسیرهای محافظت‌شده (`/api/v1/*`، `/svc*`) 붙ومئد. | متوسط |
| **بالا** | **mTLS بین خدمات** | فعال کردن `serversTransport` با TLS در Traefik برای اتصالات backend؛ صدور گواهینامه‌ها از طریق CA داخلی. | متوسط |
| **بالا** | **مدیریת کلید API** | میان‌افزار برای اعتبارسنجی کلیدهای API (header/query)، محدودیت نرخ به ازای هر کلید، یکپارچه‌سازی با ذخیره کلید (Redis/DB). | متوسط |
| **متوسط** | **تبدیل درخواست/پاسخ** | اضافه کردن middlewares `replacePathRegex`، `addPrefix`، دستکاری هدر برای سازگاری/نسخه‌سازی. | کم |
| **متوسط** | **WAF / لیست‌های اجازه/عدم اجازه IP** | middlewares `IPWhiteList` / `IPAllowList` برای endpoints اداری (`/dashboard`، `/api/metrics`). | کم |
| **متوسط** | **استقرار Canary / Blue-Green** | weighted round-robin (`weight` بر روی servers) یا middleware `mirroring` برای سایه tráfico. | متوسط |
| **متوسط** | **قابل مشاهدهсть پیشرفته** | اضافه کردن لاگ‌های دسترسی ساختاریافته به Loki، متریک‌های Prometheus سفارشی به ازای هر مسیر (لatenzi، نرخ خطا). | کم |
| **پایین** | **یکپارچه‌سازی service mesh** | ارزیابی Consul/Linkerd برای احراز istening service-to-service، retries، timeouts خارج از edge gateway. | بالا |
| **پایین** | **مسیردهی GraphQL / gRPC** | Traefik v3 مسیردهی بومی gRPC؛ middleware پیچیدگی سؤال GraphQL. | متوسط |

---

### 📋 بهبودهای آینده (باک‌لاگ)

| ویژگی | ملاحظات |
| --- | --- |
| **احراز هویت OAuth2 / OIDC** | Keycloak، Auth0، یا صادرکننده سفارشی؛ `forwardAuth` →endpoint introspection توکن |
| **احراز هویت JWT در لبه** | `plugin/jwt` یا middleware سفارشی؛ اعتبارسنجی `aud`، `iss`، `exp`، scopes |
| **محدودیت نرخ Dinamically tiers** | محدودیت‌های per-client/per-route از Redis ( fenêtre lancement journalisé) |
| **بررسی بدنه درخواست/پاسخ** | پلاگین برای PIE masking، اعتبارسنجی schema، هشدارهای اندازه بار |
| **دوران خودکار گواهینامه** | اگر Traefik هرگز TLS خاتمه دهد: ACME (Let's Encrypt) با چالش DNS |
| **مسیردهی چند‌ناحه / جغرافیایی** | جستجوی جغرافیایی `X-Forwarded-For` → مسیر به backend نزدیک‌ترین |
| **خطافات摩擦工程** | middleware خطای manque (لاتانس، errores) برای آزمایش 설ниванию |
| **GitOps برای config دینامیک** | ArgoCD/Flux همگام‌سازی `dynamic/*.yml` از Git؛ محیط‌های پیشنمایش مبتنی بر PR |
| **پرتال توسعه‌دهنده** | اسناد OpenAPI tự تولید شده برای هر سرویس پشت `/docs/<service>` |
| **شناسهباء هزینه** | متریک‌های درخواست/ پهنای باند به ازای هر سرویس برای chargeback/showback |

---

### 🛠 Notas Implementação para Auth (Próximo Passo Principal)

1. **استراتژی احراز هویت را انتخاب کنید**:
   - **اختیار 1**: `ForwardAuth` → فراخوانی سرویس احراز هویت داخلی (`/auth/validate`) در هر درخواست
   - **اختیار 2**: middleware اعتبارسنجی JWT (بی‌وضعیت، امضا +-Claims را تأیید کنید)
   - **اختیار 3**: introspection OAuth2 (RFC 7662) مقابل صادرکننده توکن

2. **نمونه minimale `ForwardAuth`** (افزودن به `middlewares.yml`):
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
   سپس پیوست کنید: `middlewares: ["rate-limit@file", "auth-validation@file", ...]`

3. **مسیرها را به صورت اختیاری محافظت کنید**:
   - عمومی: `/health`، `/docs`، `/tiles/*` (فقط خواندنی)
   - محافظت‌شده: `/api/v1/*`، `/svc1..4/*`، `/dashboard/*`

4. **میانproveudo contexto downstream**:
   - سرویس احراز هویت هدرهای `X-User-ID`، `X-User-Roles` تنظیم می‌کند
   - بckends این هدرها را tinccat می‌کنند (اعتبارسنجی در dev، اعمال در prod)

5. **Refresh توکن / logout**:
   - توکن‌های دسترسی کوتاه‌العمر (15m) + توکن‌های refresh
   - logout → توکن refresh را در فروشگاه احراز هویت لغو کنید

---

*آخرین بروز رسانی: $(date -u +"%Y-%m-%d") — ماهانه یا هنگام افزودن خدمات جدید بازنگری کنید.*