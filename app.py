from fastapi import FastAPI, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pathlib import Path
import json

app = FastAPI()
app.mount(
    "/archives",
    StaticFiles(directory="archives"),
    name="archives"
)

ARCHIVES_FILE = Path("archives.json")


def load_archives():
    if not ARCHIVES_FILE.exists():
        return []

    return json.loads(
        ARCHIVES_FILE.read_text(encoding="utf-8")
    )


@app.get("/", response_class=HTMLResponse)
def home():
    html_file = Path("templates/index.html")
    return html_file.read_text(encoding="utf-8")


@app.post("/search")
def search(url: str = Form(...)):

    archives = load_archives()

    results = []

    for archive in archives:
        if archive["url"].rstrip("/") == url.rstrip("/"):
            results.append(archive)

    return {
        "url": url,
        "results": results
    }
