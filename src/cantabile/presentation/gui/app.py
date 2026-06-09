"""FastAPI application for the local Cantabile GUI."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from cantabile.presentation.gui import actions
from cantabile.presentation.gui.jobs import JobRunner
from cantabile.shared.settings import Settings

_HERE = Path(__file__).resolve().parent


def create_app(settings: Settings | None = None, runner: JobRunner | None = None) -> FastAPI:
    """Build the local GUI app."""

    cfg = settings or Settings()
    jobs = runner or JobRunner()
    app = FastAPI(title="Cantabile Analysis Studio", docs_url=None, redoc_url=None)
    app.state.settings = cfg
    app.state.jobs = jobs

    reports_dir = Path(cfg.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=_HERE / "static"), name="static")
    app.mount("/generated", StaticFiles(directory=reports_dir), name="generated")
    templates = Jinja2Templates(directory=_HERE / "templates")

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"app_name": "Cantabile Analysis Studio"},
        )

    @app.get("/api/state")
    async def state(playlist: str = "") -> dict[str, Any]:
        payload = actions.gui_state(cfg, playlist)
        payload["jobs"] = jobs.recent()
        return payload

    @app.get("/api/track")
    async def track(playlist: str, seq: int) -> dict[str, Any]:
        try:
            return actions.gui_track(cfg, playlist, seq)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/jobs")
    async def list_jobs() -> dict[str, Any]:
        return {"jobs": jobs.recent()}

    @app.get("/api/jobs/{job_id}")
    async def get_job(job_id: str) -> dict[str, Any]:
        try:
            return jobs.snapshot(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Job not found.") from exc

    @app.post("/api/import")
    async def import_csv(file: UploadFile = File(...)) -> dict[str, Any]:
        path = await _save_upload(file)
        return jobs.enqueue("import", lambda log: actions.import_csv(path, cfg, log))

    @app.post("/api/fetch")
    async def fetch(
        playlist: str = Form(...),
        dry_run: bool = Form(False),
        no_suggest: bool = Form(False),
        overrides_text: str = Form(""),
    ) -> dict[str, Any]:
        return jobs.enqueue(
            "fetch",
            lambda log: actions.fetch_playlist(
                playlist, cfg, dry_run, no_suggest, overrides_text, log
            ),
            playlist,
        )

    @app.post("/api/lyrics")
    async def lyrics(playlist: str = Form(...), force: bool = Form(False)) -> dict[str, Any]:
        return jobs.enqueue(
            "lyrics",
            lambda log: actions.analyze_lyrics(playlist, cfg, force, log),
            playlist,
        )

    @app.post("/api/mir")
    async def mir(playlist: str = Form(...), force: bool = Form(False)) -> dict[str, Any]:
        return jobs.enqueue(
            "mir",
            lambda log: actions.analyze_mir(playlist, cfg, force, log),
            playlist,
        )

    @app.post("/api/separate")
    async def separate(
        playlist: str = Form(...),
        force: bool = Form(False),
        model: str = Form(""),
        segment: str = Form(""),
        two_stems: str = Form(""),
        out: str = Form(""),
    ) -> dict[str, Any]:
        try:
            segment_value = float(segment) if segment.strip() else None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Segment must be a number.") from exc
        return jobs.enqueue(
            "separate",
            lambda log: actions.separate_stems(
                playlist, cfg, force, model, segment_value, two_stems, out, log
            ),
            playlist,
        )

    @app.post("/api/export")
    async def export(playlist: str = Form(...), out: str = Form("")) -> dict[str, Any]:
        return jobs.enqueue(
            "export",
            lambda log: actions.export_playlist(playlist, cfg, out, log),
            playlist,
        )

    return app


async def _save_upload(file: UploadFile) -> Path:
    suffix = Path(file.filename or "playlist.csv").suffix or ".csv"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        return Path(tmp.name)
