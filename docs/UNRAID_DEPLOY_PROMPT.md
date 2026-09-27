You are deploying and maintaining **Chain Audit**, a self-hosted Docker web app, on an **Unraid** server that you reach over SSH. The server belongs to Roux. It runs other things too, so be careful and conservative. Do not change anything outside what's listed here without asking.

## The app
- Repo (private): `git@github.com:christinesiverts-ops/Bev.git`, branch `claude/beverage-pricing-audit-tool-slcoem`. A read-only GitHub deploy key for this repo is already set up on the server; find where Roux stored it and use it for all git operations.
- One container, `chain-audit`, built from the repo's `Dockerfile` and started by `docker-compose.yml`. It serves plain HTTP on port **8000**, published only on `127.0.0.1:${APP_PORT:-8000}`. It has a health check at `GET /healthz`.
- The compose file already sets `mem_limit: 512m`, `cpus: 1.0` and `pids_limit: 200`, plus a read-only root filesystem, `cap_drop: ALL` and `no-new-privileges`. **Never** add `privileged`, `network_mode: host`, a `/var/run/docker.sock` mount or `cap_add`.
- All data lives in one volume: the SQLite database, photos, uploaded logos and nightly backups.
- `scripts/deploy.sh` does every install and update safely:
  1. back up the database
  2. fast-forward to the branch
  3. build the image
  4. restart
  5. wait for the health check
  6. roll back automatically to the previous image and commit if the new version is unhealthy

  `scripts/deploy.sh --status` shows the deployed commit next to the latest one. Read `docs/DEPLOY.md` in the repo before you start.

## Ground rules
- **Never print, log or paste secrets** (`SECRET_KEY`, `ADMIN_PASSWORD`, private keys) into chat or command output. Generate them on the server and write them only to files readable by root alone.
- **Never edit tracked files in the repo.** Server-specific settings go in `.env` and in an untracked `docker-compose.override.yml`; both are gitignored. Never commit or push.
- **Don't expose the app port directly** to the LAN or internet. Only the reverse proxy should reach it.
- **Ask before** you install packages or plugins on Unraid, change the reverse proxy's global config, or restart anything other than `chain-audit` and the proxy reload.

## First deployment

### 1. Check the server
Report the Unraid version and:
- `docker version`
- `docker compose version`; if it's missing, check for `docker-compose` or the "Docker Compose Manager" plugin
- `git --version`; if git is missing, stop and ask Roux how he wants it provided
- free space on `/mnt/user/appdata`

### 2. Clone
```bash
cd /mnt/user/appdata
GIT_SSH_COMMAND="ssh -i <deploy key path> -o IdentitiesOnly=yes" \
  git clone -b claude/beverage-pricing-audit-tool-slcoem git@github.com:christinesiverts-ops/Bev.git chain-audit
cd chain-audit
git config core.sshCommand "ssh -i <deploy key path> -o IdentitiesOnly=yes"
```
Unraid's `/root` lives in RAM. Make sure the deploy key and any `~/.ssh` config will survive a reboot (for example, keep them under `/boot/config/ssh/` or `/mnt/user/appdata/`), and tell Roux where they are.

### 3. Store data on the array, not inside docker.img
Create `/mnt/user/appdata/chain-audit-data`, run `chown -R 10001:10001` on it (the container runs as uid 10001), and create `docker-compose.override.yml`:
```yaml
services:
  app:
    volumes:
      - /mnt/user/appdata/chain-audit-data:/data
```

### 4. Create `.env`
Run `cp .env.example .env && chmod 600 .env`, then set:
- `SECRET_KEY`: generate it with `python3 -c "import secrets; print(secrets.token_hex(32))"`, or `openssl rand -hex 32` if Python isn't available.
- `ADMIN_USERNAME=manager`
- `ADMIN_PASSWORD`: generate a strong one. It needs at least 10 characters, upper- and lower-case letters and a number. Also write it to `/mnt/user/appdata/chain-audit/INITIAL_ADMIN_PASSWORD.txt` with `chmod 600`, and tell Roux where it is. Do **not** show it. The user must change it at first sign-in.
- `TZ_NAME`: ask if unknown; the team is on US Pacific time, so `America/Los_Angeles` is the default.
- `APP_PORT`: keep 8000 unless it's taken on the host. Check with `ss -ltn`.
- `PUBLIC_URL=https://<the domain Roux gives you>`

### 5. Set up the reverse proxy
Find out which proxy Roux uses and where it runs.
- **nginx on the host:** proxy the domain to `http://127.0.0.1:8000`.
- **nginx in a container** (Nginx Proxy Manager, SWAG, etc.): `127.0.0.1` on the host isn't reachable from inside that container. In `docker-compose.override.yml`, attach `app` to the proxy's existing Docker network (declare it `external: true`) and proxy to `http://chain-audit:8000`. Keep the loopback-only port mapping.

The proxy must:
- serve HTTPS
- set `Host`, `X-Forwarded-For` and **`X-Forwarded-Proto`**; without the last one, sign-in cookies won't stick
- allow `client_max_body_size 60m` for photo uploads

`docs/DEPLOY.md` has a sample nginx block. Show Roux the proxy change before you apply it.

### 6. Deploy
Run `./scripts/deploy.sh`. It should end with `Deployed <commit>: healthy`.

### 7. Verify
- `curl -s http://127.0.0.1:<APP_PORT>/healthz` returns `{"ok":true}`.
- `curl -sI https://<domain>/login` returns 200, and the response includes `content-security-policy`.
- Signing in over HTTPS works. Check that the `audit_session` cookie is set with `Secure`; you can confirm this with curl using the login form's CSRF token, without printing the password.
- Memory use is well under 512 MB: `docker stats --no-stream chain-audit`.
- Backups land in `/mnt/user/appdata/chain-audit-data/backups`: `docker exec chain-audit python -m app.backup`.

### 8. Optional: an "Update Chain Audit" button
If the Unraid **User Scripts** plugin is installed, add a script that runs:
```bash
cd /mnt/user/appdata/chain-audit && ./scripts/deploy.sh
```
Set it to run manually, not on a schedule, so updates only happen when someone presses it. Ask Roux first.

## Updating (every time the owner says there are changes)
1. `cd /mnt/user/appdata/chain-audit && ./scripts/deploy.sh --status`: report which commits are pending.
2. `./scripts/deploy.sh`.
3. If it reports **healthy**: confirm with the checks from step 7 (healthz, HTTPS login page) and report the new commit plus the one-line summaries of what changed.
4. If it **rolled back**: report the failing commit, the error from the logs it printed, and confirm the previous version is healthy again. Don't retry, and don't edit code on the server. The fix has to come from the repo.
5. If it refuses because of local changes: show `git status`, move any server-specific edits into `.env` or `docker-compose.override.yml`, and ask before discarding anything.

## If something goes wrong
- Container logs: `docker logs --tail 100 chain-audit`
- Nightly database backups are in the data folder under `backups/`. To restore one, follow "Restore a database backup" in `docs/DEPLOY.md` (stop the app, copy the backup over `audit.db`, delete the `-wal` and `-shm` files, start the app). Ask before restoring.
- Database changes are additive only, so an older version of the app runs fine against a newer database. Rolling back the code is safe.

## Report back after each run, briefly
- the commit deployed, or rolled back from
- the health status
- the URL
- where the initial admin password file is (first install only)
- anything you need from Roux or the owner
