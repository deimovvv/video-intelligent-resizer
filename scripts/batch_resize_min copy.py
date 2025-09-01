#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

# Presets de salida
PRESETS = {
    "9x16":  (1080, 1920),
    "1x1":   (1080, 1080),
    "16x9":  (1920, 1080),
}

# Extensiones aceptadas
EXTS = {".mp4", ".mov", ".mxf", ".m4v", ".avi", ".mkv"}

def ensure_dirs(base_output: Path):
    for k in PRESETS.keys():
        (base_output / k).mkdir(parents=True, exist_ok=True)

def build_cmd_ffmpeg(in_path: Path, out_path: Path, w: int, h: int,
                     codec: str = "h264", crf: int = 18, preset: str = "medium",
                     prores_profile: int = 3):
    # scale to cover + crop centrado (sin barras negras)
    vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"

    if codec.lower() == "prores":
        return [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(in_path),
            "-vf", vf,
            "-c:v", "prores_ks", "-profile:v", str(prores_profile), "-pix_fmt", "yuv422p10le",
            "-c:a", "aac", "-b:a", "192k",
            str(out_path)
        ]
    else:
        return [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(in_path),
            "-vf", vf,
            "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
            "-c:a", "aac", "-b:a", "192k",
            str(out_path)
        ]

def process_all(input_dir: Path, output_dir: Path, ratios=("9x16","1x1","16x9"), codec="h264"):
    ensure_dirs(output_dir)
    files = [p for p in sorted(input_dir.iterdir()) if p.suffix.lower() in EXTS]
    if not files:
        print("[INFO] No se encontraron videos en input/", file=sys.stderr)
        return 0

    for p in files:
        print(f"\n[FILE] {p.name}")
        stem = p.stem
        for r in ratios:
            w, h = PRESETS[r]
            out_path = output_dir / r / f"{stem}_{r}.mp4"
            cmd = build_cmd_ffmpeg(p, out_path, w, h, codec=codec)
            print(f"  -> {r} → {out_path.name}")
            subprocess.run(cmd, check=True)

    print("\n[DONE] Conversión completa.")
    return 0

if __name__ == "__main__":
    base = Path(__file__).resolve().parents[1]
    input_dir = base / "input"
    output_dir = base / "output"
    codec = "h264"  # cambiar a "prores" si querés ProRes
    sys.exit(process_all(input_dir, output_dir, codec=codec))
