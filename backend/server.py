"""
Lightweight backend whose only job is to serve the DepoSync source
package as a direct download link inside the Emergent preview environment.

DepoSync itself is a local PyQt6 desktop app (see /app/DepoSync) and does
not run as a web service. This endpoint exists so the user can grab a
clean .zip of the source without relying on the GitHub sync.
"""
import os
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

app = FastAPI(title="DepoSync Source Delivery")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
ZIP_PATH = os.path.join(STATIC_DIR, "DepoSync_Source.zip")
ZIP_NAME = "DepoSync_Source.zip"


@app.get("/api/")
def health():
    exists = os.path.isfile(ZIP_PATH)
    size = os.path.getsize(ZIP_PATH) if exists else 0
    return {"status": "ok", "package_ready": exists, "package_bytes": size}


@app.get("/api/download")
@app.get("/api/download/DepoSync_Source.zip")
def download():
    if not os.path.isfile(ZIP_PATH):
        return JSONResponse({"error": "package not found"}, status_code=404)
    return FileResponse(ZIP_PATH, media_type="application/zip", filename=ZIP_NAME)


@app.get("/", response_class=HTMLResponse)
def index():
    return """<!doctype html><html><head><meta charset="utf-8">
<title>DepoSync Download</title>
<style>
 body{font-family:system-ui,Segoe UI,Arial;background:#0f1115;color:#e6e9ef;
      display:flex;min-height:100vh;align-items:center;justify-content:center;margin:0}
 .card{max-width:520px;padding:40px;background:#171a21;border:1px solid #262b36;
       border-radius:14px;box-shadow:0 20px 60px rgba(0,0,0,.4)}
 h1{margin:0 0 8px;font-size:24px}
 p{color:#9aa3b2;line-height:1.5}
 a.btn{display:inline-block;margin-top:18px;padding:14px 22px;background:#3b82f6;
       color:#fff;text-decoration:none;border-radius:10px;font-weight:600}
 a.btn:hover{background:#2563eb}
 code{background:#0f1115;padding:2px 6px;border-radius:6px;color:#7dd3fc}
</style></head>
<body><div class="card">
 <h1>DepoSync &mdash; Source Package</h1>
 <p>Clean ZIP of the full Python source (no compiled files). Unzip on your
 Windows PC, run <code>INSTALL.bat</code> once, then <code>DepoSync.bat</code>.</p>
 <a class="btn" href="/api/download/DepoSync_Source.zip" data-testid="download-zip-btn">
   Download DepoSync_Source.zip</a>
</div></body></html>"""
