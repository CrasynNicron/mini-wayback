from fastapi import FastAPI, Form, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse, Response
from pathlib import Path
import json
import httpx

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


@app.api_route(
    "/wacz/{filename}",
    methods=["GET", "HEAD", "OPTIONS"]
)
async def wacz_proxy(filename: str, request: Request):

    # Procurar o arquivo no nosso catálogo
    archives = load_archives()

    archive = next(
        (
            item
            for item in archives
            if item.get("file") == filename
        ),
        None
    )

    if archive is None:
        return Response(
            content="WACZ não encontrado",
            status_code=404
        )

    download_url = archive.get("download_url")

    if not download_url:
        return Response(
            content="Este arquivo não possui download_url",
            status_code=404
        )

    # CORS necessário para o ReplayWeb.page
    cors_headers = {
        "Access-Control-Allow-Origin": "https://replayweb.page",
        "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
        "Access-Control-Allow-Headers": "*",
        "Access-Control-Expose-Headers": (
            "Content-Length, Content-Range, "
            "Accept-Ranges, Content-Type"
        ),
    }

    # Preflight CORS
    if request.method == "OPTIONS":
        return Response(
            status_code=204,
            headers=cors_headers
        )

    # Repassar Range para o servidor que contém o WACZ
    range_header = request.headers.get("range")

    upstream_headers = {
        "Accept-Encoding": "identity"
    }

    if range_header:
        upstream_headers["Range"] = range_header

    client = httpx.AsyncClient(
        follow_redirects=True,
        timeout=None
    )

    try:
        upstream = await client.send(
            client.build_request(
                request.method,
                download_url,
                headers=upstream_headers
            ),
            stream=True
        )

        response_headers = dict(cors_headers)

        for header in [
            "content-length",
            "content-range",
            "accept-ranges",
            "content-type",
            "etag",
            "last-modified"
        ]:
            value = upstream.headers.get(header)

            if value:
                response_headers[header] = value

        if request.method == "HEAD":
            await upstream.aclose()
            await client.aclose()

            return Response(
                status_code=upstream.status_code,
                headers=response_headers
            )

        async def stream():
            try:
                async for chunk in upstream.aiter_bytes():
                    yield chunk
            finally:
                await upstream.aclose()
                await client.aclose()

        return StreamingResponse(
            stream(),
            status_code=upstream.status_code,
            headers=response_headers
        )

    except Exception as exc:
        await client.aclose()

        return Response(
            content=f"Erro ao obter WACZ: {exc}",
            status_code=502,
            headers=cors_headers
        )
