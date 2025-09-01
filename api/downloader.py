# api/downloader.py
from __future__ import annotations
import asyncio
from pathlib import Path
from typing import Iterable
import re
import aiohttp

# Mapeo simple por Content-Type -> extensión sugerida
CT_EXT = {
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/x-msvideo": ".avi",
    "video/x-matroska": ".mkv",
    "application/octet-stream": ".mp4",  # muchos hosts devuelven esto
}

def _safe_name(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("._-")
    return s or "file"

def _guess_ext(ct: str | None) -> str:
    if not ct:
        return ".mp4"
    ct = ct.split(";")[0].strip().lower()
    return CT_EXT.get(ct, ".mp4")

def _filename_from_cd(cd: str | None) -> str | None:
    # Content-Disposition: attachment; filename="video.mp4"
    if not cd:
        return None
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd, flags=re.IGNORECASE)
    if m:
        return _safe_name(m.group(1))
    return None

def _filename_from_url(url: str) -> str:
    # Intenta sacar id o nombre básico de la URL
    # Google Drive (view / uc?id=): usa el id
    m = re.search(r"(?:/d/|id=)([A-Za-z0-9_-]{8,})", url)
    if m:
        return _safe_name(m.group(1))
    # Si hay un nombre al final del path
    tail = url.split("?")[0].rstrip("/").split("/")[-1]
    return _safe_name(tail or "file")

async def _download_one(session: aiohttp.ClientSession, url: str, dest_dir: Path, idx: int):
    async with session.get(url) as r:
        r.raise_for_status()
        ct = r.headers.get("Content-Type")
        cd = r.headers.get("Content-Disposition")

        name = _filename_from_cd(cd) or _filename_from_url(url)
        ext = Path(name).suffix.lower()
        if not ext:
            # si no hay extensión, infiere por content-type
            name += _guess_ext(ct)

        # evitar colisión de nombres
        out = dest_dir / name
        if out.exists():
            stem = out.stem
            suffix = out.suffix
            out = dest_dir / f"{stem}-{idx}{suffix}"

        with open(out, "wb") as f:
            async for chunk in r.content.iter_chunked(1 << 20):
                f.write(chunk)
        print(f"[DL] OK -> {out.name}")

async def download_many(urls: Iterable[str], dest_dir: Path):
    dest_dir.mkdir(parents=True, exist_ok=True)
    timeout = aiohttp.ClientTimeout(total=None, sock_connect=60, sock_read=600)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        tasks = []
        for i, u in enumerate(urls, start=1):
            tasks.append(_download_one(session, u, dest_dir, i))
        await asyncio.gather(*tasks)
    print(f"[DL] Descargados {len(list(urls))}/{len(list(urls))} archivos.")
