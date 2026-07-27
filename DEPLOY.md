# Almanac Africa AI — deployment guide

This app ships as a **Flask + Gunicorn + PostgreSQL** stack behind **nginx** on a VPS.

Use **`./deployment.sh`** for day-to-day deploy commands. Config files live in `deploy/nginx/`.

```bash
# One command does everything:
sh deployment.sh

# Same as:
sh deployment.sh all
```

That will: start Docker → wait for health → nginx HTTP → certbot → nginx SSL → offer to create admin.

Domain: **almanac.africa** · App port: **HOST_PORT** from `.env` (default `8002`)

Other commands: `sh deployment.sh help`

---

## 1. Pre-flight checklist

- [ ] Strong `SECRET_KEY` (never reuse the dev value)
- [ ] Strong `POSTGRES_PASSWORD`
- [ ] Domain DNS **A record** → VPS public IP
- [ ] Ports **80** and **443** open on the firewall
- [ ] SMTP configured for subscribe / password-reset / newsletters
- [ ] First admin user created via CLI
- [ ] Site settings updated in `/admin/settings`

---

## 2. Generate secrets

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Put the result in `.env` as `SECRET_KEY`. Also set a strong `POSTGRES_PASSWORD`.

---

## 3. Deploy the app (Docker Compose)

On an Ubuntu/Debian VPS:

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2 git nginx certbot python3-certbot-nginx
sudo systemctl enable --now docker nginx

git clone <your-repo-url> almanac
cd almanac
cp .env.example .env
nano .env   # set SECRET_KEY and POSTGRES_PASSWORD (+ mail if ready)
```

Start the stack (Gunicorn on **127.0.0.1:8000** via published port 8000):

```bash
docker compose up --build -d
docker compose ps
curl http://127.0.0.1:8000/health
```

Create the first Super Admin:

```bash
docker compose exec web flask create-user --role SUPER_ADMIN
```

### Useful commands

```bash
docker compose logs -f web
docker compose exec web flask db upgrade
docker compose exec web flask send-scheduled-newsletters
docker compose down
```

---

## 4. nginx reverse proxy + Let’s Encrypt

### 4.1 Point DNS

Create an **A** record for `YOUR_DOMAIN` (and optionally `www`) to the VPS IP. Wait until it resolves.

### 4.2 Install HTTP site (before certificates)

```bash
sudo mkdir -p /var/www/certbot
sudo cp deploy/nginx/almanac.http.conf /etc/nginx/sites-available/almanac
sudo sed -i 's/YOUR_DOMAIN/yourdomain.com/g' /etc/nginx/sites-available/almanac
sudo ln -sf /etc/nginx/sites-available/almanac /etc/nginx/sites-enabled/almanac
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

Visit `http://yourdomain.com` — you should see the site.

### 4.3 Issue TLS certificates

```bash
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

Certbot will adjust the nginx site for HTTPS. Prefer keeping our full config afterward:

```bash
sudo cp deploy/nginx/almanac.conf /etc/nginx/sites-available/almanac
sudo sed -i 's/YOUR_DOMAIN/yourdomain.com/g' /etc/nginx/sites-available/almanac
sudo nginx -t && sudo systemctl reload nginx
```

Renewal is automatic via certbot’s timer. Test with:

```bash
sudo certbot renew --dry-run
```

### 4.4 Firewall (UFW)

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

Do **not** expose Postgres publicly. Compose already keeps it internal.

`PROXY_FIX=1` (default) trusts nginx’s `X-Forwarded-*` headers so cookies, CSRF, and absolute URLs use HTTPS.

---

## 5. Optional: bind Gunicorn to localhost only

For a tighter setup, publish the app only on the host loopback. In `docker-compose.yml` change ports to:

```yaml
ports:
  - "127.0.0.1:8000:8000"
```

Then only nginx (on the same machine) can reach Gunicorn.

---

## 6. Scheduled newsletters

```bash
docker compose exec web flask send-scheduled-newsletters
```

Crontab every 5 minutes:

```cron
*/5 * * * * cd /path/to/almanac && docker compose exec -T web flask send-scheduled-newsletters
```

---

## 7. After go-live

1. Confirm **https://yourdomain.com** loads with a valid certificate.
2. `/admin/settings` — site name, contact, social.
3. Create categories / first articles.
4. Confirm subscribe email (SMTP).
5. Check `/sitemap.xml`, `/robots.txt`, `/feed.xml`.
6. Sign in at `/auth/login`.

---

## 8. Security notes

- `.env` is gitignored — never commit it.
- Postgres port is **not** published by default.
- Production refuses weak `SECRET_KEY` values.
- Cookies are `Secure` + `HttpOnly` + `SameSite=Lax` in production.
- Uploads max **16 MB** (`client_max_body_size` matches Flask).
- Prefer Redis for `RATELIMIT_STORAGE_URI` with multiple Gunicorn workers across hosts.
  Docker Compose includes a `redis` service and defaults to `redis://redis:6379/0`.
  Local `flask run` can keep `memory://`.

---

## 9. Rollback

```bash
docker compose exec web flask db downgrade
docker compose up --build -d
sudo nginx -t && sudo systemctl reload nginx
```

---

## 10. Troubleshooting: `Name or service not known` (database)

The web container could not resolve the Postgres hostname.

**Fix on the VPS:**

```bash
cd ~/almanac
# Ensure .env has SECRET_KEY and POSTGRES_PASSWORD (not DATABASE_URL=localhost for Docker)
docker compose down
docker compose up --build -d
docker compose ps
docker compose logs db --tail 50
docker compose logs web --tail 50
```

Confirm both services are on the same network and `db` resolves:

```bash
docker compose exec web getent hosts db
docker compose exec web printenv DB_HOST POSTGRES_DB
```

You should see `DB_HOST=db`. The entrypoint builds `DATABASE_URL` from that (password is URL-encoded automatically).
