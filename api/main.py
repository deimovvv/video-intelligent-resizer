from __future__ import annotations

import uuid
import zipfile
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import subprocess
import requests
import os
from urllib.parse import urlparse, parse_qs, unquote

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

# CORS correcto (vía add_middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# ---- Estado en memoria ----
JOBS: Dict[str, Dict[str, Any]] = {}
RUNS_DIR = BASE_DIR / "runs"
RUNS_DIR.mkdir(exist_ok=True)

# -------------------- util nombres --------------------
def _safe_name_from_url(url: str) -> str:
    """
    Obtiene un nombre de archivo a partir de la URL.
    - Respeta ?filename=... cuando viene de Google Drive API (expand).
    - Si no hay extensión, asume .mp4
    """
    try:
        parsed = urlparse(url)
        q = parse_qs(parsed.query or "")
        if "filename" in q and q["filename"]:
            name = q["filename"][0]
            name = name.replace("/", "_").replace("\\", "_")
            if "." not in name:
                name += ".mp4"
            return name
    except Exception:
        pass

    name = url.split("?")[0].rstrip("/").split("/")[-1] or "file"
    if "." not in name:
        name += ".mp4"
    return name.replace("%20", "_")

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

def _extract_drive_file_id(url: str) -> Optional[str]:
    """Detecta FILE ID en enlaces de Drive tipo /uc?id=... o /file/d/<id>/..."""
    try:
        p = urlparse(url)
        if p.netloc not in ("drive.google.com", "www.drive.google.com"):
            return None
        qs = parse_qs(p.query or "")
        if "id" in qs and qs["id"]:
            return qs["id"][0]
        # patrón /file/d/<id>/...
        parts = [x for x in p.path.split("/") if x]
        if "file" in parts:
            i = parts.index("file")
            if i + 2 < len(parts) and parts[i+1] == "d":
                return parts[i+2]
    except Exception:
        return None
    return None

def _filename_from_content_disposition(cd: str) -> Optional[str]:
    """
    Extrae filename de un header Content-Disposition.
    Soporta filename* (RFC 5987) y filename=.
    """
    try:
        cd_lower = cd.lower()
        # filename*=
        if "filename*=" in cd_lower:
            # ejemplo: filename*=UTF-8''my%20file.mp4
            part = cd_lower.split("filename*=")[1].split(";")[0].strip()
            # quitamos comillas si hay
            part = part.strip('"').strip("'")
            # formato <charset>''<nombre_urlencoded>
            if "''" in part:
                enc_name = part.split("''", 1)[1]
            else:
                enc_name = part
            name = unquote(enc_name)
            return name
        # filename=
        if "filename=" in cd_lower:
            part = cd.split("filename=")[1].split(";")[0].strip()
            part = part.strip('"').strip("'")
            return part
    except Exception:
        pass
    return None

def _gdrive_filename_via_api(file_id: str) -> Optional[str]:
    """
    Si hay credenciales (GDRIVE_ENABLE + GOOGLE_APPLICATION_CREDENTIALS),
    intenta pedir a la API de Drive el nombre real del archivo.
    """
    try:
        headers = _gdrive_bearer_headers()
        if not headers:
            return None
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}?fields=name"
        r = requests.get(url, headers=headers, timeout=20)
        if r.ok:
            data = r.json()
            name = data.get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()
    except Exception:
        return None
    return None

# -------------------- Google Drive helpers (opcionales) --------------------
def _extract_drive_folder_id(folder_url: str) -> Optional[str]:
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

# -------------------- helpers results/summary --------------------
def _init_results_summary(job: Dict[str, Any]) -> None:
    job["results"] = []  # lista de items detallados
    job["summary"] = {
        "success": 0,
        "errors": 0,
        "total": 0,
        "download_errors": 0,
        "processing_errors": 0,
    }

def _push_result(job: Dict[str, Any], *,
                 stage: str,                # "download" | "process"
                 status: str,               # "ok" | "error"
                 url: Optional[str] = None,
                 file: Optional[str] = None,
                 ratio: Optional[str] = None,
                 output: Optional[str] = None,
                 reason: Optional[str] = None) -> None:
    item = {
        "stage": stage,
        "status": status,
        "url": url,
        "file": file,
        "ratio": ratio,
        "output": output,
        "reason": reason,
    }
    job["results"].append(item)
    s = job["summary"]
    s["total"] += 1
    if status == "ok":
        s["success"] += 1
    else:
        s["errors"] += 1
        if stage == "download":
            s["download_errors"] += 1
        elif stage == "process":
            s["processing_errors"] += 1

# -------------------- descarga --------------------
def download_many(job: Dict[str, Any], urls: List[str], dest_dir: Path) -> List[Tuple[Path, str]]:
    """
    Descarga cada URL a dest_dir.
    - Devuelve lista de (ruta_local, url) SOLO de descargas exitosas.
    - Registra en job['results'] cada intento (ok/error).
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    out: List[Tuple[Path, str]] = []
    drive_headers_cache: Optional[Dict[str, str]] = None

    for u in urls:
        # nombre tentativo basado en la URL
        tentative_name = _safe_name_from_url(u)
        out_path = _dedup_path(dest_dir / tentative_name)

        headers: Dict[str, str] = {}
        # Soporte a enlaces de la Google Drive Files API (?alt=media)
        if "www.googleapis.com/drive/v3/files/" in u and "alt=media" in u:
            if drive_headers_cache is None:
                drive_headers_cache = _gdrive_bearer_headers()
            headers = drive_headers_cache or {}

        try:
            with requests.get(u, stream=True, timeout=120, headers=headers) as r:
                r.raise_for_status()

                # 1) ¿El servidor nos dice el nombre real?
                cd = r.headers.get("Content-Disposition") or r.headers.get("content-disposition")
                real_name = _filename_from_content_disposition(cd) if cd else None

                # 2) ¿Es un link de Drive (uc/file/d) y tenemos creds? probamos API.
                if not real_name:
                    fid = _extract_drive_file_id(u)
                    if fid:
                        real_name = _gdrive_filename_via_api(fid)

                if real_name:
                    real_name = real_name.replace("/", "_").replace("\\", "_")
                    if "." not in real_name:
                        real_name += ".mp4"
                    out_path = _dedup_path(dest_dir / real_name)

                # descargar al nombre final decidido
                with open(out_path, "wb") as f:
                    for chunk in r.iter_content(1024 * 256):
                        if chunk:
                            f.write(chunk)

            _push_result(job, stage="download", status="ok", url=u, file=out_path.name)
            out.append((out_path, u))

        except Exception as e:
            _push_result(job, stage="download", status="error", url=u, reason=str(e))

        # Avance de progreso por descarga
        try:
            job["done_ops"] += 1
            _update_progress(job)
        except Exception:
            pass

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

# -------------------- progreso --------------------
def _recompute_total_ops(job: Dict[str, Any]) -> None:
    """
    total_ops = intentos de descarga (len(urls)) + (descargas exitosas * len(ratios))
    """
    urls = job["urls"]
    ratios = job["ratios"]
    downloads = len(urls)
    # si ya hubo descargas, contamos solo las OK que quedaron en job["_download_ok_count"]
    dl_ok = job.get("_download_ok_count")
    if dl_ok is None:
        # aún no descargamos: estima con todos
        job["total_ops"] = downloads + max(1, downloads) * max(1, len(ratios))
    else:
        job["total_ops"] = downloads + dl_ok * max(1, len(ratios))

def _update_progress(job: Dict[str, Any]) -> None:
    total = max(1, job.get("total_ops", 1))
    done = max(0, job.get("done_ops", 0))
    # mapeo 5..95 para etapas de trabajo
    job["progress"] = min(95, max(5, int(5 + (done / total) * 90)))

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
        detect_every = int(job.get("detect_every", 12))
        ema_alpha    = float(job.get("ema_alpha", 0.08))
        pan_cap_px   = float(job.get("pan_cap_px", 16.0))
        yolo_model   = job.get("yolo_model", "yolov8n.pt")
        yolo_conf    = float(job.get("yolo_conf", 0.35))

        # Inicialización de resultados/resumen/progreso
        _init_results_summary(job)
        job.update(dict(phase="downloading", message="Downloading files…"))
        job["done_ops"] = 0
        _recompute_total_ops(job)
        _update_progress(job)

        # --- Descargas ---
        pairs = download_many(job, urls, input_dir)  # [(path, url), ...]
        files = [p for p, _ in pairs]
        job["_download_ok_count"] = len(files)
        if not files:
            raise RuntimeError("No files were downloaded.")

        # recalcular total_ops con base en descargas OK
        _recompute_total_ops(job)
        _update_progress(job)

        # --- Procesado ---
        job.update(dict(phase="processing", message="Processing…"))
        output_dir.mkdir(exist_ok=True)

        targets = {"9x16": (1080, 1920), "1x1": (1080, 1080), "16x9": (1920, 1080)}
        if group_by_ratio:
            for rk in targets:
                (output_dir / rk).mkdir(parents=True, exist_ok=True)

        for f in files:
            job["current_file"] = f.name
            stem = f.stem
            for r in ratios:
                job["current_ratio"] = r
                subdir = (output_dir / r) if group_by_ratio else output_dir
                subdir.mkdir(parents=True, exist_ok=True)

                try:
                    if mode == "tracked_yolo":
                        if yolo_reframe is None:
                            raise RuntimeError("YOLO is not available (import failed).")
                        W, H = targets.get(r, (1080, 1920))
                        out_name = f"{stem}_TRACKED_{r}.mp4"
                        out_path = subdir / out_name
                        yolo_reframe(
                            f, out_path, W, H,
                            detect_every=detect_every, ema_alpha=ema_alpha,
                            pan_cap_px=pan_cap_px,
                            override=None, model_name=yolo_model, conf=yolo_conf
                        )
                    else:
                        ext = "mp4" if codec == "h264" else "mov"
                        out_name = f"{stem}_RESIZE_{r}.{ext}"
                        out_path = subdir / out_name
                        cmd = _ffmpeg_cmd(f, out_path, r, codec)
                        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                        if res.returncode != 0:
                            raise RuntimeError(res.stderr[-800:] if res.stderr else "FFmpeg failed.")

                    # OK
                    _push_result(job, stage="process", status="ok",
                                 url=None, file=f.name, ratio=r,
                                 output=out_path.name, reason=None)
                except Exception as e:
                    # ERROR
                    _push_result(job, stage="process", status="error",
                                 url=None, file=f.name, ratio=r,
                                 output=None, reason=str(e))

                # avance de progreso por cada salida (ok o error)
                job["done_ops"] += 1
                _update_progress(job)

        # --- Zipeo ---
        job.update(dict(phase="zipping", message="Creating ZIP…", current_file=None, current_ratio=None))
        zip_path = workdir / "results.zip"
        _zip_dir(output_dir, zip_path)

        job.update(dict(phase="done", message="Done", progress=100, zip_path=str(zip_path)))
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
        "id": job_id, "phase":"queued", "message":"Queued…", "progress":0,
        "total_steps":0, "step_index":0, "current_file":None, "current_ratio":None,
        "zip_path":None, "error":None, "mode":mode, "codec":codec,
        "ratios":ratios, "urls":urls, "workdir":str(workdir),
        "group_by_ratio": bool(req.get("group_by_ratio", False)),
        # YOLO params opcionales
        "detect_every": int(req.get("detect_every", 12)),
        "ema_alpha":    float(req.get("ema_alpha", 0.08)),
        "pan_cap_px":   float(req.get("pan_cap_px", 16.0)),
        "yolo_model":   req.get("yolo_model", "yolov8n.pt"),
        "yolo_conf":    float(req.get("yolo_conf", 0.35)),
    }
    JOBS[job_id] = status
    # extras para el worker
    JOBS[job_id]["workdir"] = str(workdir)  # ya está
    # results/summary los inicializa el worker al empezar

    threading.Thread(target=_process_job, args=(job_id,), daemon=True).start()
    return {"job_id": job_id, "status": status}

@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job no encontrado")
    public = {k: v for k, v in job.items() if k not in ("workdir",)}
    # asegurar results/summary aunque el worker no haya empezado
    public.setdefault("results", [])
    public.setdefault("summary", {
        "success": 0,"errors": 0,"total": 0,"download_errors": 0,"processing_errors": 0
    })
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
    job.update(dict(phase="canceled", message="Canceled by user.", progress=100))
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
                # Agregamos el nombre original como parámetro para que _safe_name_from_url lo use
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
        # Error de credenciales
        raise HTTPException(500, f"Error de configuración: {e}")
    except Exception as e:
        error_msg = str(e)
        if "403" in error_msg or "Forbidden" in error_msg:
            raise HTTPException(403, f"Sin permisos para acceder a la carpeta {folder_id}. Verifica que la carpeta sea pública o que las credenciales tengan acceso.")
        elif "404" in error_msg or "Not Found" in error_msg:
            raise HTTPException(404, f"Carpeta {folder_id} no encontrada. Verifica que el ID sea correcto y que la carpeta exista.")
        else:
            raise HTTPException(500, f"Error consultando Drive: {error_msg}")
