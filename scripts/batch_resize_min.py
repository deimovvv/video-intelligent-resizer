# scripts/batch_resize_min.py
import sys, subprocess
from pathlib import Path

EXTS = {".mp4", ".mov", ".mkv", ".m4v", ".avi", ".webm", ""}

# Presets por ratio: (W, H)
PRESETS = {
    "9x16":  (1080, 1920),
    "1x1":   (1080, 1080),
    "16x9":  (1920, 1080),
}

def ensure_dirs(p: Path): p.mkdir(parents=True, exist_ok=True)

def onepass_cmd(in_path: Path, out_9x16: Path, out_1x1: Path, out_16x9: Path,
                vcodec="libx264", preset="veryfast", crf="22", copy_audio=True):
    # armo filter_complex con split=3 y pad/scale para cada ratio
    fc = (
        "[0:v]split=3[vA][vB][vC];"
        "[vA]scale=1080:1920:force_original_aspect_ratio=decrease,"
        "pad=1080:1920:(1080-iw)/2:(1920-ih)/2,setsar=1[v9];"
        "[vB]scale=1080:1080:force_original_aspect_ratio=decrease,"
        "pad=1080:1080:(1080-iw)/2:(1080-ih)/2,setsar=1[v1];"
        "[vC]scale=1920:1080:force_original_aspect_ratio=decrease,"
        "pad=1920:1080:(1920-iw)/2:(1080-ih)/2,setsar=1[v16]"
    )
    a_map = ["-c:a", "copy"] if copy_audio else ["-c:a", "aac", "-b:a", "192k"]

    return [
        "ffmpeg", "-y", "-i", str(in_path),
        "-filter_complex", fc,

        # 9x16
        "-map", "[v9]", "-map", "0:a?", "-c:v", vcodec, "-preset", preset, "-crf", crf,
        "-movflags", "+faststart", "-threads", "0", *a_map, str(out_9x16),

        # 1x1
        "-map", "[v1]", "-map", "0:a?", "-c:v", vcodec, "-preset", preset, "-crf", crf,
        "-movflags", "+faststart", "-threads", "0", *a_map, str(out_1x1),

        # 16x9
        "-map", "[v16]", "-map", "0:a?", "-c:v", vcodec, "-preset", preset, "-crf", crf,
        "-movflags", "+faststart", "-threads", "0", *a_map, str(out_16x9),
    ]

def iter_inputs(input_dir: Path):
    for p in sorted(input_dir.iterdir()):
        if p.is_file() and (p.suffix.lower() in EXTS):
            yield p

def process_all(input_dir: Path, output_dir: Path,
                vcodec="libx264", preset="veryfast", crf="22", copy_audio=True):
    ensure_dirs(output_dir)
    files = list(iter_inputs(input_dir))
    if not files:
        print("[INFO] No se encontraron videos en input/")
        return 0

    for p in files:
        print(f"\n[FILE] {p.name}")
        stem = p.stem if p.suffix else p.name

        out_9 = output_dir / f"{stem}_9x16.mp4"
        out_1 = output_dir / f"{stem}_1x1.mp4"
        out_16 = output_dir / f"{stem}_16x9.mp4"

        cmd = onepass_cmd(p, out_9, out_1, out_16, vcodec=vcodec, preset=preset, crf=crf, copy_audio=copy_audio)
        print("  -> 9x16 / 1x1 / 16x9 (one-pass)")
        subprocess.run(cmd, check=True)

    print("\n[DONE] Conversión completa.")
    return 0

if __name__ == "__main__":
    base = Path(__file__).resolve().parents[1]
    input_dir = base / "input"
    output_dir = base / "output"

    # Ajustes rápidos por flags (opcional)
    vcodec = "libx264"      # si tenés NVIDIA: "h264_nvenc" ; Intel QSV: "h264_qsv"
    preset = "veryfast"     # para máxima velocidad: "ultrafast"
    crf = "22"              # menor = más calidad, más pesado
    copy_audio = True       # copia audio si existe

    sys.exit(process_all(input_dir, output_dir, vcodec=vcodec, preset=preset, crf=crf, copy_audio=copy_audio))
