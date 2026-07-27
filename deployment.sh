#!/bin/sh
# Almanac Africa AI — VPS deployment
#
# One-shot (recommended):
#   sh deployment.sh
#
# Or:
#   ./deployment.sh
#   sh deployment.sh all
#
# Other commands: sh deployment.sh help

set -eu

ROOT="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
cd "$ROOT"

DOMAIN_DEFAULT="almanac.africa"
NGINX_SITE="almanac"
NGINX_AVAIL="/etc/nginx/sites-available/${NGINX_SITE}"
NGINX_ENABLED="/etc/nginx/sites-enabled/${NGINX_SITE}"

# ---------------------------------------------------------------------------
# Safe .env reader (no bash source — passwords may contain ! $ " etc.)
# ---------------------------------------------------------------------------

env_get() {
  # Usage: env_get KEY [default]
  key="$1"
  default="${2:-}"
  if [ ! -f .env ]; then
    printf '%s\n' "$default"
    return 0
  fi
  # Take first matching KEY=value line; strip CR; strip surrounding quotes
  val="$(
    grep -E "^[[:space:]]*${key}=" .env 2>/dev/null | head -n 1 | sed "s/^[[:space:]]*${key}=//" | tr -d '\r' || true
  )"
  # Remove matching wrapping quotes only
  case "$val" in
    \"*\") val="$(printf '%s' "$val" | sed 's/^"//;s/"$//')" ;;
    \'*\') val="$(printf '%s' "$val" | sed "s/^'//;s/'$//")" ;;
  esac
  if [ -z "$val" ]; then
    printf '%s\n' "$default"
  else
    printf '%s\n' "$val"
  fi
}

load_vars() {
  HOST_PORT="$(env_get HOST_PORT 8002)"
  DOMAIN="$(env_get DOMAIN "$DOMAIN_DEFAULT")"
  SECRET_KEY="$(env_get SECRET_KEY)"
  POSTGRES_PASSWORD="$(env_get POSTGRES_PASSWORD)"
  HEALTH_URL="http://127.0.0.1:${HOST_PORT}/health"
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Required command not found: $1"
    exit 1
  }
}

need_env() {
  if [ ! -f .env ]; then
    echo "Missing .env"
    echo "  cp .env.example .env"
    echo "  Then set SECRET_KEY and POSTGRES_PASSWORD"
    exit 1
  fi
  load_vars
  if [ -z "$SECRET_KEY" ] || [ "$SECRET_KEY" = "dev-only-change-me" ] || [ "$SECRET_KEY" = "change-me-to-a-long-random-string" ]; then
    echo "Set a strong SECRET_KEY in .env  (run: sh deployment.sh secret)"
    exit 1
  fi
  if [ -z "$POSTGRES_PASSWORD" ] || [ "$POSTGRES_PASSWORD" = "almanac" ]; then
    echo "WARNING: set a strong POSTGRES_PASSWORD in .env before production use."
  fi
  if [ -z "$POSTGRES_PASSWORD" ]; then
    echo "Set POSTGRES_PASSWORD in .env"
    exit 1
  fi
}

compose() {
  docker compose "$@"
}

usage() {
  cat <<EOF
Almanac Africa AI — deploy helper  (domain: ${DOMAIN_DEFAULT})

  sh deployment.sh              Run full setup (recommended)
  sh deployment.sh all          Same as above
  sh deployment.sh help

Steps in "all":
  1. docker compose up --build
  2. wait for health on HOST_PORT
  3. nginx HTTP for almanac.africa
  4. certbot TLS
  5. nginx SSL config
  6. prompt to create admin user

Other commands:
  init          Create .env from example
  secret        Print a random SECRET_KEY
  up            Start stack
  down          Stop stack
  restart       Recreate web
  rebuild       Rebuild images + recreate
  ps            Status
  logs [svc]    Tail logs (default web)
  health        Curl health URL
  status        ps + health + recent logs
  shell         Shell in web container
  migrate       flask db upgrade
  create-user   Create SUPER_ADMIN
  newsletters   Send due scheduled newsletters
  nginx-http    Install HTTP nginx site
  certbot       Let's Encrypt for almanac.africa
  nginx-ssl     Install HTTPS nginx site
EOF
}

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

cmd_init() {
  if [ -f .env ]; then
    echo ".env already exists"
  else
    cp .env.example .env
    echo "Created .env"
  fi
  echo "Edit .env:"
  echo "  SECRET_KEY=\$(sh deployment.sh secret)"
  echo "  POSTGRES_PASSWORD=..."
  echo "  HOST_PORT=8002"
  echo "Then: sh deployment.sh"
}

cmd_secret() {
  if command -v python3 >/dev/null 2>&1; then
    python3 -c "import secrets; print(secrets.token_urlsafe(48))"
  elif command -v python >/dev/null 2>&1; then
    python -c "import secrets; print(secrets.token_urlsafe(48))"
  else
    openssl rand -base64 48
  fi
}

cmd_up() {
  need_env
  need_cmd docker
  compose up --build -d
  compose ps
}

cmd_down() {
  need_cmd docker
  compose down
}

cmd_restart() {
  need_env
  compose up -d db
  compose up -d --force-recreate web
  cmd_health
}

cmd_rebuild() {
  need_env
  compose build --no-cache
  compose up -d --force-recreate
  cmd_wait_health
}

cmd_ps() {
  need_cmd docker
  compose ps
}

cmd_logs() {
  svc="${1:-web}"
  compose logs -f --tail=100 "$svc"
}

cmd_health() {
  load_vars
  echo "GET ${HEALTH_URL}"
  curl -fsS "$HEALTH_URL"
  echo
}

cmd_wait_health() {
  load_vars
  echo "Waiting for ${HEALTH_URL} ..."
  i=1
  while [ "$i" -le 60 ]; do
    if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
      echo "Healthy"
      cmd_health
      return 0
    fi
    i=$((i + 1))
    sleep 2
  done
  echo "Health check timed out"
  compose logs web --tail=80
  exit 1
}

cmd_shell() {
  compose exec web sh
}

cmd_migrate() {
  compose exec web flask db upgrade
}

cmd_create_user() {
  compose exec web flask create-user --role SUPER_ADMIN
}

cmd_newsletters() {
  compose exec web flask send-scheduled-newsletters
}

cmd_nginx_http() {
  need_env
  need_cmd nginx
  domain="${1:-$DOMAIN}"
  sudo mkdir -p /var/www/certbot
  sudo cp "$ROOT/deploy/nginx/almanac.http.conf" "$NGINX_AVAIL"
  if [ "$domain" != "almanac.africa" ]; then
    sudo sed -i "s/almanac\\.africa/${domain}/g" "$NGINX_AVAIL"
  fi
  sudo sed -i "s/127\\.0\\.0\\.1:[0-9][0-9]*/127.0.0.1:${HOST_PORT}/g" "$NGINX_AVAIL"
  sudo ln -sf "$NGINX_AVAIL" "$NGINX_ENABLED"
  sudo rm -f /etc/nginx/sites-enabled/default
  sudo nginx -t
  sudo systemctl reload nginx
  echo "nginx HTTP → http://${domain} → 127.0.0.1:${HOST_PORT}"
}

cmd_nginx_ssl() {
  need_env
  need_cmd nginx
  domain="${1:-$DOMAIN}"
  sudo cp "$ROOT/deploy/nginx/almanac.conf" "$NGINX_AVAIL"
  if [ "$domain" != "almanac.africa" ]; then
    sudo sed -i "s/almanac\\.africa/${domain}/g" "$NGINX_AVAIL"
  fi
  sudo sed -i "s/127\\.0\\.0\\.1:[0-9][0-9]*/127.0.0.1:${HOST_PORT}/g" "$NGINX_AVAIL"
  sudo ln -sf "$NGINX_AVAIL" "$NGINX_ENABLED"
  sudo nginx -t
  sudo systemctl reload nginx
  echo "nginx SSL → https://${domain} → 127.0.0.1:${HOST_PORT}"
}

cmd_certbot() {
  need_env
  need_cmd certbot
  domain="${1:-$DOMAIN}"
  sudo certbot --nginx -d "$domain" -d "www.${domain}"
}

cmd_status() {
  load_vars
  cmd_ps
  echo
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    cmd_health
  else
    echo "Health: DOWN (${HEALTH_URL})"
  fi
  echo
  compose logs web --tail=30
}

cmd_all() {
  need_cmd docker
  need_cmd curl
  need_env

  echo "=========================================="
  echo " Almanac deploy → ${DOMAIN}"
  echo " App port       → 127.0.0.1:${HOST_PORT}"
  echo "=========================================="

  echo
  echo "==> 1/5  Docker Compose up"
  compose up --build -d
  cmd_wait_health

  echo
  echo "==> 2/5  nginx HTTP"
  if command -v nginx >/dev/null 2>&1; then
    cmd_nginx_http "$DOMAIN"
  else
    echo "nginx not installed — skip. Install: sudo apt install -y nginx"
  fi

  echo
  echo "==> 3/5  Let's Encrypt (certbot)"
  if command -v certbot >/dev/null 2>&1; then
    cmd_certbot "$DOMAIN" || echo "certbot failed or skipped — fix DNS then: sh deployment.sh certbot"
  else
    echo "certbot not installed — skip. Install: sudo apt install -y certbot python3-certbot-nginx"
  fi

  echo
  echo "==> 4/5  nginx SSL config"
  if command -v nginx >/dev/null 2>&1; then
    if [ -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]; then
      cmd_nginx_ssl "$DOMAIN"
    else
      echo "No cert yet at /etc/letsencrypt/live/${DOMAIN}/ — skip nginx-ssl"
    fi
  fi

  echo
  echo "==> 5/5  Admin user"
  echo "Create the first Super Admin now? [y/N]"
  read -r ans || ans=n
  case "$ans" in
    y|Y|yes|YES) cmd_create_user ;;
    *) echo "Later: sh deployment.sh create-user" ;;
  esac

  echo
  echo "Done."
  echo "  Local health: ${HEALTH_URL}"
  echo "  Site:         https://${DOMAIN}"
  echo "  Status:       sh deployment.sh status"
}

# ---------------------------------------------------------------------------
# Main — no args runs full deploy
# ---------------------------------------------------------------------------

cmd="${1:-all}"
[ "$#" -gt 0 ] && shift

case "$cmd" in
  all|deploy|"")   cmd_all ;;
  init)            cmd_init ;;
  secret)          cmd_secret ;;
  up)              cmd_up ;;
  down)            cmd_down ;;
  restart)         cmd_restart ;;
  rebuild)         cmd_rebuild ;;
  ps)              cmd_ps ;;
  logs)            cmd_logs "$@" ;;
  health)          cmd_health ;;
  status)          cmd_status ;;
  shell)           cmd_shell ;;
  migrate)         cmd_migrate ;;
  create-user)     cmd_create_user ;;
  newsletters)     cmd_newsletters ;;
  nginx-http)      cmd_nginx_http "$@" ;;
  nginx-ssl)       cmd_nginx_ssl "$@" ;;
  certbot)         cmd_certbot "$@" ;;
  -h|--help|help)  load_vars; usage ;;
  *)
    echo "Unknown command: $cmd"
    usage
    exit 1
    ;;
esac
