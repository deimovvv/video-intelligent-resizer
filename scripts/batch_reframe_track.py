#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reencuadre con focal point (rostro/persona) + tracking + suavizado.
- Detección de rostro: MediaPipe.
- Tracking: OpenCV CSRT entre detecciones.
- Suavizado: EMA del centro de recorte.
- Audio: se remuxa desde el original si existe (con ffprobe para detectar).

Parámetros:
- detect_every: cada cuántos frames re-detectar (15–24 recomendado).
- ema_alpha: 0..1. Más bajo = más suave (0.05–0.12 típico).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

import cv2
import numpy as np

PRESETS = {
    "9x16":  (1080, 1920),
    "1x1":   (1080, 1080),
    "16x9":  (1920, 1080),
}
EXTS = {".mp4", ".mov", ".mxf", ".m4v", ".avi", ".mkv"}

# ---------- Suavizado EMA ----------
class Ema:
    def __init__(self, alpha: float = 0.08):
        self.alpha = float(alpha)
        self.v: Optional[np.ndarray] = None
    def update(self, x) -> np.ndarray:
        x = np.array(x, dtype=np.float32)
        if self.v is None:
            self.v = x
        else:
            self.v = self.alpha * x + (1.0 - self.alpha) * self.v
        return self.v

# ---------- MediaPipe Face Detection (lazy init) ----------
_mp_face = None
def _get_face_detections(frame_bgr) -> list[tuple[int,int,int,int]]:
    global _mp_face
    if _mp_face is None:
        import mediapipe as mp
        _mp_face = mp.solutions.face_detection.FaceDetection(
            model_selection=0, min_detection_confidence=0.5
        )
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    res = _mp_face.process(rgb)
    boxes: list[tuple[int,int,int,int]] = []
    if getattr(res, "detections", None):
        h, w = frame_bgr.shape[:2]
        for det in res.detections:
            b = det.location_data.relative_bounding_box
            x = max(0, int(b.xmin * w))
            y = max(0, int(b.ymin * h))
            bw = max(1, int(b.width * w))
            bh = max(1, int(b.height * h))
            boxes.append((x, y, bw, bh))
    return boxes

# ---------- Utils ----------
def _clamp(v, lo, hi): return max(lo, min(hi, v))

def _compute_crop_window(frame_w: int, frame_h: int, target_ratio: float, center) -> tuple[int,int,int,int]:
    src_ratio = frame_w / frame_h
    if src_ratio > target_ratio:
        ch = frame_h
        cw = int(round(frame_h * target_ratio))
    else:
        cw = frame_w
        ch = int(round(frame_w / target_ratio))
    cx, cy = center
    x0 = int(round(cx - cw/2))
    y0 = int(round(cy - ch/2))
    x0 = _clamp(x0, 0, frame_w - cw)
    y0 = _clamp(y0, 0, frame_h - ch)
    return x0, y0, cw, ch

def _has_audio(src_path: Path) -> bool:
    """Usa ffprobe para verificar si hay al menos 1 stream de audio."""
    try:
        r = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "a",
                "-show_entries", "stream=index",
                "-of", "csv=p=0",
                str(src_path)
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        return bool(r.stdout.strip())
    except Exception:
        return False

def _remux_audio(src_path: Path, video_no_audio: Path, out_path: Path):
    """
    Si el original tiene audio, lo extrae y muxea; si no, deja el video sin audio.
    Silencia errores y evita abortar el pipeline.
    """
    if out_path.exists():
        out_path.unlink()

    if _has_audio(src_path):
        aac = video_no_audio.with_suffix('.m4a')
        try:
            subprocess.run(
                ["ffmpeg","-y","-hide_banner","-loglevel","error",
                 "-i", str(src_path), "-vn", "-acodec", "aac", "-b:a", "192k", str(aac)],
                check=True
            )
            subprocess.run(
                ["ffmpeg","-y","-hide_banner","-loglevel","error",
                 "-i", str(video_no_audio), "-i", str(aac),
                 "-c:v","copy","-c:a","aac","-shortest", str(out_path)],
                check=True
            )
        except Exception:
            video_no_audio.replace(out_path)
        finally:
            try: aac.unlink(missing_ok=True)
            except Exception: pass
            try: video_no_audio.unlink(missing_ok=True)
            except Exception: pass
    else:
        video_no_audio.replace(out_path)

# ---------- Core ----------
def reframe_video(
    src: Path, dst: Path, target_w: int, target_h: int,
    *, detect_every: int = 18, ema_alpha: float = 0.08,
    override: Optional[Dict[str,Any]] = None,
):
    cap = cv2.VideoCapture(str(src))
    if not cap.isOpened():
        raise RuntimeError(f"No se pudo abrir el video: {src}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    fw  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    fh  = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    target_ratio = target_w / target_h
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    tmp_no_audio = dst.with_name(dst.stem + "_tmp.mp4")
    out = cv2.VideoWriter(str(tmp_no_audio), fourcc, fps, (target_w, target_h))

    tracker = None
    ema = Ema(alpha=ema_alpha)
    frame_idx = 0

    manual_center = None
    fixed_box = None
    if override:
        if "manual_center" in override:
            mx, my = override["manual_center"]
            manual_center = (mx * fw, my * fh)
        if "box" in override:
            bx, by, bw, bh = override["box"]
            fixed_box = (bx*fw, by*fh, bw*fw, bh*fh)

    def init_tracker(frame, box_xywh):
        nonlocal tracker
        tracker = cv2.TrackerCSRT_create()
        tracker.init(frame, tuple(map(int, box_xywh)))

    while True:
        ok, frame = cap.read()
        if not ok: break
        frame_idx += 1

        box = None
        if fixed_box is not None:
            box = fixed_box
        else:
            use_detect = (tracker is None) or (frame_idx % max(1, detect_every) == 1)
            if use_detect:
                faces = _get_face_detections(frame)
                if faces:
                    box = max(faces, key=lambda b: b[2]*b[3])
                    init_tracker(frame, box)
                elif tracker is not None:
                    ok_t, b = tracker.update(frame)
                    if ok_t: box = b
                    else:    tracker = None
            elif tracker is not None:
                ok_t, b = tracker.update(frame)
                if ok_t: box = b
                else:    tracker = None

        if box is not None:
            x, y, bw, bh = box
            cx = x + bw/2
            cy = y + bh/2
        elif manual_center is not None:
            cx, cy = manual_center
        else:
            cx, cy = fw/2, fh/2

        scx, scy = ema.update((cx, cy))
        x0, y0, cw, ch = _compute_crop_window(fw, fh, target_ratio, (float(scx), float(scy)))

        crop = frame[int(y0):int(y0+ch), int(x0):int(x0+cw)]
        resized = cv2.resize(crop, (target_w, target_h), interpolation=cv2.INTER_AREA)
        out.write(resized)

    out.release(); cap.release()
    dst.parent.mkdir(parents=True, exist_ok=True)
    _remux_audio(src, tmp_no_audio, dst)

def process_dir(
    input_dir: Path, output_dir: Path, ratio_key: str, *,
    overrides_path: Optional[Path] = None,
    detect_every: int = 18, ema_alpha: float = 0.08,
):
    assert ratio_key in PRESETS, f"ratio_key inválido: {ratio_key}"
    w, h = PRESETS[ratio_key]

    overrides: Dict[str, Any] = {}
    if overrides_path and overrides_path.exists():
        try:
            overrides = json.loads(overrides_path.read_text(encoding="utf-8"))
        except Exception:
            overrides = {}

    files = [p for p in sorted(Path(input_dir).iterdir()) if p.suffix.lower() in EXTS]
    for p in files:
        out_p = Path(output_dir) / ratio_key / f"{p.stem}_{ratio_key}.mp4"
        out_p.parent.mkdir(parents=True, exist_ok=True)
        ov = overrides.get(p.name)
        print(f"[Reframe] {p.name} → {ratio_key} (tracked)")
        reframe_video(
            p, out_p, w, h,
            detect_every=detect_every, ema_alpha=ema_alpha, override=ov
        )

if __name__ == "__main__":
    base = Path(__file__).resolve().parents[1]
    input_dir = base / "input"
    output_dir = base / "output"
    overrides_path = base / "overrides.json"
    for rk in ("9x16","1x1","16x9"):
        process_dir(input_dir, output_dir, rk, overrides_path=overrides_path)
    print("[DONE] Reencuadre con rostro/persona + suavizado]")
