"""Server entrypoint for the local browser GUI."""

from __future__ import annotations

import threading
import webbrowser

import uvicorn

from cantabile.presentation.gui.app import create_app
from cantabile.shared.settings import Settings


def run_gui(settings: Settings, host: str, port: int, open_browser: bool) -> None:
    """Run the local GUI server."""

    url = f"http://{host}:{port}"
    app = create_app(settings)
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    print(f"Cantabile GUI running at {url}")
    uvicorn.run(app, host=host, port=port, log_level="info")
