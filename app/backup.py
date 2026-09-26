"""SQLite online backups. Run manually with:  python -m app.backup"""
import logging
import sqlite3
import threading
import time
from datetime import datetime

from . import config

log = logging.getLogger("audit.backup")


def backup_now() -> str:
    config.ensure_dirs()
    stamp = datetime.now(config.TIMEZONE).strftime("%Y%m%d-%H%M%S")
    dest = config.BACKUP_DIR / f"audit-{stamp}.db"
    src = sqlite3.connect(config.DB_PATH)
    dst = sqlite3.connect(dest)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
    old = sorted(config.BACKUP_DIR.glob("audit-*.db"))[:-config.BACKUP_KEEP]
    for f in old:
        f.unlink(missing_ok=True)
    log.info("Backup written: %s", dest.name)
    return str(dest)


def _loop():
    last_day = None
    while True:
        now = datetime.now(config.TIMEZONE)
        if now.hour == config.BACKUP_HOUR and now.date() != last_day:
            try:
                backup_now()
                last_day = now.date()
            except Exception:  # keep the thread alive
                log.exception("Nightly backup failed")
        time.sleep(300)


def start_scheduler() -> None:
    threading.Thread(target=_loop, name="nightly-backup", daemon=True).start()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(backup_now())
