# api/main.py
from __future__ import annotations

import uuid
import zipfile
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import subprocess
import requests
import os
import re
import mimetypes
from urllib.parse import urlparse, parse_qs

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

# --- import del reframe YOLO (tu archivo en scripts/) ---
import sys as _sys
BASE_DIR = Path(__file__).resolve().parents[1]
_sys.path.insert(0, str(BASE_DIR / "scripts"))
try:
    # reframe_video(src, dst, w, h, detect_every, ema_alpha, pan_cap_px, override, model_name, conf)
    from batch_reframe_track_yolo import reframe_video as yolo_reframe
except Exception:
    yolo_reframe = None

app = FastAPI(title="Batch Resizer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

JOBS: Dict[str, Dict[str, Any]] = {}
RUNS_DIR = BASE_DIR / "runs"
RUNS_DIR.mkdir(exist_ok=True)

# -------------------- helpers de nombres/headers --------------------
_WINDOWS_BAD = r'<>:"/\\|?*'
_BAD_RE = re.compile(rf"[{re.escape(_WINDOWS_BAD)}]")

def _sanitize_filename(name: str, maxlen: int = 120) -> str:
    """Limpia caracteres problemáticos y trunca con cuidado."""
    name = name.strip().replace("\n", " ").replace("\r", " ")
    name = _BAD_RE.sub("_", name)
    name = name.replace("%20", "_")
    if len(name) > maxlen:
        root, ext = os.path.splitext(name)
        name = (root[: max(1, maxlen - len(ext) - 3)] + "…") + ext
    # Evitar nombres vacíos/raros
    if not name or name in {".", ".."}:
        name = "file.mp4"
    return name

def _ensure_extension(name: str, content_type: Optional[str]) -> str:
    """Si no tiene extensión, intenta inferir por content-type; default .mp4."""
    root, ext = os.path.splitext(name)
    if ext:
        return name
    if content_type:
        guessed = mimetypes.guess_extension(content_type.split(";")[0].strip()) or ""
        if guessed:
            # Normalizar algunos tipos comunes
            if guessed == ".m4v":
                guessed = ".mp4"
            return name + guessed
    return name + ".mp4"

def _parse_cd_filename(cd: str) -> Optional[str]:
    """
    Parse RFC 5987/6266 Content-Disposition:
    - filename*=UTF-8''nombre.ext
    - filename="nombre.ext"
    """
    if not cd:
        return None
    # filename*=
    m = re.search(r"filename\*\s*=\s*([^']*)''([^;]+)", cd, re.IGNORECASE)
    if m:
        # charset = m.group(1) (no usamos, asumimos UTF-8)
        fn = requests.utils.unquote(m.group(2))
        return fn.strip().strip('"')
    # filename=
    m = re.search(r'filename\s*=\s*"([^"]+)"', cd, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r"filename\s*=\s*([^;]+)", cd, re.IGNORECASE)
    if m:
        return m.group(1).strip().strip('"')
    return None

def _last_segment_name(u: str) -> str:
    """Último segmento de la URL sin query; si vacío, 'file.mp4'."""
    name = u.split("?")[0].rstrip("/").split("/")[-1] or "file"
    if "." not in name:
        name += ".mp4"
    return name

def _name_from_query_filename(u: str) -> Optional[str]:
    """Si la URL trae ?filename=... úsalo (tu caso con Drive v3)."""
    try:
        q = parse_qs(urlparse(u).query)
        vals = q.get("filename")
        if vals and vals[0]:
            return vals[0]
    except Exception:
        pass
    return None

def _dedup_path(p: Path) -> Path:
    """Si p existe, devuelve p con sufijos _2, _3, ..."""
    if not p.exists():
        return p
    stem = p.stem
    suf = p.suffix
    i = 2
    while True:
        cand = p.with_name(f"{stem}_{i}{suf}")
        if not cand.exists():
            return cand
        i += 1

# -------------------- Google Drive helpers (opcionales) --------------------
def _extract_drive_folder_id(folder_url: str) -> str | None:
    try:
        p = urlparse(folder_url)
        if p.netloc not in ("drive.google.com", "www.drive.google.com"):
            return None
        parts = [x for x in p.path.split("/") if x]
        for i, seg in enumerate(parts):
            if seg == "folders" and i + 1 < len(parts):
                folder_id = parts[i + 1]
                return folder_id.split("?")[0]
    except Exception:
        return None
    return None

def _gdrive_client():
    from googleapiclient.discovery import build
    from google.oauth2 import service_account
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path or not os.path.exists(creds_path):
        raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS no configurado o inexistente.")
    scopes = ["https://www.googleapis.com/auth/drive.readonly"]
    creds = service_account.Credentials.from_service_account_file(creds_path, scopes=scopes)
    return build("drive", "v3", credentials=creds, cache_discovery=False)

def _gdrive_bearer_headers() -> Dict[str, str]:
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
        creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if not creds_path or not os.path.exists(creds_path):
            return {}
        scopes = ["https://www.googleapis.com/auth/drive.readonly"]
        creds = service_account.Credentials.from_service_account_file(creds_path, scopes=scopes)
        creds.refresh(Request())
        return {"Authorization": f"Bearer {creds.token}"}
    except Exception:
        return {}

# -------------------- descarga (con nombre correcto) --------------------
def download_many(urls: List[str], dest_dir: Path) -> List[Path]:
    """
    Baja todas las URLs a dest_dir.
    Regla de nombre:
      1) Content-Disposition (filename* / filename)
      2) ?filename= de la URL (ya soporta Drive API v3)
      3) último segmento de la URL (fallback; evita 'uc' si el header venía)
    Se sanitiza y se asegura extensión por Content-Type si falta.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    out: List[Path] = []

    drive_headers_cache: Dict[str, str] | None = None

    for u in urls:
        headers: Dict[str, str] = {}
        if "www.googleapis.com/drive/v3/files/" in u and "alt=media" in u:
            if drive_headers_cache is None:
                drive_headers_cache = _gdrive_bearer_headers()
            headers = drive_headers_cache or {}

        # GET (abrimos primero para leer headers)
        with requests.get(
            u,
            stream=True,
            timeout=(10, None),          # connect 10s, read stream sin límite
            headers=headers,
            allow_redirects=True,
        ) as r:
            r.raise_for_status()

            # 1) Intentar Content-Disposition
            cd = r.headers.get("Content-Disposition") or r.headers.get("content-disposition")
            name = _parse_cd_filename(cd) if cd else None

            # 2) Intentar query ?filename=
            if not name:
                name = _name_from_query_filename(u)

            # 3) Fallback: último segmento de la URL
            if not name:
                name = _last_segment_name(u)

            # Sanitizar e intentar asegurar extensión por content-type
            content_type = r.headers.get("Content-Type")
            name = _sanitize_filename(name)
            name = _ensure_extension(name, content_type)

            out_path = _dedup_path(dest_dir / name)

            with open(out_path, "wb") as f:
                for chunk in r.iter_content(1024 * 256):
                    if chunk:
                        f.write(chunk)

            out.append(out_path)

    return out

# -------------------- ffmpeg resize puro --------------------
def _ffmpeg_cmd(in_path: Path, out_path: Path, ratio: str, codec: str) -> List[str]:
    targets = {"9x16": (1080, 1920), "1x1": (1080, 1080), "16x9": (1920, 1080)}
    W, H = targets.get(ratio, (1080, 1920))
    vf = (
        "setparams=field_mode=prog,"
        f"scale={W}:{H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H},setsar=1/1"
    )
    common = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(in_path), "-vf", vf, "-movflags", "+faststart"
    ]
    if codec == "prores":
        return common + ["-c:v","prores_ks","-profile:v","3","-pix_fmt","yuv422p10le","-c:a","aac","-b:a","192k", str(out_path)]
    else:
        return common + ["-c:v","libx264","-preset","veryfast","-crf","20","-pix_fmt","yuv420p","-c:a","aac","-b:a","192k", str(out_path)]

def _zip_dir(src_dir: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in src_dir.rglob("*"):
            if p.is_file():
                z.write(p, arcname=p.name)  # solo el nombre limpio

# -------------------- worker --------------------
def _process_job(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        return
    try:
        workdir    = Path(job["workdir"])
        input_dir  = workdir / "input"
        output_dir = workdir / "output"
        urls       = job["urls"]
        ratios     = job["ratios"]
        codec      = job["codec"]
        mode       = job.get("mode", "resize")
        group_by_ratio = bool(job.get("group_by_ratio", False))

        # YOLO params (si vienen)
        detect_every = job.get("detect_every", 12)
        ema_alpha    = job.get("ema_alpha", 0.08)
        pan_cap_px   = job.get("pan_cap_px", 16.0)
        yolo_model   = job.get("yolo_model", "yolov8n.pt")
        yolo_conf    = job.get("yolo_conf", 0.35)

        job.update(dict(phase="downloading", message="Descargando archivos…", progress=3))
        files = download_many(urls, input_dir)
        if not files:
            raise RuntimeError("No se descargaron archivos")

        total_ops = max(1, len(files) * max(1, len(ratios)))
        job["total_steps"] = total_ops
        job["step_index"] = 0

        job.update(dict(phase="processing", message="Procesando…", progress=10))
        output_dir.mkdir(exist_ok=True)
        done_ops = 0

        targets = {"9x16": (1080, 1920), "1x1": (1080, 1080), "16x9": (1920, 1080)}
        if group_by_ratio:
            for rk in targets:
                (output_dir / rk).mkdir(parents=True, exist_ok=True)

        for f in files:
            job["current_file"] = f.name
            stem = f.stem  # único por download_many
            for r in ratios:
                job["current_ratio"] = r
                subdir = (output_dir / r) if group_by_ratio else output_dir

                if mode == "tracked_yolo":
                    if yolo_reframe is None:
                        raise RuntimeError("YOLO no disponible (import failed).")
                    W, H = targets.get(r, (1080, 1920))
                    out_name = f"{stem}_TRACKED_{r}.mp4"
                    out_path = subdir / out_name
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    yolo_reframe(
                        f, out_path, W, H,
                        detect_every=detect_every, ema_alpha=float(ema_alpha),
                        pan_cap_px=float(pan_cap_px),
                        override=None, model_name=yolo_model, conf=float(yolo_conf)
                    )
                else:
                    ext = "mp4" if codec == "h264" else "mov"
                    out_name = f"{stem}_RESIZE_{r}.{ext}"
                    out_path = subdir / out_name
                    cmd = _ffmpeg_cmd(f, out_path, r, codec)
                    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    if res.returncode != 0:
                        raise RuntimeError(f"FFmpeg falló en {f.name} ({r}): {res.stderr[-800:]}")

                done_ops += 1
                job["step_index"] = done_ops
                job["progress"] = min(95, 10 + int(80 * done_ops / total_ops))

        job.update(dict(phase="zipping", message="Empaquetando ZIP…", current_file=None, current_ratio=None, progress=97))
        zip_path = workdir / "results.zip"
        _zip_dir(output_dir, zip_path)

        job.update(dict(phase="done", message="Listo", progress=100, zip_path=str(zip_path)))
    except Exception as e:
        job.update(dict(phase="error", message="Error", error=str(e), progress=100))

# -------------------- endpoints --------------------
@app.post("/jobs")
def create_job(req: Dict[str, Any]):
    urls   = req.get("urls", [])
    ratios = req.get("ratios", ["9x16","1x1","16x9"])
    codec  = req.get("codec", "h264")
    mode   = req.get("mode", "resize")

    if not urls:
        raise HTTPException(400, "Faltan URLs")

    job_id = uuid.uuid4().hex
    workdir = RUNS_DIR / job_id
    (workdir / "input").mkdir(parents=True, exist_ok=True)
    (workdir / "output").mkdir(parents=True, exist_ok=True)

    status = {
        "id": job_id, "phase":"queued", "message":"En cola…", "progress":0,
        "total_steps":0, "step_index":0, "current_file":None, "current_ratio":None,
        "zip_path":None, "error":None, "mode":mode, "codec":codec,
        "ratios":ratios, "urls":urls, "workdir":str(workdir),
        "group_by_ratio": bool(req.get("group_by_ratio", False)),
        # YOLO params opcionales
        "detect_every": req.get("detect_every", 12),
        "ema_alpha":    req.get("ema_alpha", 0.08),
        "pan_cap_px":   req.get("pan_cap_px", 16.0),
        "yolo_model":   req.get("yolo_model", "yolov8n.pt"),
        "yolo_conf":    req.get("yolo_conf", 0.35),
    }
    JOBS[job_id] = status
    threading.Thread(target=_process_job, args=(job_id,), daemon=True).start()
    return {"job_id": job_id, "status": status}

@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job no encontrado")
    public = {k: v for k, v in job.items() if k not in ("workdir",)}
    return JSONResponse(public)

@app.get("/jobs/{job_id}/result")
def get_result(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job no encontrado")
    if job.get("phase") != "done" or not job.get("zip_path"):
        raise HTTPException(409, "El job aún no terminó")
    zip_path = Path(job["zip_path"])
    if not zip_path.exists():
        raise HTTPException(404, "ZIP no encontrado")
    return FileResponse(path=str(zip_path), media_type="application/zip", filename="results.zip")

@app.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job no encontrado")
    job.update(dict(phase="canceled", message="Cancelado por el usuario.", progress=100))
    return {"ok": True}

# --------- Expand Google Drive Folder (opcional) ----------
@app.post("/expand/google_drive_folder")
def expand_google_drive_folder(req: Dict[str, Any]):
    if not os.environ.get("GDRIVE_ENABLE"):
        raise HTTPException(501, "Google Drive expansion no está habilitado en este servidor.")

    folder_url = (req.get("folder_url") or "").strip()
    if not folder_url:
        raise HTTPException(400, "Falta folder_url.")

    folder_id = _extract_drive_folder_id(folder_url)
    if not folder_id:
        raise HTTPException(400, "folder_url inválida (no encuentro folder ID).")

    try:
        drive = _gdrive_client()
        q = f"'{folder_id}' in parents and trashed = false and mimeType contains 'video/'"
        page_token = None
        files = []
        while True:
            resp = drive.files().list(
                q=q,
                fields="nextPageToken, files(id, name, mimeType, size)",
                pageSize=1000,
                pageToken=page_token
            ).execute()
            for f in resp.get("files", []):
                fid = f["id"]
                dl = f"https://www.googleapis.com/drive/v3/files/{fid}?alt=media"
                dl_with_name = f"{dl}&filename={f.get('name', 'video.mp4')}"
                files.append({
                    "id": fid,
                    "name": f.get("name"),
                    "size": int(f.get("size", 0)) if "size" in f else None,
                    "mimeType": f.get("mimeType"),
                    "downloadUrl": dl_with_name,
                })
            page_token = resp.get("nextPageToken")
            if not page_token:
                break

        return {"files": files, "count": len(files), "folder_id": folder_id}

    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(500, f"Error de configuración: {e}")
    except Exception as e:
        error_msg = str(e)
        if "403" in error_msg or "Forbidden" in error_msg:
            raise HTTPException(403, f"Sin permisos para acceder a la carpeta {folder_id}. Verifica que la carpeta sea pública o que las credenciales tengan acceso.")
        elif "404" in error_msg or "Not Found" in error_msg:
            raise HTTPException(404, f"Carpeta {folder_id} no encontrada. Verifica que el ID sea correcto y que la carpeta exista.")
        else:
            raise HTTPException(500, f"Error consultando Drive: {error_msg}")
