#!/usr/bin/env bash
# Restart app stack, ensure deps, apply DB migrations, then restart services.
set -Eeuo pipefail

ok()  { printf "\033[1;32m[+]\033[0m %s\n" "$*"; }
warn(){ printf "\033[1;33m[!]\033[0m %s\n" "$*"; }
die() { printf "\033[1;31m[x]\033[0m %s\n" "$*\n" >&2; exit 1; }
unit_known() { systemctl cat "$1" &>/dev/null; }



# --- paths (repo-aware) ---
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APPDIR="$ROOT/src"
VENV="$ROOT/.venv"
PY="$VENV/bin/python"
PIP="$VENV/bin/pip"
FLASK="$VENV/bin/flask"
REQ="$APPDIR/requirements.txt"



# --- sanity checks ---
[[ -x "$PY" ]]     || die "Python venv missing at $PY (run scripts/start.sh first)."
[[ -d "$APPDIR" ]] || die "App dir missing at $APPDIR"
[[ -f "$REQ"    ]] || die "Missing requirements.txt at $REQ"



# --- detect app unit (your name) ---
APP_UNIT=""
for cand in website.service website.service; do
  if unit_known "$cand"; then APP_UNIT="$cand"; break; fi
done
[[ -n "$APP_UNIT" ]] || die "App unit not found. Run scripts/start.sh first."



# --- optional other units (unchanged) ---
MISSING=()
for u in duckdns-update.service duckdns-update.timer "$APP_UNIT" caddy.service; do
  unit_known "$u" || MISSING+=("$u")
done
((${#MISSING[@]})) && { warn "Some units aren’t present: ${MISSING[*]}"; warn "If fresh machine, run scripts/start.sh first."; }



# --- reload systemd & clear failed states ---
sudo systemctl daemon-reload
sudo systemctl reset-failed || true



# --- DuckDNS timer + one-shot update (if present) ---
if unit_known duckdns-update.timer; then
  ok "Enabling DuckDNS timer"; sudo systemctl enable --now duckdns-update.timer
else warn "duckdns-update.timer not present; skipping"; fi

if unit_known duckdns-update.service; then
  ok "Running immediate DuckDNS update"; sudo systemctl restart duckdns-update.service || true
else warn "duckdns-update.service not present; skipping"; fi



# --- Ensure Python deps ---
ok "Installing/Updating Python dependencies from requirements.txt"
"$PY" -m pip install --upgrade pip wheel setuptools
"$PIP" install -r "$REQ"



# --- Stop app before DB ops (avoid SQLite locks) ---
ok "Stopping $APP_UNIT before DB migration"
sudo systemctl stop "$APP_UNIT" || true



# --- Initialize / upgrade the database schema (Flask-Migrate/Alembic) ---
ok "Initializing / upgrading database schema"

# Make sure required env vars are in *this* process env
export DUCK_DOMAIN="$(grep -E '^DUCK_DOMAIN=' /etc/environment | cut -d= -f2-)"
export WEBSITE_SECRET_KEY="$(grep -E '^WEBSITE_SECRET_KEY=' /etc/environment | cut -d= -f2-)"
[[ -n "$DUCK_DOMAIN" ]] || warn "DUCK_DOMAIN not found in /etc/environment"
[[ -n "$WEBSITE_SECRET_KEY" ]] || die "WEBSITE_SECRET_KEY not found in /etc/environment"

# Enforce single instance dir under src/ (move any stray DB then remove root/instance)
SRC_INST="${ROOT}/src/instance"
ROOT_INST="${ROOT}/instance"
mkdir -p "$SRC_INST"
if [[ -f "${ROOT_INST}/site.db" ]]; then
  ok "Moving DB from root/instance -> src/instance"
  mv "${ROOT_INST}/site.db" "${SRC_INST}/"
fi
# remove root-level instance if empty
rmdir "${ROOT_INST}" 2>/dev/null || true

# Stop app before DB ops (avoid SQLite locks)
ok "Stopping $APP_UNIT before DB migration"
sudo systemctl stop "$APP_UNIT" || true

# Work inside src/ so imports like `from models...` resolve as expected
pushd "${ROOT}/src" >/dev/null

# Nuke any ambient settings that might force Flask to import 'src.app'
unset FLASK_APP FLASK_RUN_FROM_CLI PYTHONPATH

# Always target the app factory in app.py explicitly
APPARG=(--app app:create_app)

# First-time: create Alembic folder + baseline migration from current models
if [[ ! -d migrations ]]; then
  ok "Creating migrations/ (Alembic) and baseline revision from current models"
  "$PY" -m flask "${APPARG[@]}" db init
  "$PY" -m flask "${APPARG[@]}" db migrate -m "baseline"
fi

# Apply pending migrations (safe to run every time)
"$PY" -m flask "${APPARG[@]}" db upgrade

popd >/dev/null



# --- SMTP env for this process (so any CLI/mail in this run sees them) ---
# Pull from /etc/environment; keep quiet if missing
for k in SMTP_HOST SMTP_PORT SMTP_USER SMTP_PASS SMTP_FROM; do
  v="$(grep -E "^${k}=" /etc/environment | cut -d= -f2- || true)"
  [[ -n "$v" ]] && export "${k}=${v}"
done

# Sensible Gmail defaults if not set (you configured these in start.sh)
: "${SMTP_HOST:=smtp.gmail.com}"
: "${SMTP_PORT:=587}"
# If FROM unset but USER present, default FROM to USER
if [[ -z "${SMTP_FROM:-}" && -n "${SMTP_USER:-}" ]]; then
  export SMTP_FROM="${SMTP_USER}"
fi

# Quick visibility (no secrets printed)
[[ -n "${SMTP_USER:-}" ]] || warn "SMTP_USER missing (emails will fall back to DEV print)."
[[ -n "${SMTP_PASS:-}" ]] || warn "SMTP_PASS missing (emails will fall back to DEV print)."



# --- App (Gunicorn) ---
ok "Ensuring ${APP_UNIT} is enabled and restarting it"
sudo systemctl enable --now "$APP_UNIT"
sudo systemctl restart "$APP_UNIT"



# --- Caddy (if present) ---
if unit_known caddy.service; then
  ok "Ensuring caddy.service is enabled and reloading it"
  sudo systemctl enable --now caddy.service
  sudo systemctl reload caddy.service || sudo systemctl restart caddy.service
else
  warn "caddy.service not present; skipping"
fi



# --- quick status ---
echo
ok "Status:"
systemctl --no-pager --full status "$APP_UNIT" | sed -n '1,12p' || true
systemctl list-timers '*duckdns*' --no-pager || true
systemctl --no-pager --full status caddy.service 2>/dev/null | sed -n '1,8p' || true
