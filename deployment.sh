#!/usr/bin/env bash
# Almanac Africa AI — VPS deployment helper
# Usage: ./deployment.sh <command> [args]
# Do not run with `sh deployment.sh` — this script requires bash.
if [[ -z "${BASH_VERSION:-}" ]]; then
  echo "Run with bash:  ./deployment.sh <command>"
  echo "Not:            sh deployment.sh"
  exit 1
fi
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

COMPOSE=(docker compose)
DOMAIN_DEFAULT="almanac.africa"
NGINX_SITE="almanac"
NGINX_AVAIL="/etc/nginx/sites-available/${NGINX_SITE}"
NGINX_ENABLED="/etc/nginx/sites-enabled/${NGINX_SITE}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

load_env() {
  if [[ ! -f .env ]]; then
    echo "Missing .env — run: ./deployment.sh init"
    exit 1
  fi

  # Passwords often contain ! $ etc. — turn off nounset + history expansion while sourcing.
  set +u
  set +H
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
  set -u

  HOST_PORT="${HOST_PORT:-8002}"
  DOMAIN="${DOMAIN:-$DOMAIN_DEFAULT}"
  HEALTH_URL="http://127.0.0.1:${HOST_PORT}/health"
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Required command not found: $1"
    exit 1
  }
}

require_env_keys() {
  load_env
  local missing=0
  for key in SECRET_KEY POSTGRES_PASSWORD; do
    if [[ -z "${!key:-}" || "${!key}" == "dev-only-change-me" || "${!key}" == "change-me-to-a-long-random-string" ]]; then
      echo "Set a strong ${key} in .env"
      missing=1
    fi
  done
  if [[ "$missing" -ne 0 ]]; then
    exit 1
  fi
}

usage() {
  cat <<EOF
Almanac Africa AI — deployment helper

Usage: ./deployment.sh <command> [args]

Setup
  init                 Copy .env.example → .env (if missing) and print next steps
  secret               Print a strong SECRET_KEY candidate
  check                Validate .env + docker availability

App (Docker Compose)
  up                   Build and start stack in background
  down                 Stop stack
  restart              Restart web (+ ensure db is up)
  rebuild              Rebuild images and recreate containers
  ps                   Show compose status
  logs [service]       Tail logs (default: web)
  health               Curl local health endpoint
  shell                Open a shell in the web container
  migrate              Run flask db upgrade
  create-user          Create admin (flask create-user --role SUPER_ADMIN)
  newsletters          Process due scheduled newsletters

nginx + TLS  (default domain: almanac.africa)
  nginx-http [domain]  Install HTTP nginx site (proxy → 127.0.0.1:\$HOST_PORT)
  nginx-ssl [domain]   Install full SSL nginx site (after certbot)
  certbot [domain]     Issue Let's Encrypt certs for domain (+ www)

All-in-one
  deploy               require env → up → wait health → print status
  status               ps + health + recent web logs

Examples
  ./deployment.sh init
  ./deployment.sh deploy
  ./deployment.sh create-user
  ./deployment.sh nginx-http
  ./deployment.sh certbot
  ./deployment.sh nginx-ssl
EOF
}

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

cmd_init() {
  if [[ -f .env ]]; then
    echo ".env already exists"
  else
    cp .env.example .env
    echo "Created .env from .env.example"
  fi
  echo
  echo "Edit .env and set at least:"
  echo "  SECRET_KEY=      # ./deployment.sh secret"
  echo "  POSTGRES_PASSWORD="
  echo "  HOST_PORT=8002   # free port on this VPS (maps to the app)"
  echo
  echo "Then: ./deployment.sh deploy"
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

cmd_check() {
  need_cmd docker
  docker compose version >/dev/null
  require_env_keys
  echo "OK — docker + .env look ready (HOST_PORT=${HOST_PORT})"
}

cmd_up() {
  require_env_keys
  "${COMPOSE[@]}" up --build -d
  cmd_ps
}

cmd_down() {
  load_env
  "${COMPOSE[@]}" down
}

cmd_restart() {
  require_env_keys
  "${COMPOSE[@]}" up -d db
  "${COMPOSE[@]}" up -d --force-recreate web
  cmd_health
}

cmd_rebuild() {
  require_env_keys
  "${COMPOSE[@]}" build --no-cache
  "${COMPOSE[@]}" up -d --force-recreate
  cmd_wait_health
  cmd_ps
}

cmd_ps() {
  load_env
  "${COMPOSE[@]}" ps
}

cmd_logs() {
  load_env
  local service="${1:-web}"
  "${COMPOSE[@]}" logs -f --tail=100 "$service"
}

cmd_health() {
  load_env
  echo "GET ${HEALTH_URL}"
  curl -fsS "$HEALTH_URL"
  echo
}

cmd_wait_health() {
  load_env
  echo "Waiting for ${HEALTH_URL} ..."
  local i
  for i in $(seq 1 60); do
    if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
      echo "Healthy"
      cmd_health
      return 0
    fi
    sleep 2
  done
  echo "Health check timed out"
  "${COMPOSE[@]}" logs web --tail=80
  exit 1
}

cmd_shell() {
  load_env
  "${COMPOSE[@]}" exec web bash || "${COMPOSE[@]}" exec web sh
}

cmd_migrate() {
  load_env
  "${COMPOSE[@]}" exec web flask db upgrade
}

cmd_create_user() {
  load_env
  "${COMPOSE[@]}" exec web flask create-user --role SUPER_ADMIN
}

cmd_newsletters() {
  load_env
  "${COMPOSE[@]}" exec web flask send-scheduled-newsletters
}

cmd_nginx_http() {
  load_env
  local domain="${1:-$DOMAIN}"
  need_cmd nginx
  sudo mkdir -p /var/www/certbot
  sudo cp "$ROOT/deploy/nginx/almanac.http.conf" "$NGINX_AVAIL"
  # Keep baked-in almanac.africa; if another domain is passed, rewrite it
  if [[ "$domain" != "almanac.africa" ]]; then
    sudo sed -i "s/almanac\\.africa/${domain}/g" "$NGINX_AVAIL"
  fi
  sudo sed -i "s/127\\.0\\.0\\.1:[0-9]\\+/127.0.0.1:${HOST_PORT}/g" "$NGINX_AVAIL"
  sudo ln -sf "$NGINX_AVAIL" "$NGINX_ENABLED"
  sudo rm -f /etc/nginx/sites-enabled/default
  sudo nginx -t
  sudo systemctl reload nginx
  echo "nginx HTTP site enabled for ${domain} → 127.0.0.1:${HOST_PORT}"
  echo "Visit http://${domain}"
}

cmd_nginx_ssl() {
  load_env
  local domain="${1:-$DOMAIN}"
  need_cmd nginx
  sudo cp "$ROOT/deploy/nginx/almanac.conf" "$NGINX_AVAIL"
  if [[ "$domain" != "almanac.africa" ]]; then
    sudo sed -i "s/almanac\\.africa/${domain}/g" "$NGINX_AVAIL"
  fi
  sudo sed -i "s/127\\.0\\.0\\.1:[0-9]\\+/127.0.0.1:${HOST_PORT}/g" "$NGINX_AVAIL"
  sudo ln -sf "$NGINX_AVAIL" "$NGINX_ENABLED"
  sudo nginx -t
  sudo systemctl reload nginx
  echo "nginx SSL site enabled for ${domain} → 127.0.0.1:${HOST_PORT}"
  echo "Visit https://${domain}"
}

cmd_certbot() {
  load_env
  local domain="${1:-$DOMAIN}"
  need_cmd certbot
  sudo certbot --nginx -d "$domain" -d "www.${domain}"
}

cmd_deploy() {
  require_env_keys
  echo "==> Building and starting Almanac"
  "${COMPOSE[@]}" up --build -d
  cmd_wait_health
  echo
  echo "App is up on ${HEALTH_URL}"
  echo "Create admin:  ./deployment.sh create-user"
  echo "nginx HTTP:    ./deployment.sh nginx-http"
  echo "TLS:           ./deployment.sh certbot"
  echo "nginx SSL:     ./deployment.sh nginx-ssl"
  echo "Site:          https://almanac.africa"
}

cmd_status() {
  load_env
  cmd_ps
  echo
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    cmd_health
  else
    echo "Health: DOWN (${HEALTH_URL})"
  fi
  echo
  "${COMPOSE[@]}" logs web --tail=30
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

cmd="${1:-}"
shift || true

case "$cmd" in
  init)          cmd_init ;;
  secret)        cmd_secret ;;
  check)         cmd_check ;;
  up)            cmd_up ;;
  down)          cmd_down ;;
  restart)       cmd_restart ;;
  rebuild)       cmd_rebuild ;;
  ps)            cmd_ps ;;
  logs)          cmd_logs "$@" ;;
  health)        cmd_health ;;
  shell)         cmd_shell ;;
  migrate)       cmd_migrate ;;
  create-user)   cmd_create_user ;;
  newsletters)   cmd_newsletters ;;
  nginx-http)    cmd_nginx_http "$@" ;;
  nginx-ssl)     cmd_nginx_ssl "$@" ;;
  certbot)       cmd_certbot "$@" ;;
  deploy)        cmd_deploy ;;
  status)        cmd_status ;;
  -h|--help|help|"") usage ;;
  *)
    echo "Unknown command: $cmd"
    echo
    usage
    exit 1
    ;;
esac
