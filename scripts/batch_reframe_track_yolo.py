#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reencuadre con YOLO (person) + tracker (CSRT/KCF) + EMA + pan cap.
Ahora con CLI, progreso visible y subcarpetas por ratio dentro de output/,
y los outputs llevan sufijo `_tracked`.
"""
from __future__ import annotations
import argparse, json, math, time, sys, subprocess
from pathlib import Path
from typing import Dict, Any, Optional

import cv2
import numpy as np

try:
    from ultralytics import YOLO
except Exception as e:
    print("[ERROR] No se pudo importar ultralytics. Instalá con 'pip install ultralytics'.", file=sys.stderr)
    raise

PRESETS = {"9x16": (1080, 1920), "1x1": (1080, 1080), "16x9": (1920, 1080)}
EXTS = {".mp4", ".mov", ".mxf", ".m4v", ".avi", ".mkv"}

# ---------- helpers ----------
def _clamp(v, lo, hi): return max(lo, min(hi, v))

def _compute_crop_window(frame_w: int, frame_h: int, target_ratio: float, center) -> tuple[int,int,int,int]:
    src_ratio = frame_w / frame_h
    if src_ratio > target_ratio:
        ch = frame_h; cw = int(round(frame_h * target_ratio))
    else:
        cw = frame_w; ch = int(round(frame_w / target_ratio))
    cx, cy = center
    x0 = int(round(cx - cw/2)); y0 = int(round(cy - ch/2))
    x0 = _clamp(x0, 0, frame_w - cw); y0 = _clamp(y0, 0, frame_h - ch)
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
            for p in (aac, video_no_audio):
                try: p.unlink(missing_ok=True)
                except Exception: pass
    else:
        video_no_audio.replace(out_path)

# ---------- EMA ----------
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

def _apply_pan_cap(prev_center: np.ndarray, target_center: np.ndarray, pan_cap_px: float) -> np.ndarray:
    if prev_center is None:
        return target_center
    dx, dy = target_center - prev_center
    dist = math.hypot(float(dx), float(dy))
    if dist <= pan_cap_px or pan_cap_px <= 0:
        return target_center
    scale = pan_cap_px / dist
    return prev_center + np.array([dx*scale, dy*scale], dtype=np.float32)

# ---------- Detector ----------
class PersonDetector:
    def __init__(self, model_name: str = "yolov8n.pt", conf: float = 0.35):
        self.model = YOLO(model_name)
        self.conf = conf
        self.person_class_ids = {0}  # COCO: 0 = person

    def detect_biggest_person(self, frame_bgr) -> Optional[tuple[int,int,int,int]]:
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        res = self.model.predict(source=frame_rgb, imgsz=640, conf=self.conf, verbose=False)
        if not res: 
            return None
        r = res[0]
        if r.boxes is None or len(r.boxes) == 0:
            return None
        candidates = []
        for b in r.boxes:
            cls = int(b.cls.item())
            if cls in self.person_class_ids:
                x1, y1, x2, y2 = map(float, b.xyxy[0].tolist())
                w = max(1, int(x2 - x1)); h = max(1, int(y2 - y1))
                x = max(0, int(x1)); y = max(0, int(y1))
                candidates.append((x, y, w, h))
        if not candidates:
            return None
        return max(candidates, key=lambda b: b[2]*b[3])

def _make_tracker():
    if hasattr(cv2, "TrackerCSRT_create"):
        return cv2.TrackerCSRT_create()
    if hasattr(cv2, "TrackerKCF_create"):
        print("[WARN] CSRT no disponible, usando KCF.")
        return cv2.TrackerKCF_create()
    raise RuntimeError("No hay CSRT/KCF disponibles. Instalá opencv-contrib-python.")

# ---------- Core ----------
def reframe_video(
    src: Path, dst: Path, target_w: int, target_h: int,
    *, detect_every: int = 12, ema_alpha: float = 0.08, pan_cap_px: float = 16.0,
    override: Optional[Dict[str, Any]] = None,
    model_name: str = "yolov8n.pt", conf: float = 0.35,
    verbose: bool = False,
):
    cap = cv2.VideoCapture(str(src))
    if not cap.isOpened():
        raise RuntimeError(f"No se pudo abrir el video: {src}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    fw  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    fh  = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    target_ratio = target_w / target_h

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    tmp_no_audio = dst.with_name(dst.stem + "_tmp.mp4")
    out = cv2.VideoWriter(str(tmp_no_audio), fourcc, fps, (target_w, target_h))

    detector = PersonDetector(model_name=model_name, conf=conf)
    tracker = None
    ema = Ema(alpha=ema_alpha)
    frame_idx = 0

    prev_smooth_center: Optional[np.ndarray] = None

    while True:
        ok, frame = cap.read()
        if not ok: break
        frame_idx += 1

        box = detector.detect_biggest_person(frame) if (tracker is None or frame_idx % detect_every == 1) else None
        if box is not None:
            tracker = _make_tracker()
            tracker.init(frame, tuple(map(int, box)))
        elif tracker is not None:
            ok_t, b = tracker.update(frame)
            if ok_t: box = b

        if box is not None:
            x, y, bw, bh = box
            cx = x + bw/2; cy = y + bh/2
        else:
            cx, cy = fw/2, fh/2

        target_center = np.array([cx, cy], dtype=np.float32)
        smooth_center = ema.update(target_center)
        capped_center = smooth_center if prev_smooth_center is None else _apply_pan_cap(prev_smooth_center, smooth_center, pan_cap_px)
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
    detect_every: int = 12, ema_alpha: float = 0.08, pan_cap_px: float = 16.0,
    model_name: str = "yolov8n.pt", conf: float = 0.35, verbose: bool = False,
):
    assert ratio_key in PRESETS, f"ratio_key inválido: {ratio_key}"
    w, h = PRESETS[ratio_key]

    files = [p for p in sorted(Path(input_dir).iterdir()) if p.suffix.lower() in EXTS]
    if not files:
        print("  [INFO] No hay videos en", input_dir)
        return
    out_ratio_dir = Path(output_dir) / ratio_key
    out_ratio_dir.mkdir(parents=True, exist_ok=True)

    print(f"[Reframe-YOLO] Procesando ratio {ratio_key} ({w}x{h}), {len(files)} archivo(s)")
    for p in files:
        dst = out_ratio_dir / f"{p.stem}_tracked_{ratio_key}.mp4"
        reframe_video(
            p, dst, w, h,
            detect_every=detect_every, ema_alpha=ema_alpha, pan_cap_px=pan_cap_px,
            model_name=model_name, conf=conf, verbose=verbose
        )

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, default=Path("./input"))
    ap.add_argument("--output", type=Path, default=Path("./output"))
    ap.add_argument("--ratios", nargs="+", default=["9x16","1x1","16x9"])
    ap.add_argument("--detect-every", type=int, default=12)
    ap.add_argument("--ema-alpha", type=float, default=0.08)
    ap.add_argument("--pan-cap-px", type=float, default=16.0)
    ap.add_argument("--model", type=str, default="yolov8n.pt")
    ap.add_argument("--conf", type=float, default=0.35)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    print(f"[INFO] Input:  {args.input.resolve()}")
    print(f"[INFO] Output: {args.output.resolve()}")
    for rk in args.ratios:
        process_dir(
            args.input, args.output, rk,
            detect_every=args.detect_every, ema_alpha=args.ema_alpha, pan_cap_px=args.pan_cap_px,
            model_name=args.model, conf=args.conf, verbose=args.verbose
        )
    print("[DONE] Reencuadre YOLO + suavizado + pan cap")

if __name__ == "__main__":
    main()
