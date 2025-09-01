from __future__ import annotations

import uuid
import zipfile
import threading
from pathlib import Path
from typing import List, Dict, Any
import subprocess
import requests
import hashlib

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

# -------------------- util nombres --------------------
def _safe_name_from_url(url: str) -> str:
    """
    Toma el último segmento sin query. Si no hay extensión, asume mp4.
    """
    name = url.split("?")[0].rstrip("/").split("/")[-1] or "file"
    if "." not in name:
        name += ".mp4"
    # sanitizar simples
    return name.replace("%20", "_")

def _dedup_path(p: Path) -> Path:
    """
    Si p existe, devuelve p con sufijos _2, _3, ...
    """
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

# -------------------- descarga --------------------
def download_many(urls: List[str], dest_dir: Path) -> List[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    out: List[Path] = []
    for u in urls:
        name = _safe_name_from_url(u)
        out_path = dest_dir / name
        out_path = _dedup_path(out_path)
        with requests.get(u, stream=True, timeout=60) as r:
            r.raise_for_status()
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
    common = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(in_path), "-vf", vf, "-movflags", "+faststart"]
    if codec == "prores":
        return common + ["-c:v","prores_ks","-profile:v","3","-pix_fmt","yuv422p10le","-c:a","aac","-b:a","192k", str(out_path)]
    else:
        return common + ["-c:v","libx264","-preset","veryfast","-crf","20","-pix_fmt","yuv420p","-c:a","aac","-b:a","192k", str(out_path)]

def _zip_dir(src_dir: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in src_dir.rglob("*"):
            if p.is_file():
                z.write(p, p.relative_to(src_dir))

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

        for f in files:
            job["current_file"] = f.name
            stem = f.stem  # ya único por download_many
            for r in ratios:
                job["current_ratio"] = r
                if mode == "tracked_yolo":
                    if yolo_reframe is None:
                        raise RuntimeError("YOLO no disponible (import failed).")
                    # tamaños destino
                    targets = {"9x16": (1080, 1920), "1x1": (1080, 1080), "16x9": (1920, 1080)}
                    W, H = targets.get(r, (1080, 1920))
                    out_name = f"{stem}_{r}.mp4"  # tracked siempre mp4
                    out_path = output_dir / out_name
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    yolo_reframe(
                        f, out_path, W, H,
                        detect_every=detect_every, ema_alpha=float(ema_alpha),
                        pan_cap_px=float(pan_cap_px),
                        override=None, model_name=yolo_model, conf=float(yolo_conf)
                    )
                else:
                    out_name = f"{stem}_{r}.mp4" if codec == "h264" else f"{stem}_{r}.mov"
                    out_path = output_dir / out_name
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
        # YOLO params opcionales (si el front los manda)
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
