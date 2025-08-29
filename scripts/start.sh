#!/usr/bin/env bash
# Rebuild everything from scratch: DuckDNS + Flask(Gunicorn) + Caddy
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")"/.. && pwd)"
SETUP="${ROOT}/setupfiles"
SCRIPTS="${ROOT}/scripts"

ok()   { printf "\033[1;32m[+]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[!]\033[0m %s\n" "$*"; }
die()  { printf "\033[1;31m[x]\033[0m %s\n" "$*\n" >&2; exit 1; }
trap 'die "run aborted (line $LINENO)"' ERR

# --- sanity ---
[[ -f "${ROOT}/src/app.py" ]]               || die "src/app.py missing"
[[ -f "${SCRIPTS}/duckdns-update.sh" ]]     || die "scripts/duckdns-update.sh missing"
[[ -f "${SETUP}/website.service" ]]         || die "setupfiles/website.service (template) missing"
[[ -f "${SETUP}/duckdns-update.service" ]]  || die "setupfiles/duckdns-update.service missing"
[[ -f "${SETUP}/duckdns-update.timer" ]]    || die "setupfiles/duckdns-update.timer missing"
[[ -f "${SETUP}/Caddyfile" ]]               || die "setupfiles/Caddyfile missing"

APP_ROOT="$ROOT"
APP_USER="${SUDO_USER:-$USER}"
APP_GROUP="$APP_USER"

# --- nuke old units (stop/disable/remove), keep Caddy installed but we will reload it ---
ok "Stopping & removing previous services"
for u in website.service duckdns-update.timer duckdns-update.service; do
  sudo systemctl disable --now "$u" >/dev/null 2>&1 || true
done
sudo rm -f /etc/systemd/system/website.service \
           /etc/systemd/system/duckdns-update.service \
           /etc/systemd/system/duckdns-update.timer || true
sudo systemctl daemon-reload

# --- deps ---
ok "Installing deps (python3-venv pip curl caddy)"
sudo apt update -y
sudo apt install -y python3-venv python3-pip curl caddy

# --- venv + python deps (fresh or upgrade-in-place) ---
if [[ -d "${ROOT}/.venv" && ! -x "${ROOT}/.venv/bin/python" ]]; then
  rm -rf "${ROOT}/.venv"
fi
if [[ ! -x "${ROOT}/.venv/bin/python" ]]; then
  ok "Creating venv ${ROOT}/.venv"
  python3 -m venv "${ROOT}/.venv"
fi
ok "Installing Flask + Gunicorn"
"${ROOT}/.venv/bin/pip" -q install --upgrade pip
"${ROOT}/.venv/bin/pip" -q install flask gunicorn

# --- prompt for DuckDNS domain/token EVERY run ---
read -rp "DuckDNS subdomain (without .duckdns.org): " DUCK_DOMAIN
DUCK_DOMAIN="$(echo "$DUCK_DOMAIN" | tr '[:upper:]' '[:lower:]')"
[[ "$DUCK_DOMAIN" =~ ^[a-z0-9-]+$ ]] || die "DuckDNS subdomain must be [a-z0-9-] only"

while :; do
  read -rsp "DuckDNS token: " DUCK_TOKEN; echo
  [[ -n "$DUCK_TOKEN" ]] && break
  warn "DuckDNS token cannot be empty"
done

# --- global env vars anyone can use ---
#   MYWEBSITE_DOMAIN=subdomain
#   MYWEBSITE_FQDN=subdomain.duckdns.org
ok "Setting global environment variables in /etc/environment"
sudo sed -i '/^MYWEBSITE_DOMAIN=/d' /etc/environment || true
sudo sed -i '/^MYWEBSITE_FQDN=/d'   /etc/environment || true
echo "MYWEBSITE_DOMAIN=${DUCK_DOMAIN}"        | sudo tee -a /etc/environment >/dev/null
echo "MYWEBSITE_FQDN=${DUCK_DOMAIN}.duckdns.org" | sudo tee -a /etc/environment >/dev/null

# --- install DuckDNS updater script (inject domain/token) ---
ok "Installing DuckDNS updater → /usr/local/bin/duckdns-update.sh"
sudo install -m 0700 -o root -g root "${SCRIPTS}/duckdns-update.sh" /usr/local/bin/duckdns-update.sh

UPD="/usr/local/bin/duckdns-update.sh"
if sudo grep -q '^DUCK_DOMAIN=' "$UPD"; then
  sudo sed -i -E "s/^DUCK_DOMAIN=.*/DUCK_DOMAIN=\"${DUCK_DOMAIN}\"/" "$UPD"
else
  echo "DUCK_DOMAIN=\"${DUCK_DOMAIN}\"" | sudo tee -a "$UPD" >/dev/null
fi
if sudo grep -q '^DUCK_TOKEN=' "$UPD"; then
  sudo sed -i -E "s/^DUCK_TOKEN=.*/DUCK_TOKEN=\"${DUCK_TOKEN}\"/" "$UPD"
else
  echo "DUCK_TOKEN=\"${DUCK_TOKEN}\"" | sudo tee -a "$UPD" >/dev/null
fi
sudo chmod 700 "$UPD"

# --- install systemd units fresh ---
ok "Installing systemd units → /etc/systemd/system"
sudo install -m 0644 "${SETUP}/duckdns-update.service" /etc/systemd/system/duckdns-update.service
sudo install -m 0644 "${SETUP}/duckdns-update.timer"   /etc/systemd/system/duckdns-update.timer

# Render website.service template with dynamic paths/user
TMP_UNIT="$(mktemp)"
sed -e "s|{{APP_ROOT}}|${APP_ROOT}|g" \
    -e "s|{{USER}}|${APP_USER}|g" \
    -e "s|{{GROUP}}|${APP_GROUP}|g" \
    "${SETUP}/website.service" > "${TMP_UNIT}"
sudo install -m 0644 "${TMP_UNIT}" /etc/systemd/system/website.service
rm -f "${TMP_UNIT}"

# --- Caddy config (domain substitution) ---
ok "Installing Caddyfile → /etc/caddy/Caddyfile"
sed "s/\${DUCK_DOMAIN}/${DUCK_DOMAIN}/g" "${SETUP}/Caddyfile" | sudo tee /etc/caddy/Caddyfile >/dev/null
sudo install -d -o caddy -g caddy /var/log/caddy

# --- bring everything up ---
ok "Reloading systemd & starting services"
sudo systemctl daemon-reload
sudo systemctl enable --now duckdns-update.timer
sudo systemctl start duckdns-update.service || true   # immediate IP update
sudo systemctl enable --now website.service

sudo systemctl enable --now caddy
sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo systemctl reload caddy || sudo systemctl restart caddy

# --- firewall (optional) ---
if command -v ufw >/dev/null 2>&1 && sudo ufw status | grep -q "Status: active"; then
  ok "UFW active → allowing 80,443"
  sudo ufw allow 80/tcp || true
  sudo ufw allow 443/tcp || true
fi

# --- status ---
echo
ok "website.service:"
systemctl --no-pager --full status website.service | sed -n '1,12p' || true

ok "duckdns timers:"
systemctl list-timers '*duckdns*' --no-pager || true

ok "caddy:"
systemctl --no-pager --full status caddy | sed -n '1,10p' || true

echo
echo "Visit: https://${DUCK_DOMAIN}.duckdns.org"
echo
echo "Env vars now available system-wide:"
echo "  MYWEBSITE_DOMAIN=${DUCK_DOMAIN}"
echo "  MYWEBSITE_FQDN=${DUCK_DOMAIN}.duckdns.org"
echo
echo "Logs:"
echo "  journalctl -u website.service -f"
echo "  journalctl -u duckdns-update.service -f"
echo "  journalctl -u caddy -f"
