#!/usr/bin/env python3
# scripts/batch_resize_min.py
import subprocess
import sys
from pathlib import Path

# Ratios objetivo
PRESETS = {
    "9x16":  (1080, 1920),
    "1x1":   (1080, 1080),
    "16x9":  (1920, 1080),
}

# Extensiones aceptadas (y archivos sin extensión)
EXTS = {".mp4", ".mov", ".mxf", ".m4v", ".avi", ".mkv"}

def ensure_dirs(base_output: Path):
    for k in PRESETS.keys():
        (base_output / k).mkdir(parents=True, exist_ok=True)

def build_cmd_ffmpeg(in_path: Path, out_path: Path, w: int, h: int,
                     codec: str = "h264", crf: int = 20, preset: str = "veryfast",
                     prores_profile: int = 3):
    """
    Center-crop sin barras:
    - setparams = fuerza progresivo (evita rarezas en fuentes interlaced)
    - scale ... increase = llena el canvas en al menos uno de los lados
    - crop WxH = recorte centrado exacto
    - setsar=1/1 = SAR neutro para evitar “aplastes”
    - +faststart = moov ahead (player-friendly)
    """
    vf = (
        "setparams=field_mode=prog,"
        f"scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h},setsar=1/1"
    )
    common = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(in_path),
        "-vf", vf, "-movflags", "+faststart"
    ]
    if codec.lower() == "prores":
        return common + [
            "-c:v", "prores_ks", "-profile:v", str(prores_profile), "-pix_fmt", "yuv422p10le",
            "-c:a", "aac", "-b:a", "192k",
            str(out_path)
        ]
    else:
        return common + [
            "-c:v", "libx264", "-crf", str(crf), "-preset", preset, "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            str(out_path)
        ]

def _iter_candidate_files(input_dir: Path):
    for p in sorted(input_dir.iterdir()):
        if not p.is_file():
            continue
        if p.suffix.lower() in EXTS or p.suffix == "":
            yield p

def process_all(input_dir: Path, output_dir: Path, ratios=("9x16","1x1","16x9"),
                codec="h264"):
    ensure_dirs(output_dir)
    files = list(_iter_candidate_files(input_dir))
    if not files:
        print("[INFO] No se encontraron videos en input/", file=sys.stderr)
        return 0

    for p in files:
        print(f"\n[FILE] {p.name}")
        stem = p.stem if p.suffix else p.name
        for r in ratios:
            w, h = PRESETS[r]
            # Guardar en subcarpeta por ratio
            out_path = output_dir / r / f"{stem}_{r}.mp4"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            print(f"  -> {r} → {out_path}")
            cmd = build_cmd_ffmpeg(p, out_path, w, h, codec=codec)
            subprocess.run(cmd, check=True)

    print("\n[DONE] Conversión completa.")
    return 0

if __name__ == "__main__":
    base = Path(__file__).resolve().parents[1]
    input_dir = base / "input"
    output_dir = base / "output"
    sys.exit(process_all(input_dir, output_dir, codec="h264"))
