# MyWebsite

**Live example:** `https://martynassmilingis.duckdns.org`

Serve a tiny Flask app on your own Linux box with **HTTPS** via **Caddy** and a free **DuckDNS** domain.
Services are managed with **systemd**, and certificates auto-renew.

---

## TL;DR (Quick start)

1. **Forward ports 80 & 443** on your router → your server’s LAN IP
   *Tip:* reserve a **static LAN IP** for the server (e.g. `192.168.0.100`). See “Static IP” below.

2. **One-time setup**

```bash
./scripts/start.sh
```

`start.sh` will prompt for:

* **DuckDNS subdomain** (e.g. `myhomebox`, not the full domain)
* **DuckDNS token** (from your DuckDNS dashboard)

3. **Visit your site**

```
https://<your-subdomain>.duckdns.org
```

4. **When you change code/config (or just want to restart hosting)**

```bash
./scripts/restart.sh
```

5. **To stop hosting (and keep it stopped across reboots)**

```bash
./scripts/stop.sh
```

---

## What’s included

```
webpage_ws/
├─ src/                      # Your app code
│  ├─ app.py                 # Flask app (served by Gunicorn)
│  └─ templates/index.html
├─ setupfiles/               # Unit templates and Caddyfile
│  ├─ Caddyfile              # ${DUCK_DOMAIN}.duckdns.org → reverse_proxy 127.0.0.1:8000
│  ├─ duckdns-update.service
│  ├─ duckdns-update.timer
│  └─ website.service        # Gunicorn unit template (filled by start.sh)
└─ scripts/
   ├─ start.sh               # One-time setup / install (prompts for DuckDNS)
   ├─ restart.sh             # Re-apply config & restart services (use after edits)
   ├─ stop.sh                # Stop & disable services (no auto-start on reboot)
   └─ duckdns-update.sh      # IP updater installed to /usr/local/bin (root-only)
```

**Services used:**

* `website.service` — Gunicorn serving Flask on `127.0.0.1:8000`
* `caddy.service` — HTTPS reverse proxy on 80/443 with automatic TLS
* `duckdns-update.timer` + `duckdns-update.service` — keeps DuckDNS pointing at your WAN IP

---

## Common commands

```bash
# live logs
journalctl -u website.service -f
journalctl -u caddy -f
journalctl -u duckdns-update.service -f

# quick status
systemctl status website caddy duckdns-update.timer

# confirm DNS resolves to your WAN IP
dig +short <your-subdomain>.duckdns.org
```

---

## Full configuration (details)

### 1) DuckDNS account, domain & token

1. Sign in at [https://www.duckdns.org](https://www.duckdns.org) and create a **subdomain** (e.g., `myhomebox`).
2. Copy your **token** from the dashboard.
3. Run `./scripts/start.sh` and paste both when prompted.
4. Manual update & logs:

   ```bash
   sudo systemctl start duckdns-update.service
   journalctl -u duckdns-update.service -n 50 --no-pager
   ```

### 2) Give your server a static LAN IP

**Recommended:** DHCP reservation on your router.

* Find Wi-Fi interface name & MAC:

  ```bash
  iw dev | awk '/Interface/{print $2}'
  # suppose it's wlo1
  cat /sys/class/net/wlo1/address
  ```
* In the router UI, map that MAC → `192.168.0.100`.

**Alternative (OS static config):**

* **Ubuntu (netplan):**

  ```yaml
  # /etc/netplan/01-static.yaml
  network:
    version: 2
    renderer: networkd
    wifis:
      wlo1:
        dhcp4: no
        addresses: [192.168.0.100/24]
        routes: [{ to: default, via: 192.168.0.1 }]
        nameservers: { addresses: [192.168.0.1, 1.1.1.1] }
        access-points:
          "YourSSID":
            password: "YourWiFiPassword"
  ```

  Apply:

  ```bash
  sudo netplan generate && sudo netplan apply
  ```

* **NetworkManager:**

  ```bash
  nmcli con show
  nmcli con mod "<wifi-connection>" \
    ipv4.method manual \
    ipv4.addresses 192.168.0.100/24 \
    ipv4.gateway 192.168.0.1 \
    ipv4.dns "192.168.0.1,1.1.1.1"
  nmcli con down "<wifi-connection>" && nmcli con up "<wifi-connection>"
  ```

### 3) Router: Port forwarding & admin

* Forward **TCP 80** and **TCP 443** → your server’s LAN IP (e.g., `192.168.0.100`).
* **Disable remote/WAN admin on 80/443** so your router doesn’t hijack those ports.
* If you have **double NAT** (ISP router + your router), forward on both or bridge the ISP box.
* Test from **mobile data** (not Wi-Fi) to ensure you’re hitting your server.

### 4) First run (one-time)

```bash
cd scripts
./start.sh
```

What it does:

* Installs `python3-venv`, `pip`, `caddy`, `curl`
* Creates `.venv`, installs **Flask** + **Gunicorn**
* Installs `/usr/local/bin/duckdns-update.sh` and writes your **subdomain/token**
* Installs & starts:

  * `website.service`
  * `duckdns-update.timer`
  * `caddy.service`
* Builds `/etc/caddy/Caddyfile` from template (injects your DuckDNS domain)
* Ensures `/var/log/caddy/` exists for access logs
* Exports these system-wide env vars (in `/etc/environment`):

  * `MYWEBSITE_DOMAIN=<subdomain>`
  * `MYWEBSITE_FQDN=<subdomain>.duckdns.org`

### 5) Development workflow

* Edit code in `src/app.py` and templates in `src/templates/`.
* Apply and restart everything:

  ```bash
  ./scripts/restart.sh
  ```
* Logs:

  ```bash
  journalctl -u website.service -f
  journalctl -u caddy -f
  ```

### 6) Firewall (optional)

If **UFW** is active:

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw status
```

---

## Troubleshooting

**Caddy won’t issue certs**

* Ensure ports **80/443** are reachable from the internet (no router UI on those ports, no double NAT).
* From outside your LAN:

  ```bash
  curl -I http://<subdomain>.duckdns.org
  ```

  Expect an HTTP→HTTPS redirect.
* Caddy logs:

  ```bash
  journalctl -u caddy -n 200 --no-pager
  ```

**Gunicorn “No module named ‘app’”**

* The service must run in `/src`. The unit uses:

  ```
  --chdir .../src app:app
  ```

**DuckDNS never updates**

* Check:

  ```bash
  journalctl -u duckdns-update.service -n 50 --no-pager
  dig +short <subdomain>.duckdns.org
  ```

  It should resolve to your WAN IP.

**Can’t reach public domain from inside LAN**

* Some routers lack hairpin NAT. Test on mobile data or access via the LAN IP.

---

## Reset / Remove (manual)

```bash
# stop & disable
sudo systemctl disable --now website.service duckdns-update.timer caddy

# remove units (optional)
sudo rm -f /etc/systemd/system/website.service
sudo rm -f /etc/systemd/system/duckdns-update.service
sudo rm -f /etc/systemd/system/duckdns-update.timer
sudo systemctl daemon-reload

# remove caddy config (optional)
sudo rm -f /etc/caddy/Caddyfile

# remove updater (optional)
sudo rm -f /usr/local/bin/duckdns-update.sh
```

---

## Initialize, restart, stop

```bash
cd scripts
./start.sh     # run once to set everything up
./restart.sh   # after any code/config change, or to bring hosting back up
./stop.sh      # to stop hosting now and across reboots
```

---

## Example

```
https://martynassmilingis.duckdns.org
```

> Keep your DuckDNS token private. It’s stored only in `/usr/local/bin/duckdns-update.sh` with root-only permissions.
