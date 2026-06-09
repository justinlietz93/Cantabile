"""GUI route tests."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("jinja2")

from fastapi.testclient import TestClient

from cantabile.adapters.store.sqlite_store import SqliteStore
from cantabile.domain.models import Playlist, PlaylistEntry, Track
from cantabile.domain.observation import Observation
from cantabile.domain.value_objects import Provenance, TrackId
from cantabile.presentation.gui.app import create_app
from cantabile.shared.settings import Settings


class FakeRunner:
    def __init__(self) -> None:
        self.jobs = []

    def enqueue(self, action, fn, playlist=""):
        job = {"id": "job-1", "action": action, "playlist": playlist, "status": "queued"}
        self.jobs.append(job)
        return job

    def recent(self, limit=12):
        return self.jobs[:limit]

    def snapshot(self, job_id):
        return self.jobs[0]


def test_gui_state_and_export_job_route(tmp_path):
    db = tmp_path / "cantabile.db"
    store = SqliteStore(db)
    tid = TrackId("spotify:track:gui")
    store.upsert_track(Track(tid, "GUI Song", ["Artist"], duration_ms=120000))
    store.upsert_playlist(Playlist("GUI", [PlaylistEntry(0, tid)]))
    store.add_observation(Observation(tid, "tempo", 120.0, Provenance.SPOTIFY))
    store.close()

    settings = Settings(db_path=str(db), reports_dir=str(tmp_path / "reports"))
    runner = FakeRunner()
    client = TestClient(create_app(settings, runner))

    assert client.get("/").status_code == 200
    state = client.get("/api/state?playlist=GUI").json()
    assert state["selected"] == "GUI"
    assert state["report"]["tracks"][0]["title"] == "GUI Song"

    job = client.post("/api/export", data={"playlist": "GUI"}).json()
    assert job["action"] == "export"
    assert job["playlist"] == "GUI"
