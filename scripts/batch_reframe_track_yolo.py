#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reencuadre con detector de PERSONA (YOLO) + tracker CSRT + suavizado (EMA) + límite de paneo por frame.
- Detector: Ultralytics YOLO (clase 'person')
- Tracking: OpenCV CSRT entre redetecciones
- Suavizado: EMA del centro
- Pan Cap: limita cuántos píxeles puede moverse el centro por frame

Parámetros recomendados:
- detect_every: 8–16 (más chico = reacciona mejor; más grande = más rápido)
- ema_alpha: 0.06–0.12 (más bajo = más suave)
- pan_cap_px: 12–32 (cap de paneo por frame en píxeles; evita “cachetazos”)
"""
from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

import cv2
import numpy as np
from ultralytics import YOLO

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
    try:
        r = subprocess.run(
            ["ffprobe","-v","error","-select_streams","a",
             "-show_entries","stream=index","-of","csv=p=0", str(src_path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        return bool(r.stdout.strip())
    except Exception:
        return False

def _remux_audio(src_path: Path, video_no_audio: Path, out_path: Path):
    if out_path.exists():
        out_path.unlink()
    if _has_audio(src_path):
        aac = video_no_audio.with_suffix(".m4a")
        try:
            subprocess.run(
                ["ffmpeg","-y","-hide_banner","-loglevel","error",
                 "-i", str(src_path), "-vn", "-acodec","aac","-b:a","192k", str(aac)],
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

def _apply_pan_cap(prev_center: np.ndarray, target_center: np.ndarray, pan_cap_px: float) -> np.ndarray:
    if prev_center is None:
        return target_center
    dx, dy = target_center - prev_center
    dist = math.hypot(float(dx), float(dy))
    if dist <= pan_cap_px or pan_cap_px <= 0:
        return target_center
    scale = pan_cap_px / dist
    capped = prev_center + np.array([dx*scale, dy*scale], dtype=np.float32)
    return capped

# ---------- Detector YOLO (person) ----------
class PersonDetector:
    def __init__(self, model_name: str = "yolov8n.pt", conf: float = 0.35):
        self.model = YOLO(model_name)
        self.conf = conf
        self.person_class_ids = {0}  # COCO: 0 = person

    def detect_biggest_person(self, frame_bgr) -> Optional[tuple[int,int,int,int]]:
        # Ultralytics usa RGB internamente; puede recibir BGR igual, pero convertimos
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        res = self.model.predict(
            source=frame_rgb, imgsz=640, conf=self.conf, verbose=False
        )
        # res es una lista; tomamos el primero
        if not res: 
            return None
        r = res[0]
        if r.boxes is None or len(r.boxes) == 0:
            return None
        # Filtrar solo clase person
        candidates = []
        for b in r.boxes:
            cls = int(b.cls.item())
            if cls in self.person_class_ids:
                x1, y1, x2, y2 = map(float, b.xyxy[0].tolist())
                w = max(1, int(x2 - x1))
                h = max(1, int(y2 - y1))
                x = max(0, int(x1))
                y = max(0, int(y1))
                candidates.append((x, y, w, h))
        if not candidates:
            return None
        # Mayor área
        return max(candidates, key=lambda b: b[2]*b[3])

# ---------- Core ----------
def reframe_video(
    src: Path, dst: Path, target_w: int, target_h: int,
    *, detect_every: int = 12, ema_alpha: float = 0.08, pan_cap_px: float = 16.0,
    override: Optional[Dict[str, Any]] = None,
    model_name: str = "yolov8n.pt", conf: float = 0.35,
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

    detector = PersonDetector(model_name=model_name, conf=conf)
    tracker = None
    ema = Ema(alpha=ema_alpha)
    frame_idx = 0

    prev_smooth_center: Optional[np.ndarray] = None

    # Overrides manuales
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
                box = detector.detect_biggest_person(frame)
                if box is not None:
                    init_tracker(frame, box)
                elif tracker is not None:
                    ok_t, b = tracker.update(frame)
                    if ok_t: box = b
                    else:    tracker = None
            elif tracker is not None:
                ok_t, b = tracker.update(frame)
                if ok_t: box = b
                else:    tracker = None

        # Centro objetivo
        if box is not None:
            x, y, bw, bh = box
            cx = x + bw/2
            cy = y + bh/2
        elif manual_center is not None:
            cx, cy = manual_center
        else:
            cx, cy = fw/2, fh/2

        # Suavizado + cap de paneo
        target_center = np.array([cx, cy], dtype=np.float32)
        smooth_center = ema.update(target_center)
        if prev_smooth_center is None:
            capped_center = smooth_center
        else:
            capped_center = _apply_pan_cap(prev_smooth_center, smooth_center, pan_cap_px)
        prev_smooth_center = capped_center.copy()

        x0, y0, cw, ch = _compute_crop_window(fw, fh, target_ratio, (float(capped_center[0]), float(capped_center[1])))
        crop = frame[int(y0):int(y0+ch), int(x0):int(x0+cw)]
        resized = cv2.resize(crop, (target_w, target_h), interpolation=cv2.INTER_AREA)
        out.write(resized)

    out.release(); cap.release()
    dst.parent.mkdir(parents=True, exist_ok=True)
    _remux_audio(src, tmp_no_audio, dst)

def process_dir(
    input_dir: Path, output_dir: Path, ratio_key: str, *,
    overrides_path: Optional[Path] = None,
    detect_every: int = 12, ema_alpha: float = 0.08, pan_cap_px: float = 16.0,
    model_name: str = "yolov8n.pt", conf: float = 0.35,
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
        print(f"[Reframe-YOLO] {p.name} → {ratio_key}")
        reframe_video(
            p, out_p, w, h,
            detect_every=detect_every, ema_alpha=ema_alpha, pan_cap_px=pan_cap_px,
            override=ov, model_name=model_name, conf=conf
        )

if __name__ == "__main__":
    base = Path(__file__).resolve().parents[1]
    input_dir = base / "input"
    output_dir = base / "output"
    overrides_path = base / "overrides.json"
    for rk in ("9x16","1x1","16x9"):
        process_dir(input_dir, output_dir, rk, overrides_path=overrides_path)
    print("[DONE] Reencuadre YOLO + suavizado + pan cap]")
