import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from . import backup, config, db
from .common import redirect, render
from .migrate import upgrade
from .routes import admin, auth, branding, wins, dashboard, data, home, issues, plan, stores, tasks, visits
from .security import LoginRequired, PasswordChangeRequired
from .seed import ensure_admin, seed_plan

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_app(db_url: str | None = None, start_background: bool = True) -> FastAPI:
    if not config.SECRET_KEY or len(config.SECRET_KEY) < 32:
        raise SystemExit("SECRET_KEY must be set to a random string of at least 32 characters.")

    @asynccontextmanager
    async def lifespan(_app):
        engine = db.init_engine(db_url)
        upgrade(engine)
        with db.SessionLocal() as s:
            ensure_admin(s)
            if config.SEED_PLAN:
                seed_plan(s)
        if start_background and config.BACKUPS_ENABLED:
            backup.start_scheduler()
        yield

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY, session_cookie="audit_session",
                       max_age=config.SESSION_HOURS * 3600, same_site="lax", https_only=config.COOKIE_SECURE)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        resp.headers.setdefault("Permissions-Policy", "geolocation=(self), camera=(self), microphone=()")
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; "
            "form-action 'self'; frame-ancestors 'none'; base-uri 'self'")
        if request.url.path.startswith(("/photos/", "/data/")):
            resp.headers["Cache-Control"] = "private, no-store"
        return resp

    @app.exception_handler(LoginRequired)
    async def _login(request: Request, _exc):
        nxt = request.url.path if request.method == "GET" else "/"
        return redirect(f"/login?next={nxt}")

    @app.exception_handler(PasswordChangeRequired)
    async def _pw(_request: Request, _exc):
        return redirect("/account/password")

    @app.exception_handler(HTTPException)
    async def _http(request: Request, exc: HTTPException):
        if exc.status_code == 404 and not exc.detail:
            exc.detail = "Not found."
        return render(request, "error.html", status_code=exc.status_code, code=exc.status_code, message=exc.detail)

    @app.exception_handler(RequestValidationError)
    async def _invalid(request: Request, _exc):
        return render(request, "error.html", status_code=400, code=400, message="That link or form wasn't valid.")

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")
    for r in (branding, auth, home, wins, plan, stores, visits, issues, tasks, dashboard, admin, data):
        app.include_router(r.router)
    return app
