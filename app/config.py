"""Runtime settings, all read from environment variables (see .env.example)."""
import os
from pathlib import Path
from zoneinfo import ZoneInfo


def _bool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
DB_PATH = DATA_DIR / "audit.db"
PHOTO_DIR = DATA_DIR / "photos"
BACKUP_DIR = DATA_DIR / "backups"

SECRET_KEY = os.environ.get("SECRET_KEY", "")
COOKIE_SECURE = _bool("COOKIE_SECURE", True)
SESSION_HOURS = int(os.environ.get("SESSION_HOURS", "12"))
TIMEZONE = ZoneInfo(os.environ.get("TZ_NAME", "America/Los_Angeles"))

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
SEED_PLAN = _bool("SEED_PLAN", True)

BACKUP_KEEP = int(os.environ.get("BACKUP_KEEP", "14"))
BACKUP_HOUR = int(os.environ.get("BACKUP_HOUR", "2"))      # local hour for the nightly backup
BACKUPS_ENABLED = _bool("BACKUPS_ENABLED", True)

MAX_PHOTO_MB = int(os.environ.get("MAX_PHOTO_MB", "15"))
MAX_LOGIN_FAILURES = 5
LOCKOUT_MINUTES = 15
MIN_PASSWORD_LEN = 10
GPS_FLAG_METERS = int(os.environ.get("GPS_FLAG_METERS", "300"))


def ensure_dirs() -> None:
    for d in (DATA_DIR, PHOTO_DIR, BACKUP_DIR):
        d.mkdir(parents=True, exist_ok=True)

# ---- maps & routing ----
MAP_TILE_URL = os.environ.get("MAP_TILE_URL", "https://tile.openstreetmap.org/{z}/{x}/{y}.png")
MAP_TILE_ATTRIBUTION = os.environ.get("MAP_TILE_ATTRIBUTION", "&copy; OpenStreetMap contributors")
ROAD_FACTOR = float(os.environ.get("ROAD_FACTOR", "1.3"))        # straight-line km x this ~= road km
AVG_SPEED_KMH = float(os.environ.get("AVG_SPEED_KMH", "45"))
STOP_MINUTES = int(os.environ.get("STOP_MINUTES", "25"))          # planned time in each store
GEOCODER = os.environ.get("GEOCODER", "nominatim").strip().lower()   # nominatim | off
GEOCODER_EMAIL = os.environ.get("GEOCODER_EMAIL", "")
LEARN_STORE_GPS_MAX_ACCURACY_M = 150


def tile_origin() -> str:
    from urllib.parse import urlsplit
    u = urlsplit(MAP_TILE_URL.replace("{s}", "a"))
    host = u.netloc.replace("a.", "*.", 1) if "{s}" in MAP_TILE_URL else u.netloc
    return f"{u.scheme}://{host}"

PUBLIC_URL = os.environ.get("PUBLIC_URL", "").rstrip("/")   # e.g. https://audit.example.com (used in invite links)
