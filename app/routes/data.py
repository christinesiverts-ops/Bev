from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from .. import backup, config
from ..common import flash, redirect, render
from ..db import get_db
from ..excel_io import export_workbook, import_plan
from ..models import User
from ..security import csrf_protect, log, require_manager

router = APIRouter()
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/data")
def data_page(request: Request, user: User = Depends(require_manager)):
    backups = sorted(config.BACKUP_DIR.glob("audit-*.db"), reverse=True)[:config.BACKUP_KEEP]
    return render(request, "data.html", user=user, backups=[(b.name, b.stat().st_size) for b in backups])


@router.get("/data/export.xlsx")
def export(user: User = Depends(require_manager), db: Session = Depends(get_db)):
    body = export_workbook(db)
    log(db, user, "export", "workbook", None, "")
    db.commit()
    name = f"chain-audit-export-{datetime.now(config.TIMEZONE):%Y%m%d-%H%M}.xlsx"
    return Response(body, media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/data/stores-template.csv")
def stores_template(user: User = Depends(require_manager)):
    body = ("Chain,Division,Store #,Name,Address,City,State,Zip,Market Unit,Lat,Lng\n"
            "WinCo Foods,,12,WinCo Foods #12,123 Example Ave,Portland,OR,97201,MU-AK ID OR WA,45.5152,-122.6784\n")
    return Response(body, media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="stores-template.csv"'})


@router.post("/data/import-plan", dependencies=[Depends(csrf_protect)])
async def import_plan_route(request: Request, user: User = Depends(require_manager), db: Session = Depends(get_db)):
    form = await request.form()
    up = form.get("file")
    if not hasattr(up, "read"):
        raise HTTPException(400, "Choose an .xlsx file.")
    raw = await up.read()
    if len(raw) > 20 * 1024 * 1024:
        raise HTTPException(400, "File is larger than 20 MB.")
    backup.backup_now()  # safety net before bulk changes
    try:
        stats = import_plan(db, raw, replace_promos=form.get("replace_promos") == "Y")
    except Exception as e:
        db.rollback()
        raise HTTPException(400, f"Import failed, nothing was changed: {e}")
    log(db, user, "import", "plan", None, str(stats))
    db.commit()
    flash(request, "Plan imported: {programs_added} programs added, {programs_updated} updated, {promos_added} promo "
                   "windows loaded, {skipped} rows skipped. A backup was taken first.".format(**stats))
    return redirect("/plan")


@router.post("/data/backup", dependencies=[Depends(csrf_protect)])
def backup_create(request: Request, user: User = Depends(require_manager), db: Session = Depends(get_db)):
    path = backup.backup_now()
    log(db, user, "backup", "database", None, path)
    db.commit()
    flash(request, "Backup created.")
    return redirect("/data")


@router.get("/data/backups/{name}")
def backup_download(name: str, user: User = Depends(require_manager)):
    path = config.BACKUP_DIR / name
    if not name.startswith("audit-") or not name.endswith(".db") or "/" in name or not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, filename=name, media_type="application/octet-stream")
