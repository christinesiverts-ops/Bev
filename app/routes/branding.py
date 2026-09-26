import io

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import branding
from ..common import flash, redirect, render, s
from ..db import get_db
from ..models import Program, User
from ..security import csrf_protect, current_user, log, require_manager

router = APIRouter()


@router.get("/theme.css")
def theme_css():
    st = branding.site()
    body = branding.theme_css(st["primary_color"], st["accent_color"])
    return Response(body, media_type="text/css", headers={"Cache-Control": "no-cache"})


@router.get("/branding/{kind}/{filename}")
def branding_file(kind: str, filename: str):
    if kind not in branding.KINDS or "/" in filename or ".." in filename:
        raise HTTPException(404)
    path = branding.upload_dir(kind) / filename
    if not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, headers={"Cache-Control": "public, max-age=86400"})


@router.post("/account/theme", dependencies=[Depends(csrf_protect)])
async def set_theme(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    form = await request.form()
    theme = s(form.get("theme"))
    if theme not in ("auto", "light", "dark"):
        theme = "auto"
    u = db.get(User, user.id)
    u.theme = theme
    db.commit()
    back = s(form.get("back"))
    return redirect(back if back.startswith("/") and not back.startswith("//") else "/")


@router.get("/admin/branding")
def branding_page(request: Request, user: User = Depends(require_manager), db: Session = Depends(get_db)):
    chains = db.scalars(select(Program.chain).distinct().order_by(Program.chain)).all()
    brands = db.scalars(select(Program.brand).distinct().order_by(Program.brand)).all()
    return render(request, "admin_branding.html", user=user, st=branding.get_settings(db), chains=chains, brands=brands)


@router.post("/admin/branding", dependencies=[Depends(csrf_protect)])
async def branding_save(request: Request, user: User = Depends(require_manager), db: Session = Depends(get_db)):
    form = await request.form()
    name = s(form.get("company_name"))[:80] or branding.DEFAULTS["company_name"]
    primary = s(form.get("primary_color")).upper() or branding.DEFAULTS["primary_color"]
    accent = s(form.get("accent_color")).upper() or branding.DEFAULTS["accent_color"]
    problem = branding.validate_brand_colors(primary, accent)
    if problem:
        raise HTTPException(400, problem)
    for k, v in (("company_name", name), ("primary_color", primary), ("accent_color", accent)):
        branding.set_setting(db, k, v)
    log(db, user, "update", "branding", None, f"{name} {primary} {accent}")
    db.commit()
    branding.invalidate()
    flash(request, "Branding saved.")
    return redirect("/admin/branding")


@router.post("/admin/branding/reset-colors", dependencies=[Depends(csrf_protect)])
def branding_reset(request: Request, user: User = Depends(require_manager), db: Session = Depends(get_db)):
    for k in ("primary_color", "accent_color"):
        branding.set_setting(db, k, branding.DEFAULTS[k])
    db.commit()
    branding.invalidate()
    flash(request, "Colors reset to the default burgundy and amber.")
    return redirect("/admin/branding")


@router.post("/admin/branding/logo", dependencies=[Depends(csrf_protect)])
async def logo_upload(request: Request, user: User = Depends(require_manager), db: Session = Depends(get_db)):
    form = await request.form()
    kind, name = s(form.get("kind")), s(form.get("name"))
    if kind not in branding.KINDS:
        raise HTTPException(400, "Unknown logo type.")
    slug = "logo" if kind == "company" else (branding.brand_slug(name) if kind in ("brands", "products")
                                             else branding.chain_slug(name))
    up = form.get("file")
    if not hasattr(up, "read"):
        raise HTTPException(400, "Choose an image file.")
    raw = await up.read()
    if len(raw) > 8 * 1024 * 1024:
        raise HTTPException(400, "Image is larger than 8 MB.")
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HTTPException(400, "Use a PNG, JPEG or WEBP image. (SVG isn't accepted; export it as PNG.)")
    img = ImageOps.exif_transpose(img)
    dest = branding.upload_dir(kind)
    dest.mkdir(parents=True, exist_ok=True)
    if kind == "products":
        img = img.convert("RGB")
        img.thumbnail((900, 600))
        img.save(dest / f"{slug}.jpg", "JPEG", quality=85, optimize=True)
    else:
        img = img.convert("RGBA")
        img.thumbnail((600, 240))
        img.save(dest / f"{slug}.png", optimize=True)
    if kind == "company":
        branding.set_setting(db, "company_logo", "1")
    log(db, user, "upload", "logo", None, f"{kind}/{slug}")
    db.commit()
    branding.invalidate()
    flash(request, "Logo uploaded.")
    return redirect("/admin/branding#" + kind)


@router.post("/admin/branding/logo/delete", dependencies=[Depends(csrf_protect)])
async def logo_delete(request: Request, user: User = Depends(require_manager), db: Session = Depends(get_db)):
    form = await request.form()
    kind, name = s(form.get("kind")), s(form.get("name"))
    if kind not in branding.KINDS:
        raise HTTPException(400, "Unknown logo type.")
    slug = "logo" if kind == "company" else (branding.brand_slug(name) if kind in ("brands", "products")
                                             else branding.chain_slug(name))
    (branding.upload_dir(kind) / f"{slug}.{branding.KINDS[kind]}").unlink(missing_ok=True)
    if kind == "company":
        branding.set_setting(db, "company_logo", "")
    log(db, user, "delete", "logo", None, f"{kind}/{slug}")
    db.commit()
    branding.invalidate()
    flash(request, "Uploaded logo removed.")
    return redirect("/admin/branding#" + kind)
