#!/usr/bin/env bash
# Stop & disable app (website), DuckDNS (timer+service), and Caddy.
set -Eeuo pipefail

ok()   { printf "\033[1;32m[✓]\033[0m %s\n" "$*"; }
note() { printf "\033[1;33m[!]\033[0m %s\n" "$*"; }

unit_known() {
  local u="$1"
  # Loaded means the unit file exists and systemd knows about it
  [[ "$(systemctl show -p LoadState --value "$u" 2>/dev/null || true)" == "loaded" ]]
}

stop_disable() {
  local u="$1"
  if unit_known "$u"; then
    sudo systemctl stop "$u"    2>/dev/null || true
    sudo systemctl disable "$u" 2>/dev/null || true
    sudo systemctl reset-failed "$u" 2>/dev/null || true
    ok "stopped & disabled $u"
  else
    note "$u already off or not present (skipping)"
  fi
}

# 1) App unit (support both names)
APP_UNIT=""
for cand in website.service website.service; do
  if unit_known "$cand"; then APP_UNIT="$cand"; break; fi
done

if [[ -n "$APP_UNIT" ]]; then
  stop_disable "$APP_UNIT"
  # ensure no stray gunicorn keeps listening
  pkill -f 'gunicorn.*website_ws' 2>/dev/null || true
else
  note "website/website service already off or not present (skipping)"
fi

# 2) DuckDNS oneshot + timer (disable timer so it won’t re-enable on boot)
stop_disable duckdns-update.service
stop_disable duckdns-update.timer

# 3) Caddy
stop_disable caddy.service

# 4) Reload unit files once at the end
sudo systemctl daemon-reload

echo
ok "All services are stopped and disabled."
echo "To bring them back later:"
echo "  sudo systemctl enable --now ${APP_UNIT:-website.service} caddy.service duckdns-update.timer"
echo "You can run a one-off DuckDNS update with:"
echo "  sudo systemctl start duckdns-update.service"
