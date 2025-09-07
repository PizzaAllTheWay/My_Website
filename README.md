Here’s a cleaned-up, newbie-friendly README with collapsible sections and a clickable live link. I replaced “TL;DR” with “Quick start” and kept the rest concise but expandable.

---

# MyWebsite

**My Website:** [**https://martynassmilingis.duckdns.org**](https://martynassmilingis.duckdns.org)

Self-host a tiny Flask app with **HTTPS** via **Caddy** and a free **DuckDNS** domain.
Services run under **systemd** and certificates auto-renew.

---

## Quick start

1. **Forward ports 80 & 443** on your router → your server’s LAN IP
   *Tip:* reserve a **static LAN IP** (e.g. `192.168.0.100`). See “Static IP” below.

2. **One-time setup**

```bash
./scripts/start.sh
```

You’ll be prompted for:

- **DuckDNS subdomain** — e.g. `myhomebox` (just the name, not the full domain)
- **DuckDNS token** — from your DuckDNS dashboard
- **WEBSITE_SECRET_KEY** — leave empty to auto-generate a secure 64-hex key (or paste your own)
- **Gmail address** — the sender for password reset emails (**must be Gmail**)
- **Gmail 16-char App Password** — Google “App Password” for that Gmail (**not** your normal password)

3. **Visit your site**

```
https://<your-subdomain>.duckdns.org
```

4. **After code/config changes (or to bring hosting back up)**

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

**Services used**

* `website.service` — Gunicorn serving Flask on `127.0.0.1:8000`
* `caddy.service` — HTTPS reverse proxy on 80/443 with automatic TLS
* `duckdns-update.timer` + `duckdns-update.service` — keeps DuckDNS pointing at your WAN IP

---

<details>
<summary><strong>DuckDNS: account, domain & token</strong></summary>

1. Sign in at [https://www.duckdns.org](https://www.duckdns.org) and create a **subdomain** (e.g. `myhomebox`).
2. Copy your **token** from the dashboard.
3. Run `./scripts/start.sh` and paste both when prompted.
4. Manual update & logs:

   ```bash
   sudo systemctl start duckdns-update.service
   journalctl -u duckdns-update.service -n 50 --no-pager
   ```

</details>

<details>
<summary><strong>Gmail App Password: how to create & use</strong></summary>

**Prereqs**
- Your Google account must have **2-Step Verification** enabled.

**Create an App Password**
1. Open: <https://myaccount.google.com/security>
2. Under **“Signing in to Google”**, click **App passwords**.  
   (If you don’t see it, enable 2-Step Verification first.)
3. In **Select app**, choose **Mail** (or “Other” and type a name, e.g. `My_Website`).
4. In **Select device**, pick your device (or “Other”).
5. Click **Generate**.
6. Copy the **16-character password** (looks like `xxxx xxxx xxxx xxxx`).  
   **Use it without spaces** when pasting into the setup prompt.

**Use it in this project**
- When you run `./scripts/start.sh`, you’ll be prompted for:
  - **Gmail address** (sender): e.g. `you@gmail.com`
  - **Gmail 16-char App Password**: paste the code **without spaces**
- The script saves these to `/etc/environment` as:
  - `SMTP_HOST=smtp.gmail.com`
  - `SMTP_PORT=587`
  - `SMTP_USER=<your gmail>`
  - `SMTP_PASS=<your app password>`
  - `SMTP_FROM=<your gmail>`

**Quick test (optional)**
```bash
# One-shot test without saving anything:
SMTP_HOST="smtp.gmail.com" \
SMTP_PORT="587" \
SMTP_USER="your@gmail.com" \
SMTP_PASS="xxxxxxxxxxxxxxxx" \
SMTP_FROM="your@gmail.com" \
python - <<'PY'
from utils.mailer import send_email
send_email("your@gmail.com", "SMTP test", "Hello via Gmail SMTP")
print("Sent (if no exception). Check your inbox.")
PY
```
</details>

<details>
<summary><strong>Static IP on your LAN</strong></summary>

**Recommended (easy):** DHCP reservation on your router.

* Find your Wi-Fi interface & MAC:

  ```bash
  iw dev | awk '/Interface/{print $2}'
  # assume wlo1
  cat /sys/class/net/wlo1/address
  ```
* In the router UI, map that MAC → `192.168.0.100`.

**Alternative (OS static config, Ubuntu/netplan):**

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

</details>

<details>
<summary><strong>Router: port forwarding & admin</strong></summary>

* Forward **TCP 80** and **TCP 443** → your server’s LAN IP (e.g. `192.168.0.100`).
* **Disable remote/WAN admin** on 80/443 so the router doesn’t hijack those ports.
* If you have **double NAT** (ISP router + your router), forward on both or bridge the ISP box.
* Test from **mobile data** (not Wi-Fi) to ensure you’re hitting your server.

</details>

<details>
<summary><strong>How it works</strong></summary>

* **Gunicorn** runs the Flask app (`app:app`) on `127.0.0.1:8000`.
* **Caddy** terminates TLS on 80/443 and reverse-proxies to Gunicorn.
* **DuckDNS** binds your subdomain to your public IP via a short timer.
* `start.sh` also exports (system-wide) in `/etc/environment`:

  * `MYWEBSITE_DOMAIN=<subdomain>`
  * `MYWEBSITE_FQDN=<subdomain>.duckdns.org`

</details>

<details>
<summary><strong>Common commands</strong></summary>

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

</details>

<details>
<summary><strong>Troubleshooting</strong></summary>

**Caddy won’t issue certs**

* Ensure ports **80/443** are reachable from the internet (no router UI, no double NAT).
* From outside your LAN:

  ```bash
  curl -I http://<subdomain>.duckdns.org
  ```

  Expect an HTTP→HTTPS redirect.
* Logs:

  ```bash
  journalctl -u caddy -n 200 --no-pager
  ```

**Gunicorn “No module named ‘app’”**

* The unit must run in `/src`. It uses:

  ```
  --chdir .../src app:app
  ```

**DuckDNS never updates**

* Check:

  ```bash
  journalctl -u duckdns-update.service -n 50 --no-pager
  dig +short <subdomain>.duckdns.org
  ```

  It should resolve to your **WAN IP**.

**Can’t reach public domain from inside LAN**

* Some routers lack hairpin NAT. Test on mobile data or use the LAN IP.

</details>

<details>
<summary><strong>Reset / remove (manual)</strong></summary>

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

</details>

---

### Initialize, restart, stop

```bash
cd scripts
./start.sh     # run once to set everything up
./restart.sh   # after any code/config change, or to bring hosting back up
./stop.sh      # to stop hosting now and across reboots
```

> Keep your DuckDNS token private. It’s stored only in `/usr/local/bin/duckdns-update.sh` with root-only permissions.
