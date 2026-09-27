# Deploying the Chain Audit app

The app runs as one Docker container. It listens on `127.0.0.1:8000`, and your existing **nginx** serves it over HTTPS. All data (the SQLite database, photos and nightly backups) lives in one Docker volume, `audit-data`.

## 1. First install

```bash
git clone <this repo> chain-audit && cd chain-audit
cp .env.example .env
python3 -c "import secrets; print(secrets.token_hex(32))"   # paste into SECRET_KEY
nano .env                                                    # set SECRET_KEY, ADMIN_PASSWORD, TZ_NAME
docker compose up -d --build
docker compose ps            # STATUS should become "healthy"
curl -s http://127.0.0.1:8000/healthz
```

`ADMIN_PASSWORD` must be at least 10 characters, with upper- and lower-case letters and a number. It's only used to create the first manager when the database is empty. You'll be asked to change it at first sign-in, and you can remove it from `.env` afterwards.

## 2. nginx

Add a server block for your domain. If you already have one, add the settings from this block to it. The important lines are `X-Forwarded-Proto`, because sign-in cookies are HTTPS-only, and `client_max_body_size`, because of phone photos.

```nginx
server {
    listen 443 ssl http2;
    server_name audit.yourcompany.com;
    # ssl_certificate / ssl_certificate_key: your existing certificate setup (e.g. certbot)

    client_max_body_size 60m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
server {
    listen 80;
    server_name audit.yourcompany.com;
    return 301 https://$host$request_uri;
}
```

Then run `sudo nginx -t && sudo systemctl reload nginx`. If port 8000 is already taken on the server, set `APP_PORT` in `.env` and point `proxy_pass` at that port.

## 3. First sign-in and team setup

1. Open `https://audit.yourcompany.com` and sign in with `ADMIN_USERNAME` / `ADMIN_PASSWORD`. Choose your own password.
2. Go to **Team → Invite a team member**, create a link for each person and text or email it to them. They set up their own login and report to you. You can also add people directly under **Team & access**.

   Invite links are built from the address people use to reach the app. If that comes out wrong behind a proxy, set `PUBLIC_URL=https://your-domain` in `.env`.

   **Team & access → Add a person** also works for each team member. Pick a role:

   | Role | Can do |
   |---|---|
   | Rep | View the plan; log their own visits, checks, photos and notes; update follow-ups |
   | Manager | Everything, including editing the plan, users and imports |
   | Viewer | Read-only |

   The app shows a temporary password once. Send it to the person privately; they must change it at first sign-in.
3. Go to **Stores → Import list** and upload your store list as CSV or Excel. **Data → CSV template** shows the columns. `Chain` must match the plan's chain names. Latitude and longitude are optional, but they turn on the "checked in far from the store" flag.
4. Open **Branding**: set your company name and colors, and upload your company logo plus ZOA and Naked Life logos. The ZOA and Naked Life logos aren't in the source documents, so both brands show text marks until you upload them.
5. Work through **Data review**. As you confirm 2026 pricing, edit the programs and promo windows in the app, or re-import `Chain_Audit_Tool.xlsx` under **Data → Import plan**.

Reps can add the site to their phone's home screen, where it opens like an app. On iPhone, use Share → Add to Home Screen; on Android, use ⋮ → Add to Home screen.

## Maps

- **Street map.** The map background comes from OpenStreetMap tiles, which each user's browser loads directly. The server doesn't need outbound access for tiles. To use a different tile provider, set `MAP_TILE_URL` and `MAP_TILE_ATTRIBUTION`.
- **Store locations.** Stores get a map location from lat/long in a store import, or automatically from a rep's first accurate GPS check-in there.
- **Address lookup.** Managers can also press **Look up addresses** on the map. This uses OpenStreetMap Nominatim at 1 request per second and needs outbound HTTPS from the server. Set `GEOCODER=off` to disable it.
- **Estimates.** Route times use `STOP_MINUTES` (default 25) and `AVG_SPEED_KMH` (default 45). These are planning estimates; the Navigate button hands off to Google Maps for live traffic.

## 4. Backups

- **Automatic:** a database backup runs every night at `BACKUP_HOUR`, and the newest `BACKUP_KEEP` backups are kept. Backups are listed and downloadable under **Data**.
- **On demand:**
  ```bash
  docker compose exec app python -m app.backup
  ```
- **Off-server copy (recommended):** this includes photos. Schedule it with cron:
  ```bash
  docker run --rm -v chain-audit_audit-data:/data -v "$PWD":/out alpine \
    tar czf /out/audit-data-$(date +%F).tgz -C /data .
  ```
  The volume name is `<folder>_audit-data`. Check it with `docker volume ls`.

**Restore a database backup:**
```bash
docker compose stop app
docker run --rm -v chain-audit_audit-data:/data alpine sh -c \
  "cp /data/backups/audit-YYYYMMDD-HHMMSS.db /data/audit.db && rm -f /data/audit.db-wal /data/audit.db-shm"
docker compose start app
```

## 5. Updating

```bash
cd /path/to/chain-audit
./scripts/deploy.sh --status   # what's deployed vs. what's new
./scripts/deploy.sh            # backup -> pull -> build -> restart -> health check
```

The script backs up the database first. If the new version doesn't pass its health check, it automatically rolls back to the previous image and commit and tells you which commit failed. The database schema is upgraded automatically (additive only), and plan data is only seeded into an empty database, so updates never overwrite your edits.

Keep server-specific settings out of tracked files. Use `.env` for settings, and an untracked `docker-compose.override.yml` for things like a bind-mounted data folder or a proxy network. Otherwise `git pull` will conflict.

## 6. Security notes

- The app port is bound to `127.0.0.1`, so the only way in from the internet is through nginx over HTTPS.
- Passwords are hashed with Argon2. After 5 wrong passwords an account is locked for 15 minutes; a manager can unlock it under **Users**.
- Sessions expire after `SESSION_HOURS`. Deactivating a user or resetting their password signs them out everywhere.
- Every form is CSRF-protected. Photos are re-encoded on upload, which strips location metadata, and are only served to signed-in users.
- **Users → Activity log** records who changed what, and when.
- Keep `SECRET_KEY` private. Changing it signs everyone out.

## Building behind a TLS-inspecting proxy

If `pip install` fails during `docker compose build` with certificate errors, your network re-signs HTTPS traffic. Pass the proxy's CA certificate to the build:

```bash
docker build --secret id=extra_ca,src=/path/to/proxy-ca.crt -t chain-audit:latest .
```
