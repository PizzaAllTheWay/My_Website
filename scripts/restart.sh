#!/usr/bin/env bash
# Restart/enable services that this project uses.
set -Eeuo pipefail

ok()  { printf "\033[1;32m[+]\033[0m %s\n" "$*"; }
warn(){ printf "\033[1;33m[!]\033[0m %s\n" "$*"; }
die() { printf "\033[1;31m[x]\033[0m %s\n" "$*\n" >&2; exit 1; }

unit_known() { systemctl cat "$1" &>/dev/null; }

# --- detect app unit (support both names) ---
APP_UNIT=""
for cand in website.service website.service; do
  if unit_known "$cand"; then APP_UNIT="$cand"; break; fi
done
[[ -n "$APP_UNIT" ]] || die "App unit not found (website.service or website.service). Run scripts/start.sh first."

# --- check what we have; give a heads-up if something is missing ---
MISSING=()
for u in duckdns-update.service duckdns-update.timer "$APP_UNIT" caddy.service; do
  unit_known "$u" || MISSING+=("$u")
done
if ((${#MISSING[@]})); then
  warn "Some units aren’t present: ${MISSING[*]}"
  warn "If this is a fresh machine, run scripts/start.sh first."
fi

# --- reload systemd & clear failed states ---
sudo systemctl daemon-reload
sudo systemctl reset-failed || true

# --- DuckDNS timer + oneshot update ---
if unit_known duckdns-update.timer; then
  ok "Enabling DuckDNS timer"
  sudo systemctl enable --now duckdns-update.timer
else
  warn "duckdns-update.timer not present; skipping"
fi

if unit_known duckdns-update.service; then
  ok "Running one immediate DuckDNS update"
  sudo systemctl restart duckdns-update.service || true
else
  warn "duckdns-update.service not present; skipping"
fi

# --- App (Gunicorn) ---
ok "Ensuring ${APP_UNIT} is enabled and restarting it"
sudo systemctl enable --now "$APP_UNIT"
sudo systemctl restart "$APP_UNIT"

# --- Caddy ---
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
systemctl --no-pager --full status "$APP_UNIT" | sed -n '1,10p' || true
systemctl list-timers '*duckdns*' --no-pager || true
systemctl --no-pager --full status caddy.service 2>/dev/null | sed -n '1,8p' || true
