#!/usr/bin/env bash
# Install or update Chain Audit from git, safely.
#
#   scripts/deploy.sh            # deploy the latest commit of the deploy branch
#   scripts/deploy.sh --status   # show what's running and what's available
#
# Steps: backup the database (if running) -> fetch + fast-forward -> build image -> restart ->
# wait for the health check -> if unhealthy, roll back to the previous image and commit.
#
# Env overrides: DEPLOY_BRANCH, CONTAINER (default chain-audit), IMAGE (default chain-audit:latest),
#                BUILD_FLAGS (extra `docker build` flags), HEALTH_TIMEOUT (seconds, default 90)
set -euo pipefail
cd "$(dirname "$0")/.."

BRANCH="${DEPLOY_BRANCH:-claude/beverage-pricing-audit-tool-slcoem}"
CONTAINER="${CONTAINER:-chain-audit}"
IMAGE="${IMAGE:-chain-audit:latest}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-90}"

if docker compose version >/dev/null 2>&1; then COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then COMPOSE=(docker-compose)
else echo "ERROR: neither 'docker compose' nor 'docker-compose' is available." >&2; exit 1; fi

log() { printf '\n==> %s\n' "$*"; }
running() { [ -n "$(docker ps -q --filter "name=^${CONTAINER}$" --filter status=running)" ]; }
health() { docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$CONTAINER" 2>/dev/null || echo missing; }

wait_healthy() {
  local waited=0
  while [ "$waited" -lt "$HEALTH_TIMEOUT" ]; do
    case "$(health)" in
      healthy) return 0 ;;
      unhealthy|exited|dead|missing) [ "$waited" -gt 10 ] && return 1 ;;
    esac
    sleep 3; waited=$((waited + 3))
  done
  return 1
}

if [ "${1:-}" = "--status" ]; then
  git fetch -q origin "$BRANCH"
  echo "Deployed commit : $(git rev-parse --short HEAD) $(git log -1 --format=%s HEAD)"
  echo "Latest on origin: $(git rev-parse --short "origin/$BRANCH") $(git log -1 --format=%s "origin/$BRANCH")"
  echo "Pending commits :"; git log --oneline "HEAD..origin/$BRANCH" | sed 's/^/  /' || true
  echo "Container       : $(health)"
  exit 0
fi

[ -f .env ] || { echo "ERROR: .env is missing. Copy .env.example to .env and fill it in first." >&2; exit 1; }
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "ERROR: local changes to tracked files. Put server-specific settings in .env or" >&2
  echo "       docker-compose.override.yml (untracked), then 'git stash' or 'git checkout -- .'." >&2
  git status --short >&2; exit 1
fi

PREV_COMMIT="$(git rev-parse HEAD)"
FIRST_INSTALL=1; docker image inspect "$IMAGE" >/dev/null 2>&1 && FIRST_INSTALL=0

if running; then
  log "Backing up the database"
  docker exec "$CONTAINER" python -m app.backup
fi

log "Fetching $BRANCH"
git fetch origin "$BRANCH"
if [ "$(git rev-parse --abbrev-ref HEAD)" != "$BRANCH" ]; then
  git checkout -q "$BRANCH" 2>/dev/null || git checkout -q -b "$BRANCH" "origin/$BRANCH"
fi
git merge --ff-only "origin/$BRANCH"
NEW_COMMIT="$(git rev-parse HEAD)"

if [ "$PREV_COMMIT" = "$NEW_COMMIT" ] && [ "$FIRST_INSTALL" = 0 ] && running && [ "$(health)" = healthy ]; then
  log "Already up to date ($(git rev-parse --short HEAD)) and healthy. Nothing to do."
  exit 0
fi
if [ "$PREV_COMMIT" != "$NEW_COMMIT" ]; then
  log "Changes being deployed"; git log --oneline "$PREV_COMMIT..$NEW_COMMIT"
fi

log "Building image"
[ "$FIRST_INSTALL" = 0 ] && docker tag "$IMAGE" "${IMAGE%:*}:previous"
# shellcheck disable=SC2086
docker build -t "$IMAGE" ${BUILD_FLAGS:-} .

log "Starting container"
"${COMPOSE[@]}" up -d --no-build --remove-orphans

log "Waiting for health check"
if wait_healthy; then
  log "Deployed $(git rev-parse --short HEAD): healthy"
  docker image prune -f >/dev/null 2>&1 || true
  exit 0
fi

echo "ERROR: new version is not healthy. Last logs:" >&2
docker logs --tail 40 "$CONTAINER" >&2 || true
if [ "$FIRST_INSTALL" = 1 ]; then
  echo "First install failed; nothing to roll back to. Fix the error above (often .env) and re-run." >&2
  exit 1
fi
log "Rolling back to $(git rev-parse --short "$PREV_COMMIT")"
git reset -q --hard "$PREV_COMMIT"
docker tag "${IMAGE%:*}:previous" "$IMAGE"
"${COMPOSE[@]}" up -d --no-build --remove-orphans
if wait_healthy; then
  echo "Rolled back; the previous version is running and healthy. The failed commit was $(git rev-parse --short "$NEW_COMMIT")." >&2
else
  echo "Rollback is not healthy either. Check 'docker logs $CONTAINER'. Database backups are in the data volume's backups/ folder." >&2
fi
exit 1
